# 10. Multi-Agent A2A 설계

## 1. 도입 목적

도입 배경 — 단일 Agent 구조의 한계를 극복하고 Agent 간 표준 통신 프로토콜을 도입.

단일 Agent에 모든 기능을 몰아넣는 대신 **전문화된 Sub-Agent들이 협업**하는 구조입니다.

### 단일 Agent의 한계

```
[Single Agent]
  → 모든 도메인 지식 + 모든 Tool + 라우팅 로직 한 곳에
  → Tool 늘어날수록 프롬프트 복잡도 폭증
  → 한 영역 변경 시 전체 영향
```

### Multi-Agent의 장점

```
[Orchestrator]
    ├─ Market Agent  (환율/유연탄 도메인 전문)
    ├─ News Agent    (뉴스 처리 전문)
    ├─ RAG Agent     (문서 검색 전문)
    └─ ERP Agent     (생산 데이터 전문)

→ 각 Agent는 자기 도메인만 알면 됨
→ 독립적 개선·교체·테스트 가능
→ 병렬 실행 가능
```

---

## 2. Orchestrator + Sub-Agent 구조

### 책임 분리

| 컴포넌트 | 책임 |
|----------|------|
| **Orchestrator** | 의도 분류, Sub-Agent 선택, 결과 통합 |
| **Market Agent** | 환율, 유연탄 가격, 원가 분석, 날씨 기반 수요 예측 |
| **News Agent** | 뉴스 수집, LLM 요약, 트렌드 분석 |
| **RAG Agent** | Vector / Graph 검색, Self-RAG 루프 |
| **ERP Agent** | 생산량/재고 집계, 시계열 비교 |

### 흐름

```
사용자 질의
    │
    ▼
[Orchestrator]
  1. 의도 분류 (LLM)
  2. 호출할 Sub-Agent 결정
  3. A2A 메시지 생성
  4. Send API로 병렬 호출
    │
    ├──→ [Market Agent]  ┐
    ├──→ [News Agent]    │ 병렬 실행
    ├──→ [RAG Agent]     │
    └──→ [ERP Agent]     ┘
    │
    ▼
[Orchestrator]
  5. 결과 수집
  6. Synthesizer에 전달
```

---

## 3. A2A 프로토콜 인터페이스

### 표준 메시지 포맷

```python
class A2AMessage(BaseModel):
    """Agent 간 표준 메시지"""
    
    # 식별
    message_id: str = Field(default_factory=lambda: str(uuid4()))
    correlation_id: str             # 요청-응답 매칭
    
    # 라우팅
    sender: str                     # 발신 Agent ID
    receiver: str                   # 수신 Agent ID
    
    # 메시지 종류
    message_type: Literal[
        "request",    # 요청
        "response",   # 응답
        "error",      # 에러
        "stream",     # 스트리밍 청크
    ]
    
    # 페이로드
    payload: dict
    
    # 메타데이터
    timestamp: datetime = Field(default_factory=datetime.now)
    trace_id: Optional[str] = None  # OpenTelemetry trace
    priority: int = 0               # 우선순위 (높을수록 먼저 처리)
```

### Base Agent 인터페이스

```python
class BaseAgent(ABC):
    """모든 Sub-Agent 공통 인터페이스"""
    
    agent_id: str
    
    @abstractmethod
    async def handle(self, message: A2AMessage) -> A2AMessage:
        """수신 메시지 처리 → 응답 메시지 반환"""
        ...
    
    async def call_other_agent(
        self,
        receiver: str,
        payload: dict,
        timeout: float = 30.0,
    ) -> A2AMessage:
        """다른 Agent 호출 (동기)"""
        request = A2AMessage(
            sender=self.agent_id,
            receiver=receiver,
            message_type="request",
            payload=payload,
            correlation_id=str(uuid4()),
        )
        response = await self.bus.send(request, timeout=timeout)
        return response
    
    async def stream_to_agent(
        self,
        receiver: str,
        payload_iter: AsyncIterator[dict],
    ) -> AsyncIterator[A2AMessage]:
        """다른 Agent에 스트리밍 호출"""
        ...
```

---

## 4. Sub-Agent 구현 명세

### Market Agent

```python
class MarketAgent(BaseAgent):
    agent_id = "market_agent"
    
    async def handle(self, message: A2AMessage) -> A2AMessage:
        query = message.payload["query"]
        date = message.payload.get("date", "today")
        
        # 내부 Tool 병렬 호출
        exchange, coal_price, weather = await asyncio.gather(
            self.exchange_tool(date),
            self.coal_price_tool(date),
            self.weather_tool(date),
        )
        
        # 원가 계산
        coal_price_krw = coal_price.usd * exchange.rate
        cost_change = self.calculate_cost_change(coal_price_krw)
        
        return A2AMessage(
            sender=self.agent_id,
            receiver=message.sender,
            message_type="response",
            correlation_id=message.correlation_id,
            payload={
                "exchange": exchange.dict(),
                "coal_price_usd": coal_price.usd,
                "coal_price_krw": coal_price_krw,
                "cost_change_pct": cost_change,
                "weather": weather.dict(),
            }
        )
```

