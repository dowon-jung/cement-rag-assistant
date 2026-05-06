# 11. 모니터링 설계

## 1. 모니터링 스택

```
[FastAPI / Sub-Agents]
        │
        ├──→ Prometheus (메트릭 수집)
        │       └─ Grafana (시각화)
        │
        ├──→ OpenTelemetry / Jaeger (분산 트레이싱) — 에어갭 환경
        │
        └──→ LangSmith (LLM 트레이싱) — 인터넷 환경
```

---

## 2. Prometheus 메트릭 정의

### API 메트릭

```python
from prometheus_client import Counter, Histogram, Gauge

api_requests_total = Counter(
    "api_requests_total",
    "API 요청 총 횟수",
    ["method", "endpoint", "status_code"]
)

api_latency_seconds = Histogram(
    "api_latency_seconds",
    "API 응답 시간",
    ["method", "endpoint"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0]
)

active_requests = Gauge(
    "active_requests",
    "현재 처리 중인 요청 수"
)
```

### Agent 메트릭

```python
agent_invocations_total = Counter(
    "agent_invocations_total",
    "Agent 호출 횟수",
    ["agent_id", "status"]
)

agent_latency_seconds = Histogram(
    "agent_latency_seconds",
    "Agent 처리 시간",
    ["agent_id"]
)

agent_errors_total = Counter(
    "agent_errors_total",
    "Agent 에러 횟수",
    ["agent_id", "error_type"]
)
```

### LLM 메트릭

```python
llm_calls_total = Counter(
    "llm_calls_total",
    "LLM 호출 횟수",
    ["backend", "model"]
)

llm_tokens_total = Counter(
    "llm_tokens_total",
    "LLM 토큰 사용량",
    ["backend", "model", "type"]  # type: input | output
)

llm_latency_seconds = Histogram(
    "llm_latency_seconds",
    "LLM 응답 시간",
    ["backend"],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0]
)

llm_ttft_seconds = Histogram(
    "llm_ttft_seconds",
    "First Token까지 걸린 시간",
    ["backend"]
)
```

### 캐시 메트릭

```python
cache_hits_total = Counter(
    "cache_hits_total",
    "캐시 히트 횟수",
    ["layer"]  # L1 | L2 | L3 | L4
)

cache_misses_total = Counter(
    "cache_misses_total",
    "캐시 미스 횟수",
    ["layer"]
)

# 자동 계산: hit_rate = hits / (hits + misses)
```

### Kafka 메트릭

```python
kafka_messages_published_total = Counter(
    "kafka_messages_published_total",
    "Kafka Producer 발행 횟수",
    ["topic", "status"]
)

kafka_messages_consumed_total = Counter(
    "kafka_messages_consumed_total",
    "Kafka Consumer 처리 횟수",
    ["topic", "status"]
)

kafka_consumer_lag = Gauge(
    "kafka_consumer_lag",
    "Kafka Consumer 지연",
    ["topic", "consumer_group"]
)

dlq_messages_total = Counter(
    "dlq_messages_total",
    "DLQ 발생 횟수",
    ["original_topic"]
)
```

### RAG 메트릭

```python
rag_search_total = Counter(
    "rag_search_total",
    "RAG 검색 호출",
    ["search_type"]  # vector | graph | hybrid
)

rag_retrieval_quality = Histogram(
    "rag_retrieval_quality",
    "Self-RAG 검색 품질 점수",
    buckets=[0.0, 0.3, 0.5, 0.7, 0.85, 1.0]
)

self_rag_retries = Histogram(
    "self_rag_retries",
    "Self-RAG 재검색 횟수",
    buckets=[0, 1, 2, 3]
)
```

---

## 3. Prometheus 설정

```yaml
# monitoring/prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'cement-rag-app'
    static_configs:
      - targets: ['app:8000']
    metrics_path: /metrics
  
  - job_name: 'kafka'
    static_configs:
      - targets: ['kafka:9308']  # JMX exporter
  
  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres-exporter:9187']
  
  - job_name: 'redis'
    static_configs:
      - targets: ['redis-exporter:9121']
  
  - job_name: 'qdrant'
    static_configs:
      - targets: ['qdrant:6333']
    metrics_path: /metrics
```

---

## 4. Grafana 대시보드 구성

### 대시보드 1 — API 성능

| 패널 | PromQL |
|------|--------|
| 요청 수 (RPS) | `rate(api_requests_total[1m])` |
| 응답 시간 p50/p95/p99 | `histogram_quantile(0.95, rate(api_latency_seconds_bucket[5m]))` |
| 에러율 | `rate(api_requests_total{status_code=~"5.."}[1m])` |
| 활성 요청 | `active_requests` |

### 대시보드 2 — Agent 성능

| 패널 | PromQL |
|------|--------|
| Agent별 호출 수 | `sum by (agent_id) (rate(agent_invocations_total[1m]))` |
| Agent별 평균 응답 시간 | `rate(agent_latency_seconds_sum[5m]) / rate(agent_latency_seconds_count[5m])` |
| Agent별 에러율 | `rate(agent_errors_total[1m]) / rate(agent_invocations_total[1m])` |

### 대시보드 3 — LLM 사용량

| 패널 | PromQL |
|------|--------|
| LLM 호출 RPS | `rate(llm_calls_total[1m])` |
| 백엔드별 TTFT | `histogram_quantile(0.95, rate(llm_ttft_seconds_bucket[5m]))` |
| 토큰 사용량 (input/output) | `rate(llm_tokens_total[1m])` |
| 백엔드별 비용 추정 | `rate(llm_tokens_total[1h]) * cost_per_token` |

### 대시보드 4 — 캐시 효율

