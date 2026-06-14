"""
여행 블로그 에이전트 — 웹 서버
================================
실행: uvicorn app:app --reload
또는 블로그글생성.command 더블클릭
"""

from __future__ import annotations

import os
import subprocess
import tempfile

from google import genai
from google.genai import types
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from myrealtrip import (
    PARTNER_DISCLOSURE,
    format_hotels_text,
    format_tours_text,
    search_hotels,
    search_tours,
)

load_dotenv()

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

STYLE_GUIDE = """
[블로그 스타일 가이드 - 잉슬 네이버 블로그]

## 전반적 특징
- 공백 제외 1500~1800자 (마이리얼트립 상품 섹션 제외)
- 말투: ~해요, ~이에요, ~더라구요, ~같아요, ~거예요 (친근한 존댓말)
- 개인 경험을 자연스럽게 녹인 정보성 여행 블로그
- 글쓴이가 직접 다녀온 것처럼 1인칭으로 작성

## 줄바꿈 규칙 (매우 중요)
- 한 문장을 반드시 2~3줄로 나누어 씀
- 각 행은 짧게, 15자 내외로 끊어서 작성
- 문단 사이에는 반드시 빈 줄(엔터 두 번) 삽입
- 예시:
  "이번에 저는 첫 사이판 여행을 떠나는데요
  초보 다이버지만,
  제주 - 세부 - 보홀 - 다음으로
  사이판 여행을 준비중이에요!"

## 제목 형식
[여행지] + [장소/업체명] + [키워드] + (부제 또는 세부항목)
예시:
- "사이판 프리다이빙 한인 업체 가격 비교 (다이브위시, 프로다이버스, 딥블루, 아쿠아다이브)"
- "푸꾸옥 남부 숙소 추천: 라페스타 힐튼 호텔 리뷰 (가격, 룸컨디션, 예약 꿀팁)"

## 소제목 형식
[ 소제목명 ] — 반드시 대괄호와 공백 포함

## 이모지 사용 규칙
- 📍 위치 정보  💸 가격  📌 주요 정보  ✔️ 체크  ✅ 추천  ☑️ 팁  ⏳ 시간
- 내용에 어울리는 추가 이모지 자유롭게 사용

## 글 구조
1. 서두 (2~3문단): 개인 경험/상황 소개 (각 문장은 짧게 줄바꿈)
2. [ 소제목1 ]: 장소/서비스 기본 소개 + 이모지 정보 리스트 (📍💸⏳ 등)
3. [ 소제목2 ]: 가격 상세 / 비교 정보 + 개인 반응
4. [ 소제목3 ]: 상세 후기 / 경험 (개인 경험 중심)
5. [ 꿀팁 소제목 ]: ☑️ 리스트 3~5개
6. 마무리 (2~3줄): 정리 + "다들 즐거운 ... 여행 되시길 바랄게요!" 형식
"""

POST_TYPES = {
    "1": "숙소 리뷰",
    "2": "맛집/카페 리뷰",
    "3": "액티비티/투어 가격 비교",
    "4": "여행 코스 추천",
    "5": "여행 준비/꿀팁",
}

app = FastAPI()


def convert_heic(data: bytes) -> bytes:
    tmp_in = tempfile.mktemp(suffix=".heic")
    tmp_out = tempfile.mktemp(suffix=".jpg")
    try:
        with open(tmp_in, "wb") as f:
            f.write(data)
        result = subprocess.run(
            ["sips", "-s", "format", "jpeg", tmp_in, "--out", tmp_out],
            capture_output=True,
        )
        if result.returncode == 0 and os.path.exists(tmp_out):
            with open(tmp_out, "rb") as f:
                return f.read()
    except FileNotFoundError:
        pass  # sips not available (non-macOS); pass HEIC as-is
    finally:
        for p in [tmp_in, tmp_out]:
            if os.path.exists(p):
                os.unlink(p)
    return data