### News Agent

```python
class NewsAgent(BaseAgent):
    agent_id = "news_agent"
    
    async def handle(self, message: A2AMessage) -> A2AMessage:
        keywords = message.payload.get("keywords", DEFAULT_KEYWORDS)
        
        # 1. 뉴스 수집 (3개 키워드 병렬)
        articles = await self.collect_news(keywords)
        
        # 2. Kafka로 LLM 요약 작업 발행 (비동기)
        job_id = await self.kafka_producer.publish(
            topic="llm.requests",
            payload={
                "task": "summarize_news",
                "articles": [a.dict() for a in articles],
            }
        )
        
        # 3. 결과 폴링 (Redis pub/sub or 결과 토픽)
        summary = await self.wait_for_result(job_id, timeout=10)
        
        return A2AMessage(
            sender=self.agent_id,
            receiver=message.sender,
            message_type="response",
            correlation_id=message.correlation_id,
            payload={
                "articles": [a.dict() for a in articles],
                "summary": summary.text,
                "trend": summary.trend,
            }
        )
```

### RAG Agent

```python
class RAGAgent(BaseAgent):
    agent_id = "rag_agent"
    
    async def handle(self, message: A2AMessage) -> A2AMessage:
        query = message.payload["query"]
        
        # 1. 검색 유형 분류
        search_type = await self.classify_search_type(query)
        
        # 2. 분기 실행
        if search_type == "vector":
            results = await self.vector_search(query)        # Qdrant
        elif search_type == "graph":
            results = await self.graph_search(query)         # Neo4j
        else:  # hybrid
            # Qdrant Vector + Elasticsearch BM25(nori) 병렬 호출 후 RRF 결합
            vec, bm25, graph = await asyncio.gather(
                self.vector_search(query),       # Qdrant cosine
                self.es_bm25_search(query),      # Elasticsearch + nori
                self.graph_search(query),        # Neo4j
            )
            results = self.rrf_merge(vec, bm25, graph)
        
        # 3. Self-RAG 루프
        results = await self.self_rag_loop(query, results)
        
        return A2AMessage(
            sender=self.agent_id,
            receiver=message.sender,
            message_type="response",
            correlation_id=message.correlation_id,
            payload={
                "search_type": search_type,
                "chunks": [r.dict() for r in results],
            }
        )
```

### ERP Agent

```python
class ERPAgent(BaseAgent):
    agent_id = "erp_agent"
    
    async def handle(self, message: A2AMessage) -> A2AMessage:
        query_type = message.payload["query_type"]
        period = message.payload.get("period", "this_month")
        
        # SQL 쿼리 분기
        if query_type == "monthly_compare":
            data = await self.compare_monthly(period)
        elif query_type == "inventory":
            data = await self.get_inventory()
        else:
            data = await self.get_trend(period)
        
        return A2AMessage(
            sender=self.agent_id,
            receiver=message.sender,
            message_type="response",
            correlation_id=message.correlation_id,
            payload=data,
        )
```

---

## 5. Agent Bus (메시지 라우팅)

```python
class AgentBus:
    """Agent 간 메시지 전달 허브"""
    
    def __init__(self):
        self.agents: dict[str, BaseAgent] = {}
        self.pending_responses: dict[str, asyncio.Future] = {}
    
    def register(self, agent: BaseAgent):
        self.agents[agent.agent_id] = agent
    
    async def send(
        self, 
        message: A2AMessage,
        timeout: float = 30.0,
    ) -> A2AMessage:
        """메시지 전달 후 응답 대기"""
        receiver = self.agents.get(message.receiver)
        if not receiver:
            raise AgentNotFoundError(message.receiver)
        
        # 응답 대기 Future 등록
        future = asyncio.Future()
        self.pending_responses[message.correlation_id] = future
        
        # 비동기 처리
        asyncio.create_task(self._handle(receiver, message))
        
        # 타임아웃 적용
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        finally:
            self.pending_responses.pop(message.correlation_id, None)
    
    async def _handle(self, receiver: BaseAgent, message: A2AMessage):
        try:
            response = await receiver.handle(message)
            future = self.pending_responses.get(message.correlation_id)
            if future and not future.done():
                future.set_result(response)
        except Exception as e:
            # 에러 메시지로 변환
            error_msg = A2AMessage(
                sender=receiver.agent_id,
                receiver=message.sender,
                message_type="error",
                correlation_id=message.correlation_id,
                payload={"error": str(e)},
            )
            future = self.pending_responses.get(message.correlation_id)
            if future and not future.done():
                future.set_result(error_msg)
```

---

## 6. Orchestrator 구현

