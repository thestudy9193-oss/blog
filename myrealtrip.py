"""
마이리얼트립 파트너 API 유틸리티
===================================
투어/액티비티, 숙소 실시간 가격 조회
Base URL: https://partner-ext-api.myrealtrip.com
Auth: Authorization: Bearer {API_KEY}
"""

from __future__ import annotations

import os
import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://partner-ext-api.myrealtrip.com"
PARTNER_DISCLOSURE = "마이리얼트립과 함께하는 마케팅 파트너십을 통해 여행자가 구매할 때마다 일정 비율의 수수료를 지급받습니다."


def _headers() -> dict:
    key = os.getenv("MRT_API_KEY", "")
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def search_tours(keyword: str, size: int = 3) -> list[dict]:
    """투어·액티비티 상품 검색."""
    try:
        res = requests.post(
            f"{BASE_URL}/v1/products/tna/search",
            headers=_headers(),
            json={"keyword": keyword, "page": 1, "pageSize": size},
            timeout=8,
        )
        data = res.json()
        return data.get("data", {}).get("items", [])
    except Exception:
        return []


def search_hotels(keyword: str, check_in: str, check_out: str, adult: int = 2, size: int = 3) -> list[dict]:
    """숙소 검색."""
    try:
        res = requests.post(
            f"{BASE_URL}/v1/products/accommodation/search",
            headers=_headers(),
            json={
                "keyword": keyword,
                "checkIn": check_in,
                "checkOut": check_out,
                "adultCount": adult,
                "childCount": 0,
                "pageSize": size,
            },
            timeout=8,
        )
        data = res.json()
        return data.get("data", {}).get("items", [])
    except Exception:
        return []


def format_tours_text(tours: list[dict]) -> str:
    """투어 목록을 블로그 삽입용 텍스트로 변환."""
    if not tours:
        return ""
    lines = ["[ 마이리얼트립 추천 투어·액티비티 ]", ""]
    for t in tours:
        name = t.get("itemName", "")
        price = t.get("priceDisplay", "")
        score = t.get("reviewScore", "")
        count = t.get("reviewCount", 0)
        url = t.get("productUrl", "")
        lines.append(f"✔️ {name}")
        if price:
            lines.append(f"   💸 {price}")
        if score:
            lines.append(f"   ⭐ {score} ({count:,}개 리뷰)")
        lines.append(f"   🔗 {url}")
        lines.append("")
    return "\n".join(lines)


def format_hotels_text(hotels: list[dict]) -> str:
    """숙소 목록을 블로그 삽입용 텍스트로 변환."""
    if not hotels:
        return ""
    lines = ["[ 마이리얼트립 추천 숙소 ]", ""]
    for h in hotels:
        name = h.get("itemName", "")
        price = h.get("salePrice", 0)
        stars = "★" * int(h.get("starRating", 0))
        score = h.get("reviewScore", "")
        count = h.get("reviewCount", 0)
        url = h.get("productUrl", "")
        lines.append(f"✔️ {name} {stars}")
        if price:
            lines.append(f"   💸 1박 {price:,}원~")
        if score:
            lines.append(f"   ⭐ {score} ({count:,}개 리뷰)")
        lines.append(f"   🔗 {url}")
        lines.append("")
    return "\n".join(lines)
