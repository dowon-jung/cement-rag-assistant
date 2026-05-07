"""
ERP 생산·재고 샘플 데이터 생성기

2년치 일별 데이터 생성 (현실적인 시멘트 생산 패턴 반영):
- 제품 유형: 보통포틀랜드, 고로슬래그, 백색시멘트
- 공장 코드: PLANT_A, PLANT_B, PLANT_C
- 계절성 반영 (여름 성수기, 겨울 비수기)
- 주말 생산량 감소

실행: python app/data/samples/generate_erp.py
"""

import csv
import logging
import math
import random
from datetime import date, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

# 출력 경로
OUTPUT_CSV = Path(__file__).parent / "erp_production_sample.csv"

# 제품 유형별 기본 일일 생산량 (톤)
BASE_QTY = {
    "보통포틀랜드": 800.0,
    "고로슬래그":   400.0,
    "백색시멘트":   120.0,
}

# 공장별 생산 능력 배율
PLANT_SCALE = {
    "PLANT_A": 1.0,
    "PLANT_B": 0.8,
    "PLANT_C": 0.6,
}

# 품질 등급
QUALITY_GRADES = ["A", "A", "A", "B", "B", "C"]  # A 등급이 가장 흔함


def _seasonal_factor(d: date) -> float:
    """계절성 반영: 봄·가을 성수기, 겨울 비수기"""
    day_of_year = d.timetuple().tm_yday
    # 사인 곡선으로 계절 변동 표현 (연중 최고: 4월 말, 최저: 1월)
    factor = 1.0 + 0.25 * math.sin(2 * math.pi * (day_of_year - 90) / 365)
    return round(factor, 3)


def _weekend_factor(d: date) -> float:
    """주말 생산량 감소"""
    return 0.6 if d.weekday() >= 5 else 1.0


def generate(start_date: date | None = None, end_date: date | None = None) -> list[dict]:
    """2년치 샘플 데이터 생성"""
    random.seed(42)

    if start_date is None:
        start_date = date(2023, 1, 1)
    if end_date is None:
        end_date = date(2024, 12, 31)

    records = []
    inventory: dict[tuple, float] = {}  # (product, plant) → 재고량

    current = start_date
    while current <= end_date:
        for product, base_qty in BASE_QTY.items():
            for plant, scale in PLANT_SCALE.items():
                key = (product, plant)

                # 생산량 계산
                seasonal = _seasonal_factor(current)
                weekend = _weekend_factor(current)
                noise = random.uniform(0.85, 1.15)
                qty = round(base_qty * scale * seasonal * weekend * noise, 1)

                # 재고량 계산 (누적 - 출하)
                prev_inv = inventory.get(key, base_qty * scale * 30)  # 초기 재고 30일치
                shipment = qty * random.uniform(0.8, 1.1)
                inv = max(0.0, prev_inv + qty - shipment)
                inventory[key] = inv

                records.append({
                    "log_date": current.isoformat(),
                    "product_type": product,
                    "production_qty": qty,
                    "inventory_qty": round(inv, 1),
                    "plant_code": plant,
                    "quality_grade": random.choice(QUALITY_GRADES),
                })

        current += timedelta(days=1)

    logger.info(f"ERP 샘플 데이터 생성 완료: {len(records)}건 ({start_date} ~ {end_date})")
    return records


def save_csv(records: list[dict], output_path: Path = OUTPUT_CSV) -> None:
    """CSV 파일로 저장"""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "log_date", "product_type", "production_qty",
        "inventory_qty", "plant_code", "quality_grade",
    ]

    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)

    logger.info(f"CSV 저장 완료: {output_path} ({len(records)}행)")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    records = generate()
    save_csv(records)

    # 간단한 통계 출력
    from collections import defaultdict
    by_plant: dict = defaultdict(float)
    by_product: dict = defaultdict(float)
    for r in records:
        by_plant[r["plant_code"]] += r["production_qty"]
        by_product[r["product_type"]] += r["production_qty"]

    print("\n=== 공장별 총 생산량 (2년) ===")
    for plant, qty in sorted(by_plant.items()):
        print(f"  {plant}: {qty:,.0f} 톤")

    print("\n=== 제품별 총 생산량 (2년) ===")
    for product, qty in sorted(by_product.items()):
        print(f"  {product}: {qty:,.0f} 톤")
