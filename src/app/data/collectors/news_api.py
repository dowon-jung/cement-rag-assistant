"""
네이버 뉴스 검색 API 수집기

수집 대상: 시멘트 수요 / 건설 경기 / 유연탄 가격 관련 뉴스
API 문서: https://developers.naver.com/docs/serviceapi/search/news/news.md
"""

import asyncio
import json
import logging
import re
from datetime import datetime

import httpx
from redis.asyncio import Redis

from app.core.config import settings

logger = logging.getLogger(__name__)

# 검색 키워드
DEFAULT_KEYWORDS = ["시멘트 수요", "건설 경기", "유연탄 가격"]

# Redis 캐시 TTL (30분)
CACHE_TTL = 1800

NAVER_SEARCH_URL = "https://openapi.naver.com/v1/search/news.json"


def _strip_html(text: str) -> str:
    """HTML 태그 제거"""
    return re.sub(r"<[^>]+>", "", text or "").strip()


class NewsCollector:
    def __init__(self, redis: Redis):
        self.redis = redis
        self.http = httpx.AsyncClient(
            timeout=10.0,
            headers={
                "X-Naver-Client-Id": settings.naver_client_id,
                "X-Naver-Client-Secret": settings.naver_client_secret,
            },
        )

    async def fetch(
        self,
        keywords: list[str] | None = None,
        display: int = 10,
    ) -> dict:
        """
        키워드별 뉴스 수집 후 통합 반환.
        3개 키워드를 asyncio.gather로 병렬 호출.
        """
        if keywords is None:
            keywords = DEFAULT_KEYWORDS

        # 에어갭 모드 → DB fallback
        if settings.airgap_mode:
            return await self._fetch_from_db(keywords)

        # 3개 키워드 병렬 호출
        results = await asyncio.gather(
            *[self._fetch_keyword(kw, display) for kw in keywords],
            return_exceptions=True,
        )

        articles = []
        for kw, result in zip(keywords, results):
            if isinstance(result, Exception):
                logger.warning(f"뉴스 수집 실패 ({kw}): {result}")
                continue
            articles.extend(result)

        # 중복 제거 (link 기준)
        seen = set()
        unique_articles = []
        for a in articles:
            if a["link"] not in seen:
                seen.add(a["link"])
                unique_articles.append(a)

        # 날짜 최신순 정렬
        unique_articles.sort(key=lambda x: x.get("pub_date", ""), reverse=True)

        return {
            "articles": unique_articles[:display],
            "keywords": keywords,
            "collected_at": datetime.now().isoformat(),
            "total": len(unique_articles),
        }

    async def _fetch_keyword(self, keyword: str, display: int) -> list[dict]:
        """단일 키워드 뉴스 검색"""
        now_hour = datetime.now().strftime("%Y%m%d_%H")
        cache_key = f"news:{keyword}:{now_hour}"

        # Redis 캐시 확인
        cached = await self.redis.get(cache_key)
        if cached:
            logger.debug(f"캐시 HIT: {cache_key}")
            return json.loads(cached)

        # API 호출
        resp = await self.http.get(
            NAVER_SEARCH_URL,
            params={"query": keyword, "display": display, "sort": "date"},
        )
        resp.raise_for_status()
        body = resp.json()

        articles = [
            {
                "title": _strip_html(item["title"]),
                "link": item["link"],
                "description": _strip_html(item["description"]),
                "pub_date": item.get("pubDate", ""),
                "keyword": keyword,
            }
            for item in body.get("items", [])
        ]

        # Redis 캐시 저장
        await self.redis.setex(cache_key, CACHE_TTL, json.dumps(articles, ensure_ascii=False))
        logger.info(f"뉴스 수집 완료: '{keyword}' — {len(articles)}건")
        return articles

    async def _fetch_from_db(self, keywords: list[str]) -> dict:
        """PostgreSQL에서 최근 뉴스 조회 (에어갭 fallback)"""
        logger.warning("DB fallback: 실제 DB 연결은 Phase 3에서 구현")
        raise NotImplementedError("DB fallback은 Phase 3에서 구현 예정")

    async def close(self):
        await self.http.aclose()
