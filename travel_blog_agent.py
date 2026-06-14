"""
여행 블로그 자동화 에이전트
=============================
잉슬 네이버 블로그 스타일에 맞는 여행 블로그 글을 자동 생성합니다.
사진을 첨부하면 사진 내용을 분석해서 글에 반영합니다.

실행: python travel_blog_agent.py
의존성: pip install -r requirements.txt
"""

from __future__ import annotations

import base64
import os
import subprocess
import sys
import tempfile

from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

# 블로그 스타일 가이드 (실제 글 분석 기반)
STYLE_GUIDE = """
[블로그 스타일 가이드 - 잉슬 네이버 블로그]

## 전반적 특징
- 공백 제외 1500~1800자
- 말투: ~해요, ~이에요, ~더라구요, ~같아요, ~거예요 (친근한 존댓말)
- 줄바꿈: 짧은 문장을 여러 줄로 나누어 씀 (한 문장을 2~3줄로 분리)
- 개인 경험을 자연스럽게 녹인 정보성 여행 블로그
- 글쓴이가 직접 다녀온 것처럼 1인칭으로 작성

## 제목 형식
[여행지] + [장소/업체명] + [키워드] + (부제 또는 세부항목)
예시:
- "사이판 프리다이빙 한인 업체 가격 비교 (다이브위시, 프로다이버스, 딥블루, 아쿠아다이브)"
- "푸꾸옥 남부 숙소 추천: 라페스타 힐튼 호텔 리뷰 (가격, 룸컨디션, 예약 꿀팁)"

## 소제목 형식
[ 소제목명 ] — 반드시 대괄호와 공백 포함
예시: "[ 라페스타 힐튼 호텔 소개 ]", "[ 사이판 프리다이빙 다이빙샵 가격 비교 ]"

## 이모지 사용 규칙
정보 키포인트 앞에 반드시 이모지 사용:
- 📍 위치 정보
- 💸 가격 정보
- 📌 주요 정보/포인트
- ✔️ 체크 항목
- ✅ 추천/장점
- ☑️ 참고/팁 항목
- ⏳ 시간/체크인 정보
- 내용에 어울리는 추가 이모지 자유롭게 사용

## 글 구조 (반드시 이 순서로)
1. 서두 (2~3문단, 이모지 없음)
   - 개인 경험/여행 상황 소개
   - "이번에 저는..." / "제가 직접 가보니..." 형식
   - 이 글에서 알려줄 내용 한 줄 예고

2. [ 소제목1 ] — 장소/서비스 기본 소개 + 이모지 정보 리스트
   - 📍 위치
   - 💸 가격
   - 기타 주요 정보를 이모지 리스트로

3. [ 소제목2 ] — 가격 상세 / 비교 정보
   - 실제 가격 수치 포함
   - "생각보다 ..." 형식의 개인 반응 포함

4. [ 소제목3 ] — 상세 후기 / 경험
   - 개인 경험 중심
   - "제가 느끼기엔..." / "솔직히 말하면..." 형식

5. [ 꿀팁 소제목 ] — ☑️ 리스트
   - 실용적인 팁 3~5개
   - 반드시 ☑️ 이모지로 시작

6. 마무리 (2~3줄)
   - 장소/서비스 간단 정리
   - 추천 멘트로 마무리
   - "다들 즐거운 ... 여행 되시길 바랄게요!" 형식

## 실제 글 예시 서두
"이번에 저는 첫 사이판 여행을 떠나는데요
초보 다이버지만,
제주 - 세부 - 보홀 - 다음으로
사이판 여행을 준비중이에요!"

## 실제 이모지 리스트 예시
"[ 라페스타 푸꾸옥 큐리오 컬렉션 바이 힐튼]
📍Sunset Town, An Thới, Phú Quốc
💸 예약가격 : 10만원대 중반 (15~20만원 사이)
⏳체크인 : 3시 (유연하게 얼리 체크인 가능)
🚠 혼똔섬 케이블카 도보 5분거리 위치
🏜️ 수영장에서 인생 노을을 볼 수 있음"

## 실제 꿀팁 예시
"[라페스타 힐튼 푸꾸옥 꿀팁]
☑️밤 9시쯤 키스오브더씨 공연의 불꽃놀이 관람 가능
☑️키스오브브릿지 무료 입장 가능"
"""

