"""
Neo4j 제약조건 및 인덱스 초기화 스크립트
실행: python scripts/init_neo4j.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from neo4j import GraphDatabase
from app.core.config import settings

CONSTRAINTS = [
    # 법령 코드 유일성
    "CREATE CONSTRAINT law_code IF NOT EXISTS FOR (l:Law) REQUIRE l.code IS UNIQUE",
    # 조항 복합 유일성
    "CREATE CONSTRAINT article_unique IF NOT EXISTS FOR (a:Article) REQUIRE (a.law_code, a.number) IS UNIQUE",
]

INDEXES = [
    # 오염물질 이름 인덱스 (검색 빈번)
    "CREATE INDEX pollutant_name IF NOT EXISTS FOR (p:Pollutant) ON (p.name)",
    # 시설 유형 인덱스
    "CREATE INDEX facility_type IF NOT EXISTS FOR (f:Facility) ON (f.type)",
    # 수치기준 유형 인덱스
    "CREATE INDEX standard_type IF NOT EXISTS FOR (s:Standard) ON (s.type)",
]


def init_neo4j():
    driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
    )

    with driver.session() as session:
        print("제약조건 생성 중...")
        for constraint in CONSTRAINTS:
            try:
                session.run(constraint)
                name = constraint.split("CONSTRAINT ")[1].split(" IF")[0]
                print(f"  [OK] {name}")
            except Exception as e:
                print(f"  [WARN] {e}")

        print("\n인덱스 생성 중...")
        for index in INDEXES:
            try:
                session.run(index)
                name = index.split("INDEX ")[1].split(" IF")[0]
                print(f"  [OK] {name}")
            except Exception as e:
                print(f"  [WARN] {e}")

    driver.close()
    print("\nNeo4j 초기화 완료")


if __name__ == "__main__":
    print("Neo4j 초기화 중...")
    init_neo4j()
