# 01. 환경 세팅 및 수집기 동작 확인

> **대상 Phase**: Phase 1 (프로젝트 뼈대) + Phase 2 (데이터 수집 레이어)
> **API 키 필요 여부**: Step 1~5는 불필요 / Step 6은 필요

---

## 전체 체크리스트

```
Step 1  Docker Compose 기동             [ ]
Step 2  DB 초기화 스크립트              [ ]
Step 3  ERP 샘플 데이터 생성            [ ]
Step 4  FastAPI 서버 기동               [ ]
Step 5  단위 테스트 (mock)              [ ]
Step 6  실제 API 수집기 동작 확인       [ ]  ← API 키 필요
```

---

## Step 1 — Docker Compose 기동

### 실행

```bash
# 앱 서버 제외하고 인프라만 먼저 기동
docker-compose up -d postgres redis qdrant elasticsearch neo4j kafka
```

### 확인 방법

```bash
docker-compose ps
```

### 성공 기준

모든 서비스가 `healthy` 상태여야 합니다.

```
NAME                    STATUS
cement-postgres         Up (healthy)
cement-redis            Up (healthy)
cement-qdrant           Up (healthy)
cement-elasticsearch    Up (healthy)
cement-neo4j            Up (healthy)
cement-kafka            Up (healthy)
```

### 자주 발생하는 문제

**Elasticsearch가 계속 starting...**
```bash
# JVM 메모리 부족 — .env 또는 docker-compose.yml에서 힙 크기 축소
# ES_JAVA_OPTS=-Xms1g -Xmx1g 으로 변경 후 재시작
docker-compose restart elasticsearch
```

**Kafka가 healthy가 안 됨**
```bash
# 로그 확인
docker logs cement-kafka --tail 30

# CLUSTER_ID 중복 오류 시 볼륨 초기화
docker-compose down -v
docker-compose up -d kafka
```

**Neo4j 포트 충돌 (7474)**
```bash
# 다른 프로세스 확인
lsof -i :7474
# docker-compose.yml에서 포트 변경 후 재시작
```

---

## Step 2 — DB 초기화 스크립트

### 실행 순서

```bash
# 1. PostgreSQL
psql -h localhost -U cement -d cement_rag -f scripts/init_db.sql
# 비밀번호: cement_pass

# 2. Qdrant 컬렉션 생성
python scripts/init_qdrant.py

# 3. Elasticsearch 인덱스 생성 (nori 플러그인 확인 포함)
python scripts/init_elasticsearch.py

# 4. Neo4j 제약조건 및 인덱스
python scripts/init_neo4j.py

# 5. Kafka 토픽 생성
python scripts/init_kafka.py
```

### 확인 방법

**PostgreSQL 테이블 확인**
```bash
psql -h localhost -U cement -d cement_rag -c "\dt"
```

예상 출력:
```
 Schema |      Name       | Type  | Owner
--------+-----------------+-------+--------
 public | coal_prices     | table | cement
 public | market_rates    | table | cement
 public | news_cache      | table | cement
 public | production_logs | table | cement
 public | weather_cache   | table | cement
```

**Qdrant 컬렉션 확인**
```bash
curl http://localhost:6333/collections
```

예상 출력:
```json
{
  "result": {
    "collections": [
      {"name": "regulations"},
      {"name": "coal_prices"},
      {"name": "manuals"},
      {"name": "quality_standards"}
    ]
  }
}
```

**Elasticsearch 인덱스 확인**
```bash
curl http://localhost:9200/_cat/indices?v
```

예상 출력:
```
health status index              ...
green  open   regulations        ...
green  open   coal_prices        ...
green  open   manuals            ...
green  open   quality_standards  ...
```

**nori 플러그인 확인**
```bash
curl http://localhost:9200/_cat/plugins?v
```

예상 출력:
```
name    component       version
...     analysis-nori   8.13.0
```

> nori가 없으면 아래 명령으로 설치 후 ES 재시작
> ```bash
> docker exec cement-elasticsearch \
>   bin/elasticsearch-plugin install --batch analysis-nori
> docker-compose restart elasticsearch
> ```

**Neo4j 제약조건 확인**
```bash
# Neo4j 브라우저: http://localhost:7474
# 접속 후 아래 쿼리 실행
SHOW CONSTRAINTS
```

**Kafka 토픽 확인**
```bash
docker exec cement-kafka \
  kafka-topics --list --bootstrap-server localhost:9092
```

예상 출력:
```
dlq.errors
erp.updated
indexing.requests
indexing.results
llm.requests
llm.results
market.raw
news.raw
weather.raw
```

### 성공 기준

- PostgreSQL 테이블 5개 생성됨
- Qdrant 컬렉션 4개 생성됨
- Elasticsearch 인덱스 4개 생성됨
- Kafka 토픽 9개 생성됨

---

## Step 3 — ERP 샘플 데이터 생성

### 실행

```bash
python app/data/samples/generate_erp.py
```

### 예상 출력

```
ERP 샘플 데이터 생성 완료: 6579건 (2023-01-01 ~ 2024-12-31)
CSV 저장 완료: app/data/samples/erp_production_sample.csv (6579행)

=== 공장별 총 생산량 (2년) ===
  PLANT_A: 584,320 톤
  PLANT_B: 467,456 톤
  PLANT_C: 350,592 톤

=== 제품별 총 생산량 (2년) ===
  고로슬래그:   467,456 톤
  백색시멘트:   140,237 톤
  보통포틀랜드: 794,675 톤
```

### 확인 방법

