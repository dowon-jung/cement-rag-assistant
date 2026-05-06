# 12. Kafka 이벤트 스트리밍 설계

## 1. 도입 목적

수집기와 처리기를 **완전히 디커플링**하여 다음을 달성합니다.

- **장애 격리**: 인덱싱 워커 다운 시에도 수집은 계속 동작
- **확장성**: Consumer를 늘려서 처리량 스케일 아웃
- **비동기 처리**: 무거운 작업을 백그라운드로 분리
- **재처리**: 실패 메시지를 DLQ에 보관해 안전하게 재시도
- **이벤트 추적**: 모든 데이터 흐름이 토픽으로 기록됨

---

## 2. Topic 설계

### Topic 목록

| Topic | 용도 | 파티션 | Retention | Producer | Consumer |
|-------|------|--------|-----------|----------|----------|
| `market.raw` | 환율 수집 이벤트 | 3 | 7d | exchange_collector | monitoring_consumer (로깅·알림 전용) |
| `news.raw` | 뉴스 수집 이벤트 | 3 | 7d | news_collector | llm_consumer |
| `weather.raw` | 날씨 수집 이벤트 | 3 | 3d | weather_collector | weather_consumer |
| `erp.updated` | ERP 배치 완료 | 1 | 14d | erp_batch | erp_consumer |
| `indexing.requests` | 인덱싱 요청 | 5 | 7d | pipeline_trigger | indexing_consumer |
| `indexing.results` | 인덱싱 완료 | 3 | 3d | indexing_consumer | (모니터링) |
| `llm.requests` | LLM 비동기 처리 요청 | 5 | 7d | news_agent, rag_agent | llm_consumer |
| `llm.results` | LLM 처리 완료 | 5 | 3d | llm_consumer | 호출자 |
| `dlq.errors` | Dead Letter Queue | 3 | 30d | 모든 Consumer | dlq_consumer |

### 파티션 키 전략

| Topic | Partition Key | 이유 |
|-------|---------------|------|
| `market.raw` | `currency` | 통화별로 동일 파티션 → 순서 보장 |
| `news.raw` | `keyword` | 키워드별 처리 분산 |
| `indexing.requests` | `source_type` | 동일 유형 문서끼리 묶이도록 |
| `llm.requests` | `correlation_id` | 동일 요청은 동일 파티션 |

---

## 3. 메시지 스키마

### 공통 envelope

```python
class KafkaMessage(BaseModel):
    """모든 Kafka 메시지 공통 envelope"""
    
    # 메타데이터
    message_id: str = Field(default_factory=lambda: str(uuid4()))
    correlation_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    schema_version: str = "v1"
    
    # 라우팅
    source: str                    # 발행한 서비스명
    event_type: str                # 이벤트 종류
    
    # 실제 데이터
    payload: dict
    
    # 추적
    trace_id: Optional[str] = None
```

### Topic별 payload 스키마

#### market.raw
```python
{
    "type": "exchange",
    "currency": "USD/KRW",
    "rate": 1380.0,
    "base_date": "2025-05-06",
    "collected_at": "2025-05-06T11:00:00"
}
```
> market.raw는 별도 처리 Consumer가 없습니다. 환율 데이터는 수집 시점에 이미 PostgreSQL에 저장되며,
> market.raw 토픽은 **모니터링·알림 전용**입니다. (예: 환율 급변 감지 시 Alertmanager 연동)

#### news.raw
```python
{
    "keyword": "시멘트 수요",
    "articles": [
        {
            "title": "...",
            "link": "...",
            "description": "...",
            "pub_date": "2025-05-06T09:00:00"
        }
    ],
    "collected_at": "2025-05-06T09:30:00"
}
```

#### indexing.requests
```python
{
    "source_type": "regulation",  # regulation | coal | manual | quality
    "file_path": "/data/raw/대기환경보전법.pdf",
    "metadata": {
        "law_name": "대기환경보전법",
        "version": "2025-01"
    }
}
```

#### llm.requests
```python
{
    "task": "summarize_news",     # summarize_news | self_rag | rewrite_query
    "prompt_template": "...",
    "input_data": {...},
    "callback_topic": "llm.results",
    "priority": 1
}
```

#### dlq.errors
```python
{
    "original_topic": "indexing.requests",
    "original_message": {...},
    "error_type": "ChunkingError",
    "error_message": "PDF 파싱 실패",
    "retry_count": 3,
    "first_failed_at": "2025-05-06T10:00:00"
}
```

---

## 4. Producer 구현