```python
class Orchestrator(BaseAgent):
    agent_id = "orchestrator"
    
    async def handle(self, message: A2AMessage) -> A2AMessage:
        query = message.payload["query"]
        
        # 1. 의도 분류
        intents = await self.classify_intent(query)
        # intents: ["market", "news"]
        
        # 2. Sub-Agent 매핑
        sub_agents = self.map_intents_to_agents(intents)
        # sub_agents: ["market_agent", "news_agent"]
        
        # 3. 병렬 호출 (LangGraph Send API 또는 asyncio.gather)
        responses = await asyncio.gather(*[
            self.call_other_agent(
                receiver=agent_id,
                payload={"query": query},
            )
            for agent_id in sub_agents
        ])
        
        # 4. 결과 통합
        merged_results = {
            r.sender: r.payload 
            for r in responses 
            if r.message_type == "response"
        }
        
        return A2AMessage(
            sender=self.agent_id,
            receiver=message.sender,
            message_type="response",
            correlation_id=message.correlation_id,
            payload={
                "sub_agent_results": merged_results,
                "agents_called": sub_agents,
            }
        )
```

### 의도 분류 프롬프트

```python
INTENT_CLASSIFICATION_PROMPT = """
사용자 질의를 분석하여 호출할 Sub-Agent를 결정하세요.

가능한 Sub-Agent:
- market_agent: 환율, 유연탄, 원가, 날씨 기반 수요
- news_agent: 뉴스 수집 + 요약
- rag_agent: 규제, 매뉴얼, 품질 기준 문서 검색
- erp_agent: 생산량, 재고, 실적 집계

복합 질의는 여러 Agent 동시 호출 가능.

JSON 응답:
{
  "intents": ["market", "news"],
  "agents_to_call": ["market_agent", "news_agent"],
  "reasoning": "..."
}
"""
```

---

## 7. LangGraph 통합

```python
graph = StateGraph(AgentState)

graph.add_node("orchestrator",  orchestrator_node)
graph.add_node("market_agent",  market_agent_node)
graph.add_node("news_agent",    news_agent_node)
graph.add_node("rag_agent",     rag_agent_node)
graph.add_node("erp_agent",     erp_agent_node)
graph.add_node("synthesizer",   synthesizer_node)

graph.add_edge(START, "orchestrator")

# Send API로 병렬 분기
graph.add_conditional_edges(
    "orchestrator",
    lambda state: [
        Send(agent, {"query": state["query"]})
        for agent in state["sub_agents_to_call"]
    ],
    ["market_agent", "news_agent", "rag_agent", "erp_agent"]
)

# 모든 Sub-Agent → Synthesizer
for agent in ["market_agent", "news_agent", "rag_agent", "erp_agent"]:
    graph.add_edge(agent, "synthesizer")

graph.add_edge("synthesizer", END)
```

---

## 8. 에러 처리 및 Fallback

### Sub-Agent 실패 시
- 다른 Sub-Agent 결과로만 응답 생성 (graceful degradation)
- 실패한 Agent 로깅 → Prometheus 메트릭에 기록
- 실패 정보를 응답 메타데이터에 포함

```python
async def synthesize_with_fallback(
    sub_agent_results: dict,
    failed_agents: list[str],
) -> str:
    if not sub_agent_results:
        return "현재 데이터를 가져올 수 없습니다."
    
    available = list(sub_agent_results.keys())
    
    answer = await llm.generate(
        SYNTHESIZER_PROMPT.format(
            results=sub_agent_results,
            note=f"일부 데이터({failed_agents}) 미반영" if failed_agents else "",
        )
    )
    return answer
```

---

## 9. 확장성 고려사항

### Agent 추가 시
새 도메인이 생기면 `BaseAgent` 상속 후 등록만 하면 됨.

```python
class WeatherForecastAgent(BaseAgent):
    agent_id = "weather_forecast_agent"
    async def handle(self, message): ...

# 등록
bus.register(WeatherForecastAgent())
```

### Agent를 별도 마이크로서비스로 분리
초기에는 단일 프로세스 내 호출, 트래픽 증가 시 Agent별로 별도 서비스로 분리 가능.

```
[현재]
FastAPI 프로세스
  └─ Orchestrator + 모든 Sub-Agent

[확장 후]
FastAPI (Orchestrator만)
  ├──→ Market Service (별도 K8s Pod)
  ├──→ News Service
  ├──→ RAG Service
  └──→ ERP Service
```

이때 `AgentBus`를 HTTP 또는 gRPC로 교체하면 됨.

---

## 10. 모니터링

### Agent별 메트릭
```python
agent_request_total = Counter(
    "agent_request_total",
    "Agent 요청 횟수",
    ["agent_id", "status"]
)

agent_latency = Histogram(
    "agent_latency_seconds",
    "Agent 처리 시간",
    ["agent_id"]
)
```

### 트레이싱 (Jaeger / LangSmith)
```python
async def handle(self, message: A2AMessage) -> A2AMessage:
    with tracer.start_as_current_span(f"{self.agent_id}.handle") as span:
        span.set_attribute("agent.id", self.agent_id)
        span.set_attribute("correlation_id", message.correlation_id)
        # ... 처리 ...
```

각 Sub-Agent 실행이 트레이스로 시각화되어 병목 파악이 쉬워짐.
