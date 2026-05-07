"""
Qdrant 컬렉션 초기화 스크립트
실행: python scripts/init_qdrant.py
"""

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.core.config import settings

COLLECTIONS = [
    {
        "name": "regulations",
        "description": "환경부 규제 문서",
    },
    {
        "name": "coal_prices",
        "description": "유연탄 가격 통계",
    },
    {
        "name": "manuals",
        "description": "생산 매뉴얼",
    },
    {
        "name": "quality_standards",
        "description": "품질검사 기준서",
    },
]

VECTOR_SIZE = 768  # ko-sroberta-multitask 출력 차원


def init_qdrant():
    client = QdrantClient(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
    )

    existing = {c.name for c in client.get_collections().collections}

    for col in COLLECTIONS:
        if col["name"] in existing:
            print(f"  [SKIP] 이미 존재함: {col['name']}")
            continue

        client.create_collection(
            collection_name=col["name"],
            vectors_config=VectorParams(
                size=VECTOR_SIZE,
                distance=Distance.COSINE,
            ),
        )
        print(f"  [OK] 생성 완료: {col['name']} — {col['description']}")

    print("\nQdrant 초기화 완료")
    print(f"총 컬렉션: {len(client.get_collections().collections)}개")


if __name__ == "__main__":
    print("Qdrant 컬렉션 초기화 중...")
    init_qdrant()