POST_TYPES = {
    "1": "숙소 리뷰",
    "2": "맛집/카페 리뷰",
    "3": "액티비티/투어 가격 비교",
    "4": "여행 코스 추천",
    "5": "여행 준비/꿀팁",
}

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".heif"}
MIME_MAP = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    # .heic/.heif는 sips로 변환 후 jpeg로 전송
}


def convert_heic_to_jpeg(path: str) -> str | None:
    """iPhone HEIC 사진을 macOS 내장 sips로 JPEG 변환. 임시 파일 경로 반환."""
    tmp = tempfile.mktemp(suffix=".jpg")
    result = subprocess.run(
        ["sips", "-s", "format", "jpeg", path, "--out", tmp],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0 and os.path.exists(tmp):
        return tmp
    return None


def load_image_block(path: str) -> dict | None:
    """이미지 파일을 Claude API용 content block으로 변환."""
    path = path.strip().strip("'\"")  # 터미널 드래그 시 따옴표 제거

    if not os.path.isfile(path):
        print(f"   ⚠️  파일을 찾을 수 없어요: {path}")
        return None

    ext = os.path.splitext(path)[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        print(f"   ⚠️  지원하지 않는 형식이에요: {ext}  (JPG, PNG, WEBP, GIF, HEIC 가능)")
        return None

    tmp_to_delete = None

    # HEIC/HEIF → JPEG 변환
    if ext in (".heic", ".heif"):
        converted = convert_heic_to_jpeg(path)
        if not converted:
            print(f"   ⚠️  HEIC 변환 실패: {path}")
            return None
        path = converted
        tmp_to_delete = converted
        ext = ".jpg"

    mime_type = MIME_MAP.get(ext, "image/jpeg")

    try:
        with open(path, "rb") as f:
            raw = f.read()
    except Exception as e:
        print(f"   ⚠️  이미지 읽기 실패: {e}")
        return None
    finally:
        if tmp_to_delete and os.path.exists(tmp_to_delete):
            os.remove(tmp_to_delete)

    # Gemini inline_data 형식
    return {"mime_type": mime_type, "data": raw}


def collect_images() -> list[dict]:
    """사용자에게 사진 경로를 입력받아 이미지 블록 리스트 반환."""
    print("📸 사진 첨부 (최대 10장)")
    print("   Finder에서 터미널로 파일을 드래그하면 경로가 자동 입력돼요.")
    print("   한 장씩 Enter, 완료하면 빈 Enter")
    print()

    images = []
    idx = 1
    while len(images) < 10:
        raw = input(f"   사진 {idx} 경로 (완료: 빈 Enter): ").strip()
        if not raw:
            break
        block = load_image_block(raw)
        if block:
            images.append(block)
            print(f"   ✅ 사진 {idx} 추가됨")
            idx += 1

    return images


def generate_blog_post(
    topic: str,
    post_type: str,
    extra_info: str,
    client: genai.Client,
    images: list[dict] | None = None,
) -> str:
    extra_section = f"\n- 추가 정보: {extra_info}" if extra_info.strip() else ""

    if images:
        photo_instruction = f"""

## 첨부된 사진 {len(images)}장을 분석해서 글에 반영하세요
- 사진 속 장소, 음식, 인테리어, 분위기, 색감 등 보이는 요소를 글에 구체적으로 묘사해주세요
- 사진에서 읽을 수 있는 정보(메뉴판 가격, 간판 이름, 특이한 데코 등)가 있으면 적극 활용하세요
- [이미지: 사진 설명] 태그를 사진 순서대로 적절한 위치에 배치해주세요
- 사진 내용을 보고 제목과 소제목도 더 구체적으로 만들어주세요"""
    else:
        photo_instruction = "\n3. 이미지가 들어갈 자리는 [이미지: 간단 설명] 형태로 표시"

    prompt_text = f"""당신은 '잉슬'이라는 닉네임의 20~30대 여성 여행 블로거입니다.
아래 스타일 가이드를 완벽하게 따라서 네이버 블로그 글을 작성해주세요.

{STYLE_GUIDE}

## 이번 글 작성 요청
- 주제: {topic}
- 글 유형: {post_type}{extra_section}{photo_instruction}

## 작성 규칙
1. 제목을 첫 줄에 쓰고, 빈 줄 하나 두고 본문 시작
2. 네이버 스마트에디터에 바로 붙여넣을 수 있는 텍스트만 작성 (마크다운 # ## 기호 절대 사용 금지)
3. 공백 제외 글자수 1500~1800자 준수
4. 소제목은 반드시 [ 소제목 ] 대괄호 형식 사용

지금 바로 글을 작성해주세요:"""

    parts: list = []
    if images:
        for img in images:
            parts.append(types.Part.from_bytes(data=img["data"], mime_type=img["mime_type"]))
    parts.append(prompt_text)

    response = client.models.generate_content(model=GEMINI_MODEL, contents=parts)
    return response.text


def copy_to_clipboard(text: str) -> bool:
    try:
        process = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
        process.communicate(text.encode("utf-8"))
        return True
    except Exception:
        return False


def send_notification(title: str, message: str):
    try:
        script = f'display notification "{message}" with title "{title}"'
        subprocess.run(["osascript", "-e", script], check=False)
    except Exception:
        pass


def print_separator(char: str = "=", width: int = 55):
    print(char * width)


def run_generation(topic, post_type, extra_info, images, client):
    """글 생성 → 출력 → 클립보드 복사."""
    has_photos = bool(images)
    photo_msg = f" (사진 {len(images)}장 분석 포함)" if has_photos else ""
    print(f"🤖 '{topic}' ({post_type}){photo_msg} 글 생성 중... (10~20초 소요)")
    print()

    post = generate_blog_post(topic, post_type, extra_info, client, images)

    print_separator()
    print("📝 생성된 블로그 글")
    print_separator()
    print()
    print(post)
    print()
    print_separator()

    char_count = len(post.replace(" ", "").replace("\n", ""))
    print(f"📊 공백 제외 글자수: {char_count}자")

    copied = copy_to_clipboard(post)
    if copied:
        print("✅ 클립보드에 복사 완료!")
        send_notification(
            "여행 블로그 글 생성 완료",
            f"'{topic}' 글이 클립보드에 복사되었습니다. 네이버 블로그에 붙여넣기 하세요!",
        )
    else:
        print("⚠️  클립보드 복사 실패 — 위 텍스트를 직접 복사해주세요.")

    print()
    print("👉 네이버 블로그 글쓰기 열고 Cmd+V 로 붙여넣기 하세요!")
    print()
    return post


def main():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ GEMINI_API_KEY가 설정되지 않았습니다.")
        print("   .env 파일에 GEMINI_API_KEY=... 를 추가해주세요.")
        print("   키 발급: https://aistudio.google.com/apikey")
        sys.exit(1)

    client = genai.Client(api_key=api_key)

    print_separator()
    print("  ✈️  잉슬 여행 블로그 자동화 에이전트")
    print_separator()
    print()

    topic = input("📌 블로그 주제 (예: 제주도 협재 카페, 방콕 호텔 추천): ").strip()
    if not topic:
        print("❌ 주제를 입력해주세요.")
        sys.exit(1)

    print()
    print("글 유형을 선택하세요:")
    for key, val in POST_TYPES.items():
        print(f"  {key}. {val}")
    print()
    choice = input("선택 (1~5, 기본값 1): ").strip() or "1"
    post_type = POST_TYPES.get(choice, "숙소 리뷰")

    print()
    extra_info = input("추가로 넣고 싶은 정보가 있으면 입력하세요 (없으면 Enter): ").strip()

    # 사진 첨부 여부 확인
    print()
    attach = input("📸 사진을 첨부하시겠어요? (y/n, 기본값 n): ").strip().lower()
    images: list[dict] = []
    if attach == "y":
        print()
        images = collect_images()
        if images:
            print(f"\n   총 {len(images)}장 첨부 완료!")
        else:
            print("   사진 없이 진행합니다.")
        print()

    try:
        run_generation(topic, post_type, extra_info, images, client)

        # 재생성 옵션
        while True:
            again = input("다시 생성할까요? (y/n, 기본값 n): ").strip().lower()
            if again != "y":
                break
            print()
            run_generation(topic, post_type, extra_info, images, client)

    except Exception as e:
        err = str(e)
        if "API_KEY" in err or "api key" in err.lower():
            print("❌ API 키가 올바르지 않습니다. .env 파일의 GEMINI_API_KEY를 확인해주세요.")
        else:
            print(f"❌ 오류 발생: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