```python
# app/kafka/producer.py
from aiokafka import AIOKafkaProducer
import json

class KafkaProducer:
    def __init__(self, bootstrap_servers: str):
        self.producer = AIOKafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            acks="all",                    # 모든 ISR 확인
            compression_type="lz4",        # 압축
            enable_idempotence=True,       # 중복 방지
            max_in_flight_requests_per_connection=5,
        )
    
    async def start(self):
        await self.producer.start()
    
    async def stop(self):
        await self.producer.stop()
    
    async def publish(
        self,
        topic: str,
        payload: dict,
        partition_key: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> str:
        message = KafkaMessage(
            source="cement-rag",
            event_type=topic,
            correlation_id=correlation_id,
            payload=payload,
        )
        
        # 발행 (재시도 3회, exponential backoff)
        for attempt in range(3):
            try:
                await self.producer.send_and_wait(
                    topic,
                    value=message.dict(),
                    key=partition_key.encode() if partition_key else None,
                )
                return message.message_id
            except KafkaError as e:
                if attempt == 2:
                    raise
                await asyncio.sleep(2 ** attempt)
```

---

## 5. Consumer 구현

### Base Consumer

```python
# app/kafka/consumers/base.py
from aiokafka import AIOKafkaConsumer
import json

class BaseConsumer(ABC):
    consumer_group: str
    topics: list[str]
    
    def __init__(self, bootstrap_servers: str):
        self.consumer = AIOKafkaConsumer(
            *self.topics,
            bootstrap_servers=bootstrap_servers,
            group_id=self.consumer_group,
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            auto_offset_reset="earliest",
            enable_auto_commit=False,    # 수동 커밋
            max_poll_records=10,
        )
        self.dlq_producer = KafkaProducer(bootstrap_servers)
    
    @abstractmethod
    async def process(self, message: dict) -> None:
        ...
    
    async def run(self):
        await self.consumer.start()
        try:
            async for msg in self.consumer:
                try:
                    await self.process(msg.value)
                    await self.consumer.commit()
                except Exception as e:
                    await self._send_to_dlq(msg, e)
                    await self.consumer.commit()
        finally:
            await self.consumer.stop()
    
    async def _send_to_dlq(self, msg, error):
        await self.dlq_producer.publish(
            topic="dlq.errors",
            payload={
                "original_topic": msg.topic,
                "original_message": msg.value,
                "error_type": type(error).__name__,
                "error_message": str(error),
                "retry_count": 0,
                "first_failed_at": datetime.now().isoformat(),
            }
        )
```

### Indexing Consumer

```python
# app/kafka/consumers/indexing_consumer.py
class IndexingConsumer(BaseConsumer):
    consumer_group = "indexing-workers"
    topics = ["indexing.requests"]
    
    async def process(self, message: dict):
        payload = message["payload"]
        source_type = payload["source_type"]
        file_path = payload["file_path"]
        
        # 1. 청킹 전략 분기
        if source_type == "regulation":
            chunks = await semantic_chunk(file_path)
        elif source_type == "coal":
            chunks = await table_aware_chunk(file_path)
        else:
            chunks = await semantic_chunk(file_path)
        
        # 2. 임베딩 + Qdrant 적재
        await self.index_to_qdrant(chunks, source_type)
        
        # 3. 완료 이벤트 발행
        await self.producer.publish(
            topic="indexing.results",
            payload={
                "source_type": source_type,
                "file_path": file_path,
                "chunks_indexed": len(chunks),
                "status": "success",
            }
        )
```

### LLM Consumer

```python
class LLMConsumer(BaseConsumer):
    consumer_group = "llm-workers"
    topics = ["llm.requests"]
    
    async def process(self, message: dict):
        payload = message["payload"]
        task = payload["task"]
        
        # Task별 분기
        if task == "summarize_news":
            result = await self.summarize_news(payload["input_data"])
        elif task == "self_rag":
            result = await self.self_rag_evaluate(payload["input_data"])
        elif task == "rewrite_query":
            result = await self.rewrite_query(payload["input_data"])
        
        # 결과 발행
        await self.producer.publish(
            topic=payload.get("callback_topic", "llm.results"),
            payload={
                "task": task,
                "result": result,
                "correlation_id": message["correlation_id"],
            }
        )
```

### DLQ Consumer

```python
class DLQConsumer(BaseConsumer):
    consumer_group = "dlq-handler"
    topics = ["dlq.errors"]
    MAX_RETRY = 3
    
    async def process(self, message: dict):
        payload = message["payload"]
        retry_count = payload.get("retry_count", 0)
        
        if retry_count >= self.MAX_RETRY:
            # 최대 재시도 초과 → 영구 실패 로깅
            logger.error(
                "dlq_max_retry_exceeded",
                original_topic=payload["original_topic"],
                error=payload["error_message"],
            )
            return
        
        # exponential backoff 후 원본 토픽으로 재발행
        await asyncio.sleep(2 ** retry_count)
        
        original_msg = payload["original_message"]
        original_msg["payload"]["_retry_count"] = retry_count + 1
        
        await self.producer.publish(
            topic=payload["original_topic"],
            payload=original_msg["payload"]
        )
```

---

## 6. 동시성 및 순서 보장

