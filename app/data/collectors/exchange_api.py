"""
한국은행 ECOS API 환율 수집기

수집 대상: USD/KRW 매매기준율
API 문서: https://ecos.bok.or.kr/api/#/DevGuide/TopPage
"""

import json
import logging
from datetime import date, datetime, timedelta

import httpx
from redis.asyncio import Redis

from app.core.config import settings

logger = logging.getLogger(__name__)

# ECOS API 통계표 코드 (원/달러 매매기준율)
STAT_CODE = "731Y001"
ITEM_CODE = "0000001"

# Redis 캐시 TTL (1시간)
CACHE_TTL = 3600


class ExchangeCollector:
    def __init__(self, redis: Redis):
        self.redis = redis
        self.http = httpx.AsyncClient(timeout=10.0)

    async def fetch(self, target_date: date | None = None) -> dict:
        """
        환율 데이터 반환.
        Redis 캐시 HIT → 캐시 반환
        MISS + AIRGAP_MODE=false → ECOS API 호출
        MISS + AIRGAP_MODE=true  → PostgreSQL fallback
        """
        if target_date is None:
            target_date = date.today()

        cache_key = f"exchange:usd_krw:{target_date.strftime('%Y%m%d')}"

        # 1. Redis 캐시 확인
        cached = await self.redis.get(cache_key)
        if cached:
            logger.debug(f"캐시 HIT: {cache_key}")
            return json.loads(cached)

        # 2. 에어갭 모드 → DB fallback
        if settings.airgap_mode:
            return await self._fetch_from_db(target_date)

        # 3. ECOS API 호출
        try:
            data = await self._call_ecos_api(target_date)
            # Redis 캐시 저장
            await self.redis.setex(cache_key, CACHE_TTL, json.dumps(data))
            return data
        except Exception as e:
            logger.warning(f"ECOS API 호출 실패: {e} → DB fallback 시도")
            return await self._fetch_from_db(target_date)

    async def _call_ecos_api(self, target_date: date) -> dict:
        """ECOS API 실제 호출"""
        date_str = target_date.strftime("%Y%m%d")
        url = (
            f"https://ecos.bok.or.kr/api/StatisticSearch"
            f"/{settings.bok_api_key}/json/kr/1/1"
            f"/{STAT_CODE}/DD/{date_str}/{date_str}/{ITEM_CODE}"
        )

        resp = await self.http.get(url)
        resp.raise_for_status()
        body = resp.json()

        rows = body.get("StatisticSearch", {}).get("row", [])
        if not rows:
            # 주말·공휴일이면 전일 데이터 재시도
            prev_date = target_date - timedelta(days=1)
            logger.info(f"{date_str} 데이터 없음 → {prev_date} 재시도")
            return await self._call_ecos_api(prev_date)

        rate = float(rows[0]["DATA_VALUE"])
        result = {
            "currency": "USD/KRW",
            "rate": rate,
            "base_date": rows[0]["TIME"],
            "collected_at": datetime.now().isoformat(),
            "source": "ecos",
        }
        logger.info(f"환율 수집 완료: {rate} ({date_str})")
        return result

    async def _fetch_from_db(self, target_date: date) -> dict:
        """PostgreSQL에서 가장 최근 환율 조회 (fallback)"""
        # 실제 DB 연결은 Phase 3에서 완성
        # 지금은 구조만 정의
        logger.warning("DB fallback: 실제 DB 연결은 Phase 3에서 구현")
        raise NotImplementedError("DB fallback은 Phase 3에서 구현 예정")

    async def close(self):
        await self.http.aclose()
