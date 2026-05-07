# 08. 성능 최적화 설계

## 1. 성능 목표

| 항목 | 목표 |
|------|------|
| 단순 질의 응답 시간 | p95 < 1.5s |
| 복합 질의 응답 시간 | p95 < 4s |
| TTFT (스트리밍) | < 500ms |
| 동시 요청 처리 | 50 RPS 안정 처리 |
| API 캐시 hit rate | > 60% |

---

## 2. 비동기 처리 설계

### 외부 API 호출 — asyncio.gather 병렬화

**Before (순차)**
```python
# 3초 + 2초 + 1초 = 6초
exchange = await fetch_exchange()
news = await fetch_news()
weather = await fetch_weather()
```

**After (병렬)**
```python
# max(3, 2, 1) = 3초
exchange, news, weather = await asyncio.gather(
    fetch_exchange(),
    fetch_news(),
    fetch_weather(),
)
```

### 적용 대상

| 위치 | 효과 |
|------|------|
| 네이버 뉴스 키워드 3개 호출 | 3x 단축 |
| Market Agent 내부 (환율 + 유연탄 + 날씨) | 2~3x 단축 |
| Hybrid Search (Vector + Elasticsearch BM25) | 2x 단축 |

---

## 3. LangGraph Send API — 병렬 Sub-Agent 실행

### 순차 실행의 한계
```python
# 복합 질의 — 순차 처리 시
market_result = await market_agent(query)      # 2.0s
news_result = await news_agent(query)          # 1.5s
rag_result = await rag_agent(query)            # 2.5s
# 총 6초
```

### Send API 병렬 실행
```python
def route_to_sub_agents(state: AgentState):
    return [
        Send(agent_name, {"query": state["query"]})
        for agent_name in state["sub_agents_to_call"]
    ]

graph.add_conditional_edges(
    "orchestrator",
    route_to_sub_agents,
    ["market_agent", "news_agent", "rag_agent"]
)
# max(2.0, 1.5, 2.5) = 2.5초
# 60% 단축
```

### 측정 계획

| 시나리오 | 순차 | 병렬 | 단축률 |
|----------|------|------|--------|
| 2개 Agent 호출 | 측정 예정 | 측정 예정 | - |
| 3개 Agent 호출 | 측정 예정 | 측정 예정 | - |
| 4개 Agent 호출 | 측정 예정 | 측정 예정 | - |

결과는 `docs/eval_results/parallel_perf.md`에 기록.

---

## 4. 캐싱 전략

### 다층 캐시 구조

```
요청
  │
  ▼
[L1: 응답 캐시] Redis (5분 TTL)
  └─ 동일 질의 재요청 시 즉시 반환
  │
  ▼ MISS
[L2: API 캐시] Redis (30m~1h TTL)
  └─ 외부 API 응답 캐싱 (환율, 뉴스, 날씨)
  │
  ▼ MISS
[L3: 임베딩 캐시] Redis (24h TTL)
  └─ 동일 텍스트 재임베딩 방지
  │
  ▼ MISS
[L4: 검색 결과 캐시] Redis (5분 TTL)
  └─ 동일 검색 쿼리 재실행 방지
```

### Redis 키 설계

| 레이어 | 키 패턴 | TTL |
|--------|---------|-----|
| L1 | `response:{hash(query)}` | 300s |
| L2 | `api:{source}:{params}` | 1800~3600s |
| L3 | `embed:{hash(text)}` | 86400s |
| L4 | `search:{collection}:{hash(query)}` | 300s |

### 캐시 무효화 전략
- 유연탄 가격 갱신 시 → `coal_prices` 관련 캐시 전부 삭제
- 규제 문서 재인덱싱 시 → `regulations` 관련 캐시 전부 삭제

---

## 5. DB 최적화

### PostgreSQL
```sql
-- 자주 조회되는 인덱스
CREATE INDEX CONCURRENTLY idx_production_logs_date_plant
  ON production_logs (log_date DESC, plant_code);

-- 부분 인덱스 (최근 90일만)
CREATE INDEX idx_production_recent
  ON production_logs (log_date DESC)
  WHERE log_date >= CURRENT_DATE - INTERVAL '90 days';

-- 집계 쿼리 자주 실행 시 Materialized View
CREATE MATERIALIZED VIEW monthly_production AS
SELECT 
    DATE_TRUNC('month', log_date) AS month,
    product_type,
    SUM(production_qty) AS total_qty
FROM production_logs
GROUP BY 1, 2;

-- 일 1회 갱신
REFRESH MATERIALIZED VIEW CONCURRENTLY monthly_production;
```

