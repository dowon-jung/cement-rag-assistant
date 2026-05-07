# 🔧 소스 코드

## 폴더 구조

```
src/
├── services/          MSA 서비스 (각각 독립 배포 가능)
│   ├── collector/     수집 서비스 (환율/뉴스/날씨/유연탄/ERP)
│   ├── indexer/       인덱싱 서비스 (청킹/임베딩/Qdrant/ES/Neo4j)
│   ├── agent/         LangGraph Agent 서비스
│   ├── gateway/       FastAPI API 게이트웨이
│   └── evaluator/     RAGAS 평가 서비스
├── shared/            서비스 간 공통 코드
│   ├── config.py      환경변수
│   ├── models/        공통 Pydantic 모델
│   ├── kafka/         Kafka 공통 래퍼
│   └── db/            DB 연결 공통
├── scripts/           초기화 스크립트 (1회성)
├── tests/
│   ├── unit/          서비스별 단위 테스트
│   └── integration/   서비스 간 통합 테스트
└── pyproject.toml
```

> 폴더 구조 설계 의도: [../docs/design/00_folder_structure.md](../docs/design/00_folder_structure.md)

## 빠른 시작

```bash
cd src
pip install -e ".[dev]"

# 인프라 기동
cd ../infra && docker-compose up -d

# DB 초기화
cd ../src
python scripts/init_qdrant.py
python scripts/init_elasticsearch.py
python scripts/init_neo4j.py
python scripts/init_kafka.py

# 게이트웨이 실행
uvicorn services.gateway.main:app --reload
```