```bash
# CSV 파일 생성 확인
ls -lh app/data/samples/erp_production_sample.csv

# 첫 5행 확인
head -5 app/data/samples/erp_production_sample.csv
```

### 성공 기준

- `app/data/samples/erp_production_sample.csv` 생성됨
- 행 수 약 6,579개 (731일 × 3제품 × 3공장)
- 생산량이 계절성 패턴 반영 (여름 > 겨울)

---

## Step 4 — FastAPI 서버 기동

### 실행

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 확인 방법

**헬스체크**
```bash
curl http://localhost:8000/health
```

예상 응답:
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "llm_backend": "local",
  "airgap_mode": false
}
```

**Swagger UI 접속**
```
http://localhost:8000/docs
```

**Prometheus 메트릭 확인**
```bash
curl http://localhost:8000/metrics | head -20
```

### 성공 기준

- `/health` 엔드포인트 200 응답
- Swagger UI 정상 렌더링
- `/metrics` 엔드포인트 접근 가능

---

## Step 5 — 단위 테스트 실행 (mock 기반, API 키 불필요)

### 실행

```bash
pytest tests/test_collectors.py -v
```

### 예상 출력

```
tests/test_collectors.py::TestUtils::test_strip_html PASSED
tests/test_collectors.py::TestUtils::test_latlon_to_grid_seoul PASSED
tests/test_collectors.py::TestUtils::test_predict_demand_increase PASSED
tests/test_collectors.py::TestUtils::test_predict_demand_decrease_cold PASSED
tests/test_collectors.py::TestUtils::test_predict_demand_decrease_rain PASSED
tests/test_collectors.py::TestUtils::test_predict_demand_none PASSED
tests/test_collectors.py::TestExchangeCollector::test_cache_hit PASSED
tests/test_collectors.py::TestExchangeCollector::test_api_call_on_cache_miss PASSED
tests/test_collectors.py::TestNewsCollector::test_parallel_fetch PASSED
tests/test_collectors.py::TestCoalPriceCollector::test_generate_sample PASSED
tests/test_collectors.py::TestCoalPriceCollector::test_get_latest PASSED
tests/test_collectors.py::TestCoalPriceCollector::test_calculate_krw_price PASSED
tests/test_collectors.py::TestERPGenerate::test_generate_two_years PASSED
tests/test_collectors.py::TestERPGenerate::test_seasonal_pattern PASSED
tests/test_collectors.py::TestERPGenerate::test_required_fields PASSED

15 passed in X.XXs
```

### 성공 기준

- 15개 테스트 전부 PASSED
- FAILED 0개

### 자주 발생하는 문제

**ModuleNotFoundError: app**
```bash
# 프로젝트 루트에서 실행했는지 확인
cd cement-rag-assistant
pip install -e ".[dev]"
pytest tests/test_collectors.py -v
```

---

## Step 6 — 실제 API 수집기 동작 확인 (API 키 필요)

> API 키 발급 방법은 [docs/05_env_setup.md](../../docs/design/05_env_setup.md) 참고

### 6-1. 환율 수집기 확인

```bash
python -c "
import asyncio
from redis.asyncio import Redis
from app.data.collectors.exchange_api import ExchangeCollector

async def test():
    redis = Redis.from_url('redis://localhost:6379')
    collector = ExchangeCollector(redis=redis)
    result = await collector.fetch()
    print('환율:', result)
    await collector.close()
    await redis.aclose()

asyncio.run(test())
"
```

예상 출력:
```
환율: {'currency': 'USD/KRW', 'rate': 1380.5, 'base_date': '20250507', ...}
```

### 6-2. 뉴스 수집기 확인

```bash
python -c "
import asyncio
from redis.asyncio import Redis
from app.data.collectors.news_api import NewsCollector

async def test():
    redis = Redis.from_url('redis://localhost:6379')
    collector = NewsCollector(redis=redis)
    result = await collector.fetch(keywords=['시멘트'])
    print(f'뉴스 {result[\"total\"]}건 수집')
    for a in result['articles'][:3]:
        print(' -', a['title'])
    await collector.close()
    await redis.aclose()

asyncio.run(test())
"
```

### 6-3. 날씨 수집기 확인

```bash
python -c "
import asyncio
from redis.asyncio import Redis
from app.data.collectors.weather_api import WeatherCollector

async def test():
    redis = Redis.from_url('redis://localhost:6379')
    collector = WeatherCollector(redis=redis)
    result = await collector.fetch()
    print('날씨:', result)
    await collector.close()
    await redis.aclose()

asyncio.run(test())
"
```

### 성공 기준

| 수집기 | 성공 기준 |
|--------|-----------|
| 환율 | `rate` 필드에 숫자 값 반환 |
| 뉴스 | `articles` 배열에 1개 이상 항목 |
| 날씨 | `tmp`, `pop` 필드에 값 반환 |

---

## 전체 완료 후 상태

Step 1~6 모두 완료 시 아래 상태가 됩니다.

```
✅ Docker 인프라 6개 서비스 실행 중
✅ PostgreSQL 테이블 5개 + Materialized View 생성
✅ Qdrant 컬렉션 4개 생성
✅ Elasticsearch 인덱스 4개 생성 (nori 분석기)
✅ Neo4j 제약조건 및 인덱스 생성
✅ Kafka 토픽 9개 생성
✅ ERP 샘플 데이터 6,579건 생성
✅ FastAPI 서버 /health 응답
✅ 단위 테스트 15개 통과
✅ 실제 API 수집기 동작 확인
```

다음 단계: [Phase 3 — Kafka 이벤트 파이프라인](../../docs/TASK.md)