### Qdrant
```python
# HNSW 인덱스 파라미터 튜닝
hnsw_config = {
    "m": 16,                # 정확도-속도 균형
    "ef_construct": 200,    # 인덱스 품질
    "ef": 100,              # 검색 시 품질
}

# Quantization으로 메모리 감소 (정확도 약간 손실)
quantization_config = ScalarQuantization(
    scalar=ScalarQuantizationConfig(
        type=ScalarType.INT8,
        always_ram=True,
    )
)
```

---

## 6. Embedding 배치 처리

```python
# Before — 1개씩 임베딩
for chunk in chunks:
    vector = model.encode(chunk.text)
    
# After — 배치 처리
vectors = model.encode(
    [c.text for c in chunks],
    batch_size=32,
    show_progress_bar=True,
)
# 약 5~10x 빠름 (GPU 활용 시)
```

---

## 7. Connection Pool

### PostgreSQL
```python
from asyncpg import create_pool

pool = await create_pool(
    dsn=settings.POSTGRES_DSN,
    min_size=5,
    max_size=20,
    max_inactive_connection_lifetime=300,
)
```

### Redis
```python
from redis.asyncio import ConnectionPool, Redis

pool = ConnectionPool.from_url(
    settings.REDIS_URL,
    max_connections=50,
)
redis = Redis(connection_pool=pool)
```

### HTTP (httpx)
```python
client = httpx.AsyncClient(
    limits=httpx.Limits(
        max_keepalive_connections=20,
        max_connections=100,
    ),
    timeout=httpx.Timeout(30.0),
)
```

---

## 8. 스트리밍 응답 (SSE)

### 효과
- 사용자 체감 속도 ↑ (TTFT 빨라짐)
- 긴 응답에서 특히 효과

```python
@router.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    async def event_generator():
        async for token in agent.astream(req.query):
            yield f"data: {json.dumps({'text': token})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no"}  # nginx 버퍼링 비활성화
    )
```

---

## 9. Kafka로 무거운 작업 분리

### 동기 처리의 문제
```
사용자 → /chat → LLM 요약 (5초) → 응답
                    ↑
              요청 블로킹
```

### Kafka 비동기 처리
```
사용자 → /chat → Kafka 발행 → 즉시 응답 (job_id)
                    ↓
              LLM Consumer (백그라운드)
                    ↓
              결과 → Redis 저장
                    
사용자 → /chat/result/{job_id} → 결과 조회
```

### 적용 대상
- 뉴스 일괄 요약
- 인덱싱 파이프라인 (PDF 처리)
- Self-RAG 재검색 루프
- 대량 데이터 분석

---

## 10. Adaptive RAG로 평균 응답 시간 단축

### 문제
모든 질의에 풀 파이프라인(Hybrid + Re-ranker + Rewriting) 적용 시  
단순 질의도 5초+ 소요.

### 해결
질의 난이도별 전략 분기.

| 난이도 | 전략 | 예상 응답 시간 |
|--------|------|----------------|
| simple | Vector Search only | 800ms |
| medium | Hybrid Search | 1,500ms |
| complex | Hybrid + Re-ranker + Rewriting | 3,500ms |

### 측정 계획
- 골든 셋 20개에 대해 평균 응답 시간 비교
- "Always complex" vs "Adaptive" 비교
- 결과: `docs/eval_results/adaptive_perf.md`

---

## 11. 모니터링 메트릭

```python
# Prometheus 메트릭
from prometheus_client import Histogram, Counter

api_latency = Histogram(
    "api_request_duration_seconds",
    "API 요청 처리 시간",
    ["endpoint", "method"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
)

cache_hits = Counter(
    "cache_hits_total",
    "캐시 hit 카운트",
    ["layer"]
)

cache_misses = Counter(
    "cache_misses_total",
    "캐시 miss 카운트",
    ["layer"]
)
```

### Grafana 대시보드 패널
- API 응답 시간 p50/p95/p99
- 캐시 hit/miss 비율
- LLM 호출 횟수 및 평균 시간
- Kafka Consumer lag

---

## 12. 부하 테스트

```bash
# locust로 부하 테스트
pip install locust

# locustfile.py
from locust import HttpUser, task, between

class CementRAGUser(HttpUser):
    wait_time = between(1, 3)
    
    @task(3)
    def simple_query(self):
        self.client.post("/chat", json={
            "query": "오늘 환율은?"
        })
    
    @task(1)
    def complex_query(self):
        self.client.post("/chat", json={
            "query": "전년 대비 생산량과 환율 변동을 고려한 원가 분석"
        })

# 실행
locust -f locustfile.py --host=http://localhost:8000
```

목표: 동시 사용자 50명 안정 처리.
