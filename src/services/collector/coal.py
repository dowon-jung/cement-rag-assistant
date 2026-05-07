"""
유연탄 가격 CSV 수집기

원본: 한국자원정보서비스 (kores.net) 월별 가격 CSV
컬럼: 연도, 월, 가격($/톤), 전월비(%), 전년비(%)
"""

import logging
from pathlib import Path

import pandas as pd

from shared.config import settings

logger = logging.getLogger(__name__)

# 샘플 데이터 경로 (실제 파일 없을 경우 사용)
SAMPLE_CSV_PATH = Path(__file__).parent.parent / "samples" / "coal_prices_sample.csv"


class CoalPriceCollector:
    def load_csv(self, file_path: str | Path | None = None) -> list[dict]:
        """
        유연탄 가격 CSV 로드 후 파싱.
        file_path 미지정 시 샘플 데이터 사용.
        """
        path = Path(file_path) if file_path else SAMPLE_CSV_PATH

        if not path.exists():
            logger.warning(f"CSV 파일 없음: {path} → 샘플 데이터 생성")
            return self._generate_sample()

        df = pd.read_csv(path, encoding="utf-8-sig")
        df.columns = df.columns.str.strip()

        records = []
        for _, row in df.iterrows():
            try:
                records.append({
                    "year": int(row.get("연도", row.get("year", 0))),
                    "month": int(row.get("월", row.get("month", 0))),
                    "price_usd": float(row.get("가격($/톤)", row.get("price_usd", 0))),
                    "mom_pct": float(row.get("전월비(%)", row.get("mom_pct", 0)) or 0),
                    "yoy_pct": float(row.get("전년비(%)", row.get("yoy_pct", 0)) or 0),
                    "source": str(path.name),
                })
            except (ValueError, TypeError) as e:
                logger.warning(f"행 파싱 실패: {e}")
                continue

        logger.info(f"유연탄 가격 로드 완료: {len(records)}건")
        return records

    def _generate_sample(self) -> list[dict]:
        """
        샘플 데이터 생성 (2023-01 ~ 2024-12).
        실제 유연탄 가격 범위(100~200 USD/톤)를 반영.
        """
        import random
        random.seed(42)

        records = []
        price = 160.0  # 시작 가격
        for year in [2023, 2024]:
            for month in range(1, 13):
                change = random.uniform(-8, 8)
                price = max(100.0, min(220.0, price + change))
                prev = records[-1]["price_usd"] if records else price
                records.append({
                    "year": year,
                    "month": month,
                    "price_usd": round(price, 2),
                    "mom_pct": round((price - prev) / prev * 100, 2) if prev else 0,
                    "yoy_pct": 0.0,
                    "source": "sample",
                })

        # 전년비 계산
        for i, rec in enumerate(records):
            if i >= 12:
                prev_year = records[i - 12]["price_usd"]
                rec["yoy_pct"] = round((rec["price_usd"] - prev_year) / prev_year * 100, 2)

        # 샘플 CSV 저장
        SAMPLE_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
        df = pd.DataFrame(records)
        df.to_csv(SAMPLE_CSV_PATH, index=False, encoding="utf-8-sig")
        logger.info(f"샘플 CSV 생성 완료: {SAMPLE_CSV_PATH}")

        return records

    def get_latest(self, records: list[dict]) -> dict | None:
        """가장 최근 월 가격 반환"""
        if not records:
            return None
        return max(records, key=lambda r: (r["year"], r["month"]))

    def calculate_krw_price(self, price_usd: float, usd_krw_rate: float) -> float:
        """달러 유연탄 가격 → 원화 환산 ($/톤 → 원/톤)"""
        return round(price_usd * usd_krw_rate, 0)
