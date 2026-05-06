# 05. 환경 설정 가이드

## 1. 필요한 API 키

| API | 발급 URL | 용도 | 비고 |
|-----|---------|------|------|
| 한국은행 ECOS | [ecos.bok.or.kr](https://ecos.bok.or.kr/api/#/DevGuide/TopPage) | 환율 조회 | 무료 |
| 네이버 검색 | [developers.naver.com](https://developers.naver.com/apps/#/register) | 뉴스 수집 | 무료, Client ID/Secret |
| 기상청 Open API | [data.go.kr](https://data.go.kr) | 단기예보 | 무료, 단기예보 검색 |
| Anthropic API | [console.anthropic.com](https://console.anthropic.com) | Claude 사용 시 | 선택, 유료 |
| AWS Bedrock | [aws.amazon.com/bedrock](https://aws.amazon.com/bedrock) | Bedrock 사용 시 | 선택, 유료 |
| LangSmith | [smith.langchain.com](https://smith.langchain.com) | 트레이싱 | 선택, 무료 티어 |

---

## 2. .env.example

```bash
# === 외부 API 키 ===
BOK_API_KEY=your_ecos_api_key
NAVER_CLIENT_ID=your_naver_client_id
NAVER_CLIENT_SECRET=your_naver_client_secret
WEATHER_API_KEY=your_weather_api_key

# === LLM 백엔드 선택 ===
# local | bedrock | anthropic
LLM_BACKEND=local

# Anthropic API (LLM_BACKEND=anthropic 시 필요)
ANTHROPIC_API_KEY=sk-ant-xxxxx

# AWS Bedrock (LLM_BACKEND=bedrock 시 필요)
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0

# Ollama (LLM_BACKEND=local 시)
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=gemma2:9b

# === 에어갭 모드 ===
AIRGAP_MODE=false

# === 데이터베이스 ===
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=cement_rag
POSTGRES_USER=cement
POSTGRES_PASSWORD=cement_pass

REDIS_HOST=localhost
REDIS_PORT=6379

QDRANT_HOST=localhost
QDRANT_PORT=6333

NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=neo4j_pass

# === Kafka ===
KAFKA_BOOTSTRAP_SERVERS=localhost:9092

# === 모델 경로 (에어갭 시) ===
EMBEDDING_MODEL_PATH=./models/ko-sroberta
RERANKER_MODEL_PATH=./models/reranker

# === 모니터링 ===
LANGSMITH_TRACING=false
LANGSMITH_API_KEY=
LANGSMITH_PROJECT=cement-rag

JAEGER_ENDPOINT=http://localhost:14268/api/traces

# === 앱 설정 ===
APP_HOST=0.0.0.0
APP_PORT=8000
LOG_LEVEL=INFO
```

---

## 3. Docker Compose 서비스 구성

```yaml
# docker-compose.yml
services:
  postgres:
    image: postgres:16
    ports: ["5432:5432"]
    environment:
      POSTGRES_DB: cement_rag
      POSTGRES_USER: cement
      POSTGRES_PASSWORD: cement_pass
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./scripts/init_db.sql:/docker-entrypoint-initdb.d/init.sql

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    volumes:
      - redis_data:/data

  qdrant:
    image: qdrant/qdrant:latest
    ports: ["6333:6333"]
    volumes:
      - qdrant_data:/qdrant/storage

  neo4j:
    image: neo4j:5-community
    ports: ["7474:7474", "7687:7687"]
    environment:
      NEO4J_AUTH: neo4j/neo4j_pass
    volumes:
      - neo4j_data:/data

  kafka:
    image: confluentinc/cp-kafka:7.5.0
    ports: ["9092:9092"]
    environment:
      KAFKA_NODE_ID: 1
      KAFKA_PROCESS_ROLES: broker,controller
      KAFKA_LISTENERS: PLAINTEXT://:9092,CONTROLLER://:9093
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://localhost:9092
      KAFKA_CONTROLLER_LISTENER_NAMES: CONTROLLER
      KAFKA_CONTROLLER_QUORUM_VOTERS: 1@kafka:9093
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: PLAINTEXT:PLAINTEXT,CONTROLLER:PLAINTEXT
      CLUSTER_ID: cement-rag-cluster

  ollama:
    image: ollama/ollama:latest
    ports: ["11434:11434"]
    volumes:
      - ollama_data:/root/.ollama

  prometheus:
    image: prom/prometheus:latest
    ports: ["9090:9090"]
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml

  grafana:
    image: grafana/grafana:latest
    ports: ["3000:3000"]
    environment:
      GF_SECURITY_ADMIN_PASSWORD: admin

  jaeger:
    image: jaegertracing/all-in-one:latest
    ports:
      - "16686:16686"   # UI
      - "14268:14268"   # HTTP collector

  app:
    build: .
    ports: ["8000:8000"]
    env_file: .env
    depends_on: [postgres, redis, qdrant, neo4j, kafka]

volumes:
  postgres_data:
  redis_data:
  qdrant_data:
  neo4j_data:
  ollama_data:
```

---

## 4. 초기 설정 절차

```bash
# 1. 레포 클론 및 환경 변수 설정
git clone https://github.com/dowon-jung/cement-rag-assistant.git
cd cement-rag-assistant
cp .env.example .env
# .env에 API 키 입력

# 2. Docker Compose 기동
docker-compose up -d

# 3. 헬스체크
docker-compose ps
# 모든 서비스 healthy 확인

# 4. DB 초기화
psql -h localhost -U cement -d cement_rag -f scripts/init_db.sql
python scripts/init_qdrant.py
python scripts/init_neo4j.py
python scripts/init_kafka.py

# 5. Python 패키지 설치
pip install -e ".[dev]"

# 6. (선택) Ollama 모델 다운로드
docker exec -it ollama ollama pull gemma2:9b

# 7. 인덱싱 파이프라인 실행
python -m app.indexing.pipeline --source all

# 8. FastAPI 서버 실행
uvicorn app.main:app --reload

# 9. (선택) Streamlit 데모
streamlit run streamlit_app.py
```

---

## 5. 포트 할당

| 서비스 | 포트 | 용도 |
|--------|------|------|
| FastAPI | 8000 | API 서버 |
| Streamlit | 8501 | 데모 UI |
| PostgreSQL | 5432 | DB |
| Redis | 6379 | 캐시 |
| Qdrant | 6333 | Vector DB (HTTP), 6334 (gRPC) |
| Neo4j | 7474, 7687 | UI, Bolt |
| Kafka | 9092 | Broker |
| Ollama | 11434 | LLM 서빙 |
| Prometheus | 9090 | 메트릭 |
| Grafana | 3000 | 대시보드 |
| Jaeger | 16686 | 트레이스 UI |

---

## 6. 의존 패키지 (pyproject.toml)

```toml
[project]
name = "cement-rag-assistant"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    # Web
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "pydantic>=2.9.0",
    "pydantic-settings>=2.5.0",
    "httpx>=0.27.0",
    "slowapi>=0.1.9",
    
    # LangChain ecosystem
    "langchain>=0.3.0",
    "langgraph>=0.2.0",
    "langsmith>=0.1.0",
    
    # Vector / Graph DB
    "qdrant-client>=1.12.0",
    "neo4j>=5.25.0",
    
    # SQL / Cache
    "sqlalchemy>=2.0.0",
    "asyncpg>=0.29.0",
    "redis>=5.0.0",
    
    # Kafka
    "aiokafka>=0.11.0",
    
    # Embedding / Re-ranker
    "sentence-transformers>=3.0.0",
    "torch>=2.4.0",
    
    # PDF / Document
    "pymupdf>=1.24.0",
    "pandas>=2.2.0",
    
    # LLM Backends
    "ollama>=0.3.0",
    "anthropic>=0.34.0",
    "boto3>=1.35.0",
    
    # Evaluation
    "ragas>=0.2.0",
    
    # Monitoring
    "prometheus-client>=0.21.0",
    "opentelemetry-api>=1.27.0",
    "opentelemetry-sdk>=1.27.0",
    "opentelemetry-exporter-jaeger>=1.21.0",
    
    # UI
    "streamlit>=1.39.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-asyncio>=0.24.0",
    "ruff>=0.6.0",
    "mypy>=1.11.0",
]
```

---

## 7. 문제 해결

### Kafka 연결 실패
```bash
# 컨테이너 로그 확인
docker logs cement-rag-kafka-1

# Topic 확인
docker exec -it cement-rag-kafka-1 \
  kafka-topics --list --bootstrap-server localhost:9092
```

### Qdrant 컬렉션 미생성
```bash
python scripts/init_qdrant.py
curl http://localhost:6333/collections
```

### Ollama 모델 미다운로드
```bash
docker exec -it ollama ollama list
docker exec -it ollama ollama pull gemma2:9b
```
