# 🔧 소스 코드

## 폴더 구조

```
src/
├── app/          FastAPI 앱 (수집기, Agent, API, 인덱싱, Kafka 등)
├── scripts/      DB 초기화 스크립트
├── tests/        단위 테스트
└── pyproject.toml
```

## 빠른 시작

```bash
cd src
pip install -e ".[dev]"

# 인프라 먼저 기동 (infra/ 폴더에서)
cd ../infra
docker-compose up -d postgres redis qdrant elasticsearch neo4j kafka

# DB 초기화
cd ../src
python scripts/init_qdrant.py
python scripts/init_elasticsearch.py
python scripts/init_neo4j.py
python scripts/init_kafka.py

# 앱 실행
uvicorn app.main:app --reload
```

> 단계별 실행 가이드: [../docs/runbook/01_setup_verify.md](../docs/runbook/01_setup_verify.md)
