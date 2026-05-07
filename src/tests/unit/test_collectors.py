"""
데이터 수집기 단위 테스트

실행: pytest tests/test_collectors.py -v
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import date

from services.collector.exchange import ExchangeCollector
from services.collector.news import NewsCollector, _strip_html
from services.collector.weather import WeatherCollector, _latlon_to_grid, _predict_demand
from services.collector.coal import CoalPriceCollector
from services.collector.erp import generate as generate_erp


# ── 유틸 함수 테스트 ────────────────────────────────

class TestUtils:
    def test_strip_html(self):
        assert _strip_html("<b>시멘트</b> 수요") == "시멘트 수요"
        assert _strip_html("일반 텍스트") == "일반 텍스트"
        assert _strip_html("") == ""
        assert _strip_html(None) == ""

    def test_latlon_to_grid_seoul(self):
        """서울 위경도 → 격자 좌표"""
        nx, ny = _latlon_to_grid(37.5665, 126.9780)
        # 서울 격자 좌표 (60, 127) 근방
        assert 55 <= nx <= 65
        assert 122 <= ny <= 132

    def test_predict_demand_increase(self):
        demand, reason = _predict_demand(20.0, 10)
        assert demand == "증가"

    def test_predict_demand_decrease_cold(self):
        demand, reason = _predict_demand(2.0, 20)
        assert demand == "감소"

    def test_predict_demand_decrease_rain(self):
        demand, reason = _predict_demand(20.0, 80)
        assert demand == "감소"

    def test_predict_demand_none(self):
        demand, reason = _predict_demand(None, None)
        assert demand == "유지"


# ── 환율 수집기 테스트 ──────────────────────────────

class TestExchangeCollector:
    @pytest.fixture
    def mock_redis(self):
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.setex = AsyncMock(return_value=True)
        return redis

    @pytest.mark.asyncio
    async def test_cache_hit(self, mock_redis):
        """Redis 캐시 HIT 시 API 호출 없이 반환"""
        import json
        mock_redis.get = AsyncMock(return_value=json.dumps({"rate": 1380.0}).encode())

        collector = ExchangeCollector(redis=mock_redis)
        result = await collector.fetch(date(2025, 5, 6))

        assert result["rate"] == 1380.0
        await collector.close()

    @pytest.mark.asyncio
    async def test_api_call_on_cache_miss(self, mock_redis):
        """캐시 MISS 시 ECOS API 호출"""
        mock_response = {
            "StatisticSearch": {
                "row": [{"TIME": "20250506", "DATA_VALUE": "1375.50"}]
            }
        }

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_get.return_value = MagicMock(
                status_code=200,
                json=MagicMock(return_value=mock_response),
                raise_for_status=MagicMock(),
            )

            collector = ExchangeCollector(redis=mock_redis)
            result = await collector.fetch(date(2025, 5, 6))

            assert result["rate"] == 1375.5
            assert result["currency"] == "USD/KRW"
            await collector.close()


# ── 뉴스 수집기 테스트 ──────────────────────────────

class TestNewsCollector:
    @pytest.fixture
    def mock_redis(self):
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.setex = AsyncMock(return_value=True)
        return redis

    @pytest.mark.asyncio
    async def test_parallel_fetch(self, mock_redis):
        """3개 키워드 병렬 호출 → 중복 제거"""
        mock_items = [
            {"title": "<b>시멘트</b> 뉴스", "link": "http://a.com/1", "description": "내용", "pubDate": "2025-05-06"},
            {"title": "건설 뉴스", "link": "http://a.com/2", "description": "내용", "pubDate": "2025-05-06"},
        ]
        mock_response = {"items": mock_items}

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_get.return_value = MagicMock(
                status_code=200,
                json=MagicMock(return_value=mock_response),
                raise_for_status=MagicMock(),
            )

            collector = NewsCollector(redis=mock_redis)
            result = await collector.fetch(keywords=["시멘트", "건설"])

            assert "articles" in result
            # 중복 제거 확인 (같은 링크가 여러 키워드에서 나와도 1건만)
            links = [a["link"] for a in result["articles"]]
            assert len(links) == len(set(links))
            await collector.close()


# ── 유연탄 수집기 테스트 ─────────────────────────────

class TestCoalPriceCollector:
    def test_generate_sample(self):
        """샘플 데이터 생성 테스트"""
        collector = CoalPriceCollector()
        records = collector._generate_sample()

        assert len(records) == 24  # 2년치 (2023~2024)
        assert all(100 <= r["price_usd"] <= 220 for r in records)
        assert records[0]["year"] == 2023
        assert records[0]["month"] == 1

    def test_get_latest(self):
        """최신 월 데이터 반환 테스트"""
        collector = CoalPriceCollector()
        records = [
            {"year": 2024, "month": 11, "price_usd": 150.0},
            {"year": 2024, "month": 12, "price_usd": 160.0},
            {"year": 2023, "month": 12, "price_usd": 140.0},
        ]
        latest = collector.get_latest(records)
        assert latest["month"] == 12
        assert latest["year"] == 2024
        assert latest["price_usd"] == 160.0

    def test_calculate_krw_price(self):
        """원화 환산 테스트"""
        collector = CoalPriceCollector()
        krw = collector.calculate_krw_price(150.0, 1380.0)
        assert krw == 207000.0


# ── ERP 샘플 생성 테스트 ─────────────────────────────

class TestERPGenerate:
    def test_generate_two_years(self):
        """2년치 데이터 생성 확인"""
        from datetime import date
        records = generate_erp(
            start_date=date(2023, 1, 1),
            end_date=date(2024, 12, 31),
        )
        # 365 + 366(윤년) = 731일 × 3 제품 × 3 공장 = 6,579행
        assert len(records) == 731 * 3 * 3

    def test_seasonal_pattern(self):
        """계절성 패턴 확인 — 여름이 겨울보다 생산량 높아야 함"""
        from datetime import date
        records = generate_erp(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        )
        # 보통포틀랜드 PLANT_A 기준
        filtered = [
            r for r in records
            if r["product_type"] == "보통포틀랜드" and r["plant_code"] == "PLANT_A"
        ]
        jan_avg = sum(r["production_qty"] for r in filtered if r["log_date"].startswith("2024-01")) / 31
        jul_avg = sum(r["production_qty"] for r in filtered if r["log_date"].startswith("2024-07")) / 31
        assert jul_avg > jan_avg  # 여름 > 겨울

    def test_required_fields(self):
        """필수 필드 존재 확인"""
        from datetime import date
        records = generate_erp(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 7),
        )
        required = {"log_date", "product_type", "production_qty", "inventory_qty", "plant_code", "quality_grade"}
        for r in records:
            assert required.issubset(r.keys())
