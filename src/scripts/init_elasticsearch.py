"""
Elasticsearch 인덱스 초기화 스크립트 (nori 형태소 분석기)
실행: python scripts/init_elasticsearch.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from elasticsearch import Elasticsearch
from shared.config import settings

# nori 분석기 공통 설정
SETTINGS = {
    "analysis": {
        "analyzer": {
            "korean": {
                "type": "custom",
                "tokenizer": "nori_tokenizer",
                "filter": ["nori_part_of_speech", "lowercase"],
            }
        }
    }
}

# 인덱스별 매핑 정의
INDICES = {
    "regulations": {
        "settings": SETTINGS,
        "mappings": {
            "properties": {
                "text":        {"type": "text", "analyzer": "korean"},
                "law_name":    {"type": "keyword"},
                "article":     {"type": "keyword"},
                "page":        {"type": "integer"},
                "chunk_index": {"type": "integer"},
                "updated_at":  {"type": "date"},
            }
        },
    },
    "coal_prices": {
        "settings": SETTINGS,
        "mappings": {
            "properties": {
                "text":         {"type": "text", "analyzer": "korean"},
                "source":       {"type": "keyword"},
                "year":         {"type": "integer"},
                "month":        {"type": "integer"},
                "price_usd":    {"type": "float"},
                "chunk_index":  {"type": "integer"},
            }
        },
    },
    "manuals": {
        "settings": SETTINGS,
        "mappings": {
            "properties": {
                "text":         {"type": "text", "analyzer": "korean"},
                "source":       {"type": "keyword"},
                "section":      {"type": "keyword"},
                "page":         {"type": "integer"},
                "chunk_index":  {"type": "integer"},
                "product_type": {"type": "keyword"},
            }
        },
    },
    "quality_standards": {
        "settings": SETTINGS,
        "mappings": {
            "properties": {
                "text":         {"type": "text", "analyzer": "korean"},
                "source":       {"type": "keyword"},
                "ks_code":      {"type": "keyword"},
                "page":         {"type": "integer"},
                "chunk_index":  {"type": "integer"},
            }
        },
    },
}


def check_nori_plugin(es: Elasticsearch) -> bool:
    """nori 플러그인 설치 여부 확인"""
    try:
        plugins = es.cat.plugins(format="json")
        for p in plugins:
            if "analysis-nori" in p.get("component", ""):
                return True
        return False
    except Exception:
        return False


def init_elasticsearch():
    es = Elasticsearch(settings.elasticsearch_host)

    if not es.ping():
        print("Elasticsearch 연결 실패. 서버 상태를 확인해주세요.")
        sys.exit(1)

    # nori 플러그인 확인
    if check_nori_plugin(es):
        print("  [OK] nori 플러그인 확인됨")
    else:
        print("  [WARNING] nori 플러그인이 감지되지 않았습니다.")
        print("  에어갭 환경: initContainer로 사전 반입 필요 (docs/14_airgap.md 6장 참고)")
        print("  로컬 환경: docker exec elasticsearch bin/elasticsearch-plugin install analysis-nori")
        print("  → 계속 진행합니다 (인덱스 생성 후 nori 설치 필요)")

    # 인덱스 생성
    for index_name, body in INDICES.items():
        if es.indices.exists(index=index_name):
            print(f"  [SKIP] 이미 존재함: {index_name}")
            continue

        es.indices.create(index=index_name, body=body)
        print(f"  [OK] 생성 완료: {index_name}")

    print("\nElasticsearch 초기화 완료")


if __name__ == "__main__":
    print("Elasticsearch 인덱스 초기화 중...")
    init_elasticsearch()