def build_prompt(topic: str, post_type: str, extra_info: str, has_images: bool) -> str:
    extra_section = f"\n- 추가 정보: {extra_info}" if extra_info.strip() else ""
    photo_instruction = (
        """

## 첨부된 사진을 분석해서 글에 반영하세요
- 사진 속 장소, 음식, 인테리어, 분위기, 색감 등 보이는 요소를 구체적으로 묘사해주세요
- 사진에서 읽을 수 있는 정보(메뉴판 가격, 간판 이름, 특이한 데코 등)가 있으면 적극 활용하세요
- [이미지: 사진 설명] 태그를 사진 순서대로 적절한 위치에 배치해주세요
- 사진 내용을 보고 제목과 소제목도 더 구체적으로 만들어주세요"""
        if has_images
        else ""
    )

    return f"""당신은 '잉슬'이라는 닉네임의 20~30대 여성 여행 블로거입니다.
아래 스타일 가이드를 완벽하게 따라서 네이버 블로그 글을 작성해주세요.

{STYLE_GUIDE}

## 이번 글 작성 요청
- 주제: {topic}
- 글 유형: {post_type}{extra_section}{photo_instruction}

## 작성 규칙 (반드시 준수)
1. 제목을 첫 줄에 쓰고, 빈 줄 하나 두고 본문 시작
2. 네이버 스마트에디터에 바로 붙여넣을 수 있는 텍스트만 작성 (마크다운 # ## 기호 절대 사용 금지)
3. 공백 제외 글자수 1500~1800자 준수
4. 소제목은 반드시 [ 소제목 ] 대괄호 형식 사용
5. 줄바꿈을 자주 사용 — 한 문장을 2~3줄로 끊어서 네이버 블로그 특유의 읽기 쉬운 형식으로 작성
6. 각 문단 사이에는 반드시 빈 줄 삽입

지금 바로 글을 작성해주세요:"""


def assemble_post(body: str, tours_text: str, hotels_text: str, use_mrt: bool) -> str:
    """생성된 블로그 본문 + 마이리얼트립 상품 조합."""
    parts = []

    if use_mrt:
        parts.append(PARTNER_DISCLOSURE)
        parts.append("")

    parts.append(body.strip())

    if use_mrt and (tours_text or hotels_text):
        parts.append("")
        parts.append("─" * 30)
        parts.append("")
        if tours_text:
            parts.append(tours_text)
        if hotels_text:
            parts.append(hotels_text)

    return "\n".join(parts)


_ROOT = os.path.dirname(os.path.abspath(__file__))

@app.get("/")
def index():
    return FileResponse(os.path.join(_ROOT, "index.html"))


@app.get("/post-types")
def get_post_types():
    return POST_TYPES


@app.post("/generate")
async def generate(
    topic: str = Form(...),
    post_type: str = Form(...),
    extra_info: str = Form(""),
    use_mrt: str = Form("false"),
    check_in: str = Form(""),
    check_out: str = Form(""),
    photos: list[UploadFile] = File(default=[]),
):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return JSONResponse(
            {"success": False, "error": "GEMINI_API_KEY가 설정되지 않았습니다. .env 파일을 확인해주세요."},
            status_code=500,
        )

    enable_mrt = use_mrt.lower() == "true"

    # 이미지 처리
    images = []
    for photo in photos:
        if not photo.filename:
            continue
        data = await photo.read()
        if not data:
            continue
        ext = os.path.splitext(photo.filename)[1].lower()
        mime_type = photo.content_type or "image/jpeg"
        if ext in (".heic", ".heif"):
            data = convert_heic(data)
            mime_type = "image/jpeg"
        images.append({"mime_type": mime_type, "data": data})

    try:
        # 마이리얼트립 상품 조회 (선택 기능)
        tours_text = ""
        hotels_text = ""
        if enable_mrt:
            tours = search_tours(topic, size=3)
            tours_text = format_tours_text(tours)

            if check_in and check_out:
                hotels = search_hotels(topic, check_in, check_out, size=3)
                hotels_text = format_hotels_text(hotels)

        # 블로그 글 생성
        client = genai.Client(api_key=api_key)
        prompt = build_prompt(topic, POST_TYPES.get(post_type, post_type), extra_info, bool(images))

        parts: list = []
        for img in images:
            parts.append(types.Part.from_bytes(data=img["data"], mime_type=img["mime_type"]))
        parts.append(prompt)

        response = client.models.generate_content(model=GEMINI_MODEL, contents=parts)
        body = response.text

        post = assemble_post(body, tours_text, hotels_text, enable_mrt)
        char_count = len(body.replace(" ", "").replace("\n", ""))

        return JSONResponse({
            "success": True,
            "post": post,
            "char_count": char_count,
            "mrt_included": enable_mrt and bool(tours_text or hotels_text),
        })

    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)