| 패널 | PromQL |
|------|--------|
| 레이어별 hit rate | `rate(cache_hits_total[5m]) / (rate(cache_hits_total[5m]) + rate(cache_misses_total[5m]))` |
| 캐시 메모리 사용량 | Redis exporter 메트릭 |

### 대시보드 5 — Kafka 파이프라인

| 패널 | PromQL |
|------|--------|
| Topic별 publish RPS | `rate(kafka_messages_published_total[1m])` |
| Topic별 consume RPS | `rate(kafka_messages_consumed_total[1m])` |
| **Consumer lag (HPA 트리거)** | `kafka_consumer_lag` |
| DLQ 발생 횟수 | `rate(dlq_messages_total[5m])` |

### 대시보드 6 — RAG 품질

| 패널 | PromQL |
|------|--------|
| 검색 유형별 호출 비율 | `sum by (search_type) (rate(rag_search_total[5m]))` |
| Self-RAG 재시도 분포 | Histogram `self_rag_retries` |
| 평균 검색 품질 | Histogram avg `rag_retrieval_quality` |

---

## 5. 알림 규칙 (Alertmanager)

```yaml
# monitoring/alerts.yml
groups:
  - name: cement_rag_alerts
    rules:
      - alert: HighAPIErrorRate
        expr: rate(api_requests_total{status_code=~"5.."}[5m]) > 0.05
        for: 5m
        annotations:
          summary: "API 에러율 5% 초과"
      
      - alert: SlowAPIResponse
        expr: histogram_quantile(0.95, rate(api_latency_seconds_bucket[5m])) > 5
        for: 10m
        annotations:
          summary: "API p95 응답 시간 5초 초과"
      
      - alert: KafkaConsumerLag
        expr: kafka_consumer_lag > 1000
        for: 5m
        annotations:
          summary: "Kafka Consumer lag {{ $value }} 초과"
      
      - alert: DLQSpike
        expr: rate(dlq_messages_total[5m]) > 10
        for: 2m
        annotations:
          summary: "DLQ 메시지 급증 — 처리 실패 대량 발생"
      
      - alert: LowCacheHitRate
        expr: |
          rate(cache_hits_total[10m]) 
          / (rate(cache_hits_total[10m]) + rate(cache_misses_total[10m])) 
          < 0.4
        for: 30m
        annotations:
          summary: "캐시 hit rate 40% 미만"
```

---

## 6. 분산 트레이싱

### LangSmith (인터넷 환경)

```python
# .env
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=ls__xxxxx
LANGSMITH_PROJECT=cement-rag

# 자동으로 LangChain/LangGraph 호출이 트레이스됨
```

수집되는 정보:
- Agent 실행 트리 (Orchestrator → Sub-Agent)
- 각 Tool 호출 입출력
- LLM 프롬프트 및 응답
- 토큰 사용량
- 실행 시간

### OpenTelemetry + Jaeger (에어갭 환경)

```python
# app/monitoring/tracing.py
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

def setup_tracing(app):
    provider = TracerProvider()
    
    jaeger_exporter = JaegerExporter(
        agent_host_name="jaeger",
        agent_port=6831,
    )
    
    provider.add_span_processor(
        BatchSpanProcessor(jaeger_exporter)
    )
    
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app)

tracer = trace.get_tracer(__name__)
```

각 Agent에서 수동 계측:
```python
async def handle(self, message: A2AMessage) -> A2AMessage:
    with tracer.start_as_current_span(f"{self.agent_id}.handle") as span:
        span.set_attribute("agent.id", self.agent_id)
        span.set_attribute("correlation_id", message.correlation_id)
        # 처리 로직
```

---

## 7. 로깅 전략

### 구조화 로깅 (JSON)

```python
import structlog

logger = structlog.get_logger()

logger.info(
    "agent_invocation",
    agent_id="market_agent",
    correlation_id="abc-123",
    duration_ms=240,
    status="success",
)
```

### 로그 레벨 가이드

| 레벨 | 용도 |
|------|------|
| DEBUG | 개발 시 상세 흐름 |
| INFO | 정상 동작 (Agent 호출, 외부 API 응답) |
| WARNING | Self-RAG 재시도, 캐시 miss 폭증 |
| ERROR | Agent 실패, LLM 에러, DB 연결 실패 |
| CRITICAL | 시스템 다운 위험 (DB down, OOM 등) |

### 로그 수집
- 단일 노드 환경: 로컬 파일 → logrotate
- K8s 환경: 표준 출력 → Fluentd / Loki

---

## 8. 헬스체크

### `/health` 엔드포인트

```python
@router.get("/health")
async def health():
    checks = {
        "postgres": await check_postgres(),
        "redis": await check_redis(),
        "qdrant": await check_qdrant(),
        "neo4j": await check_neo4j(),
        "kafka": await check_kafka(),
        "llm_backend": await check_llm(),
    }
    
    all_healthy = all(c["healthy"] for c in checks.values())
    status_code = 200 if all_healthy else 503
    
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "healthy" if all_healthy else "unhealthy",
            "checks": checks,
        }
    )
```

### K8s liveness / readiness probe
```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 10

readinessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 5
```

---

## 9. 면접 어필 포인트

이 모니터링 설계로 어필 가능한 점:

1. **수치 기반 의사결정**: "캐시 hit rate가 40%까지 떨어져서 TTL 조정으로 75%까지 회복"
2. **병목 식별**: Jaeger 트레이스로 "RAG Agent의 Self-RAG 루프가 평균 1.2초 차지하는 것 발견"
3. **비용 최적화**: LLM 토큰 사용량 추적 → 백엔드 전환 비용 비교
4. **실서비스 운영 역량**: HPA 트리거 메트릭 명확히 설계
