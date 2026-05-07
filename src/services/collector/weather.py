"""
기상청 단기예보 API 수집기

수집 대상: 기온(TMP), 강수확률(POP), 풍속(WSD), 하늘상태(SKY)
API 문서: https://www.data.go.kr — 단기예보조회서비스
기본 격자 좌표: 단양 시멘트 공장 인근 (nx=83, ny=121)
"""

import json
import logging
import math
from datetime import datetime

import httpx
from redis.asyncio import Redis

from shared.config import settings

logger = logging.getLogger(__name__)

# Redis 캐시 TTL (1시간)
CACHE_TTL = 3600

WEATHER_URL = (
    "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst"
)

# 기상청 발표 시각 (3시간 간격)
BASE_TIMES = ["0200", "0500", "0800", "1100", "1400", "1700", "2000", "2300"]

# 수요 예측 기준
DEMAND_RULES = {
    "increase":  {"tmp_min": 10, "tmp_max": 28, "pop_max": 30},
    "decrease":  {"tmp_min": None, "tmp_max": 5, "pop_min": 70},
}


def _get_base_time() -> str:
    """현재 시각 기준 가장 최근 발표 시각 반환"""
    now_hour = datetime.now().hour
    now_min = datetime.now().minute
    current = now_hour * 100 + now_min

    for bt in reversed(BASE_TIMES):
        if current >= int(bt) + 10:  # 발표 후 10분 지나야 데이터 안정
            return bt
    return BASE_TIMES[-1]  # 자정 이전이면 전날 2300


def _latlon_to_grid(lat: float, lon: float) -> tuple[int, int]:
    """위경도 → 기상청 격자 좌표 변환"""
    RE = 6371.00877
    GRID = 5.0
    SLAT1 = 30.0
    SLAT2 = 60.0
    OLON = 126.0
    OLAT = 38.0
    XO = 43
    YO = 136

    DEGRAD = math.pi / 180.0
    re = RE / GRID
    slat1 = SLAT1 * DEGRAD
    slat2 = SLAT2 * DEGRAD
    olon = OLON * DEGRAD
    olat = OLAT * DEGRAD

    sn = math.tan(math.pi * 0.25 + slat2 * 0.5) / math.tan(math.pi * 0.25 + slat1 * 0.5)
    sn = math.log(math.cos(slat1) / math.cos(slat2)) / math.log(sn)
    sf = math.tan(math.pi * 0.25 + slat1 * 0.5)
    sf = (sf ** sn) * math.cos(slat1) / sn
    ro = math.tan(math.pi * 0.25 + olat * 0.5)
    ro = re * sf / (ro ** sn)

    ra = math.tan(math.pi * 0.25 + lat * DEGRAD * 0.5)
    ra = re * sf / (ra ** sn)
    theta = lon * DEGRAD - olon
    if theta > math.pi:
        theta -= 2.0 * math.pi
    if theta < -math.pi:
        theta += 2.0 * math.pi
    theta *= sn

    nx = int(ra * math.sin(theta) + XO + 0.5)
    ny = int(ro - ra * math.cos(theta) + YO + 0.5)
    return nx, ny


def _predict_demand(tmp: float | None, pop: int | None) -> tuple[str, str]:
    """기온·강수 기반 수요 예측"""
    if tmp is None or pop is None:
        return "유지", "데이터 부족"

    r = DEMAND_RULES
    if (
        r["increase"]["tmp_min"] <= tmp <= r["increase"]["tmp_max"]
        and pop <= r["increase"]["pop_max"]
    ):
        return "증가", f"기온 {tmp}°C, 강수확률 {pop}% — 건설 현장 작업 가능"

    if (
        (r["decrease"]["tmp_max"] is not None and tmp <= r["decrease"]["tmp_max"])
        or pop >= r["decrease"]["pop_min"]
    ):
        return "감소", f"기온 {tmp}°C 또는 강수확률 {pop}% — 건설 현장 작업 어려움"

    return "유지", f"기온 {tmp}°C, 강수확률 {pop}% — 보통 수준"


class WeatherCollector:
    def __init__(self, redis: Redis):
        self.redis = redis
        self.http = httpx.AsyncClient(timeout=10.0)

    async def fetch(self, nx: int = 83, ny: int = 121) -> dict:
        """
        단기예보 데이터 반환.
        기본 좌표: 단양 시멘트 공장 인근 (nx=83, ny=121)
        """
        today = datetime.now().strftime("%Y%m%d")
        base_time = _get_base_time()
        cache_key = f"weather:{nx}_{ny}:{today}_{base_time}"

        # 1. Redis 캐시 확인
        cached = await self.redis.get(cache_key)
        if cached:
            logger.debug(f"캐시 HIT: {cache_key}")
            return json.loads(cached)

        # 2. 에어갭 모드
        if settings.airgap_mode:
            return await self._fetch_from_db(nx, ny, today)

        # 3. 기상청 API 호출
        try:
            data = await self._call_weather_api(nx, ny, today, base_time)
            await self.redis.setex(cache_key, CACHE_TTL, json.dumps(data, ensure_ascii=False))
            return data
        except Exception as e:
            logger.warning(f"기상청 API 호출 실패: {e}")
            return await self._fetch_from_db(nx, ny, today)

    async def _call_weather_api(
        self, nx: int, ny: int, base_date: str, base_time: str
    ) -> dict:
        """기상청 단기예보 API 실제 호출"""
        resp = await self.http.get(
            WEATHER_URL,
            params={
                "serviceKey": settings.weather_api_key,
                "pageNo": 1,
                "numOfRows": 1000,
                "dataType": "JSON",
                "base_date": base_date,
                "base_time": base_time,
                "nx": nx,
                "ny": ny,
            },
        )
        resp.raise_for_status()
        body = resp.json()

        items = body["response"]["body"]["items"]["item"]

        # 카테고리별 값 추출 (가장 가까운 예보 시각)
        parsed: dict[str, float | int | None] = {
            "TMP": None, "POP": None, "WSD": None, "SKY": None
        }
        for item in items:
            cat = item["category"]
            if cat in parsed and parsed[cat] is None:
                try:
                    parsed[cat] = float(item["fcstValue"])
                except (ValueError, TypeError):
                    pass

        demand, reason = _predict_demand(parsed["TMP"], parsed.get("POP"))

        result = {
            "nx": nx,
            "ny": ny,
            "forecast_date": base_date,
            "forecast_time": base_time,
            "tmp": parsed["TMP"],
            "pop": int(parsed["POP"]) if parsed["POP"] is not None else None,
            "wsd": parsed["WSD"],
            "sky": int(parsed["SKY"]) if parsed["SKY"] is not None else None,
            "demand_forecast": demand,
            "reason": reason,
            "collected_at": datetime.now().isoformat(),
        }
        logger.info(f"날씨 수집 완료: 기온 {parsed['TMP']}°C, 강수 {parsed['POP']}% → 수요 {demand}")
        return result

    async def _fetch_from_db(self, nx: int, ny: int, target_date: str) -> dict:
        """PostgreSQL에서 최근 날씨 조회 (에어갭 fallback)"""
        logger.warning("DB fallback: 실제 DB 연결은 Phase 3에서 구현")
        raise NotImplementedError("DB fallback은 Phase 3에서 구현 예정")

    def latlon_to_grid(self, lat: float, lon: float) -> tuple[int, int]:
        """위경도 → 격자 좌표 변환 (외부 호출용)"""
        return _latlon_to_grid(lat, lon)

    async def close(self):
        await self.http.aclose()
