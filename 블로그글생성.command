#!/bin/bash
# 여행 블로그 에이전트 웹 앱 실행
cd "$(dirname "$0")"

# 가상환경 없으면 생성 + 패키지 설치
if [ ! -d "venv" ]; then
    echo "📦 처음 실행 — 가상환경 생성 중..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -q -r requirements.txt
    echo "✅ 설치 완료!"
    echo ""
else
    source venv/bin/activate
    # 새 패키지 추가됐을 수 있으므로 조용히 업데이트
    pip install -q -r requirements.txt
fi

# .env 파일 없으면 안내
if [ ! -f ".env" ]; then
    echo "⚠️  .env 파일이 없습니다."
    echo "   .env.example 을 복사해서 .env 를 만들고"
    echo "   GEMINI_API_KEY 를 입력해주세요."
    echo ""
    echo "   cp .env.example .env"
    echo ""
    read -p "Enter 키를 누르면 종료합니다..."
    exit 1
fi

echo "🚀 웹 앱 시작 중..."
echo "   브라우저가 자동으로 열립니다."
echo "   종료하려면 이 창에서 Ctrl+C 를 누르세요."
echo ""

# 브라우저 자동 열기 (1초 후)
(sleep 1 && open http://localhost:8000) &

# 서버 시작
uvicorn app:app --host 127.0.0.1 --port 8000 --reload