### 동일 entity 순서 보장
파티션 키를 동일 entity로 설정하면 같은 파티션에 저장되어 순서가 보장됨.

```python
# 환율은 통화별로 순서 보장
await producer.publish(
    topic="market.raw",
    payload=data,
    partition_key="USD/KRW",
)
```

### Consumer 동시 실행
```python
# Consumer 5개 동시 실행 (같은 group_id)
# Kafka가 자동으로 파티션 분배
async def run_consumers():
    tasks = [
        IndexingConsumer().run() for _ in range(5)
    ]
    await asyncio.gather(*tasks)
```

---

## 7. Docker Compose 구성

```yaml
# docker-compose.yml (Kafka 부분)
kafka:
  image: confluentinc/cp-kafka:7.5.0
  ports:
    - "9092:9092"
  environment:
    KAFKA_NODE_ID: 1
    KAFKA_PROCESS_ROLES: broker,controller
    KAFKA_LISTENERS: PLAINTEXT://:9092,CONTROLLER://:9093
    KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:9092
    KAFKA_CONTROLLER_LISTENER_NAMES: CONTROLLER
    KAFKA_CONTROLLER_QUORUM_VOTERS: 1@kafka:9093
    KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: PLAINTEXT:PLAINTEXT,CONTROLLER:PLAINTEXT
    CLUSTER_ID: cement-rag-cluster
    KAFKA_AUTO_CREATE_TOPICS_ENABLE: "false"
  volumes:
    - kafka_data:/var/lib/kafka/data

kafka-ui:
  image: provectuslabs/kafka-ui:latest
  ports:
    - "8080:8080"
  environment:
    KAFKA_CLUSTERS_0_NAME: cement-rag
    KAFKA_CLUSTERS_0_BOOTSTRAPSERVERS: kafka:9092
```

---

## 8. Topic 초기화 스크립트

```python
# scripts/init_kafka.py
from kafka.admin import KafkaAdminClient, NewTopic

TOPICS = [
    NewTopic(name="market.raw",         num_partitions=3, replication_factor=1,
             topic_configs={"retention.ms": "604800000"}),  # 7일
    NewTopic(name="news.raw",           num_partitions=3, replication_factor=1,
             topic_configs={"retention.ms": "604800000"}),
    NewTopic(name="weather.raw",        num_partitions=3, replication_factor=1,
             topic_configs={"retention.ms": "259200000"}),  # 3일
    NewTopic(name="erp.updated",        num_partitions=1, replication_factor=1),
    NewTopic(name="indexing.requests",  num_partitions=5, replication_factor=1),
    NewTopic(name="indexing.results",   num_partitions=3, replication_factor=1),
    NewTopic(name="llm.requests",       num_partitions=5, replication_factor=1),
    NewTopic(name="llm.results",        num_partitions=5, replication_factor=1),
    NewTopic(name="dlq.errors",         num_partitions=3, replication_factor=1,
             topic_configs={"retention.ms": "2592000000"}),  # 30일
]

admin = KafkaAdminClient(bootstrap_servers="localhost:9092")
admin.create_topics(TOPICS, validate_only=False)
```

---

## 9. 모니터링

### Consumer Lag
Consumer가 메시지 처리를 따라가지 못하면 lag이 쌓임.

```promql
kafka_consumer_lag{topic="indexing.requests"} > 1000
```

이 값이 일정 임계값을 초과하면 K8s HPA가 Consumer Pod를 자동으로 늘림 (Phase 13 참고).

### DLQ 모니터링
```promql
rate(dlq_messages_total[5m]) > 10
```
DLQ에 메시지가 급증하면 Alertmanager가 알림 발송.

### Kafka UI
`http://localhost:8080`에서 실시간 토픽 상태, 메시지 검색, Consumer group 관리 가능.

---

## 10. 운영 시나리오

### 시나리오 1 — 인덱싱 워커 다운
```
1. 인덱싱 Consumer Pod 다운
2. indexing.requests 토픽에 메시지 쌓임 (lag 증가)
3. K8s가 새 Pod 시작
4. 새 Pod가 마지막 commit offset부터 처리 재개
5. 메시지 손실 없음
```

### 시나리오 2 — PDF 파싱 실패
```
1. indexing_consumer에서 PDF 파싱 실패
2. dlq.errors로 메시지 이동
3. dlq_consumer가 2초 후 재시도 (1회차)
4. 또 실패 → 4초 후 재시도 (2회차)
5. 또 실패 → 8초 후 재시도 (3회차)
6. 최대 재시도 초과 → 영구 실패 로깅 + 알림
```

### 시나리오 3 — 트래픽 급증
```
1. 사용자 질의 폭증 → llm.requests 발행 폭증
2. Consumer lag 증가
3. HPA가 LLM Consumer Pod를 1 → 5개로 스케일 아웃
4. 처리량 5배 증가 → lag 회복
5. 트래픽 안정 후 Pod 자동 축소
```
