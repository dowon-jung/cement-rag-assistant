# 03. Agent 설계

## 1. 전체 Agent 흐름

```
사용자 질의
    │
    ▼
[Adaptive Router]
  질의 난이도 분류 → 검색 전략 선택
    │
    ├─ 단순  → Vector Search only
    ├─ 중간  → Hybrid Search
    └─ 복잡  → Hybrid + Re-ranker + Query Rewriting
    │
    ▼
[Orchestrator Agent]
  의도 분류 → Sub-Agent 선택
    │
    ├─ Market Agent  ─┐
    ├─ News Agent    ─┤  (LangGraph Send API 병렬 실행)
    ├─ RAG Agent     ─┤
    └─ ERP Agent     ─┘
    │         ↑
    │    RAG Agent 내부에서만 Self-RAG 루프 실행
    │    (검색 결과 자가 평가 → 불충분 시 재검색, 최대 3회)
    │    다른 Sub-Agent(Market, News, ERP)는 Self-RAG 미적용
    │
    ▼
[Answer Synthesizer]
  Sub-Agent 결과 통합 → LLM 답변 생성
    │
    ▼
사용자 응답 (SSE 스트리밍)
```

---

## 2. LangGraph 상태 정의

```python
class AgentState(TypedDict):
    # 입력
    query: str                          # 원본 질의
    
    # Adaptive RAG
    complexity: Literal["simple", "medium", "complex"]
    search_strategy: dict
    
    # Orchestrator
    intent: List[str]                   # 분류된 의도
    sub_agents_to_call: List[str]       # 호출할 Sub-Agent
    
    # 실행 결과
    sub_agent_results: Dict[str, Any]   # Sub-Agent별 결과
    
    # Self-RAG
    retrieval_quality: float            # 0.0~1.0
    retry_count: int                    # 최대 3
    rewritten_query: Optional[str]
    
    # 최종 응답
    final_answer: str
    sources: List[dict]                 # 인용 출처
    error: Optional[str]
```

---

## 3. Adaptive Router

### 난이도 분류 기준

| 난이도 | 조건 | 전략 |
|--------|------|------|
| simple | 단일 의도 + 키워드 명확 | Vector Search only (Qdrant) |
| medium | 단일 의도 + 자연어 질의 | Hybrid Search (Qdrant Vector + Elasticsearch BM25/nori + RRF) |
| complex | 복합 의도 or 비교/추론 필요 | Hybrid + Re-ranker + Query Rewriting |

### 분류 프롬프트
```python
ADAPTIVE_ROUTER_PROMPT = """
사용자 질의의 복잡도를 분석하여 분류하세요.

분류 기준:
- simple: 단순 사실 조회, 키워드가 명확함
  예) "오늘 환율은?", "유연탄 가격 알려줘"
- medium: 자연어 질의, 단일 의도
  예) "환경부 질소산화물 배출 기준이 뭐야?"
- complex: 복합 의도, 비교, 추론 필요
  예) "전년 대비 생산량과 환율 변동을 고려한 원가 분석해줘"

JSON 응답:
{"complexity": "simple|medium|complex", "reasoning": "..."}
"""
```

---

## 4. Orchestrator Agent

### 의도 분류 기준

| 의도 | 키워드 패턴 | 호출 Sub-Agent |
|------|-------------|----------------|
| market | 환율, 달러, 유연탄, 원가, 비용, 날씨, 기온, 강수, 수요 예측 | Market Agent |
| news | 뉴스, 최신, 동향, 시황 | News Agent |
| production | 생산량, 재고, 전년 대비, 실적 | ERP Agent |
| regulation | 규제, 기준, 법령, 적합, 허용치 | RAG Agent |
| manual | 매뉴얼, 절차, 방법, 양생 | RAG Agent |
| composite | 위 의도 2개 이상 혼합 | 다중 Sub-Agent 병렬 호출 |

> 날씨(weather) 의도는 Market Agent에 통합합니다.
> 날씨는 단독 질의보다 "날씨 → 수요 예측 → 원가 영향" 흐름으로 Market Agent와 함께 사용되는 경우가 대부분이기 때문입니다.
> `/weather/today` API 엔드포인트는 내부적으로 Market Agent를 통해 응답합니다.

### 분류 프롬프트
```python
ORCHESTRATOR_PROMPT = """
당신은 시멘트 제조업 AI 어시스턴트의 Orchestrator입니다.
사용자 질의를 분석하여 호출할 Sub-Agent를 결정하세요.

가능한 Sub-Agent:
- market_agent: 환율, 유연탄 가격, 원가 분석, 날씨 기반 수요 예측
- news_agent: 뉴스 수집 + 요약
- rag_agent: 규제 문서, 매뉴얼, 품질 기준 검색 (Vector + Graph)
- erp_agent: ERP 생산량, 재고, 실적 집계 분석

복합 질의는 여러 Agent를 동시에 호출할 수 있습니다.

JSON 응답:
{"sub_agents": ["market_agent", "news_agent"], "reasoning": "..."}
"""
```

---

## 5. Sub-Agent 스펙

### Market Agent
```python
입력:
  - query: str
  - date: str = "today"

내부 호출 Tool:
  - exchange_tool: 한국은행 환율
  - coal_price_tool: 유연탄 가격
  - weather_tool: 날씨 + 수요 예측

출력:
  {
    "usd_krw": 1380.0,
    "coal_price_usd": 142.5,
    "coal_price_krw": 196650.0,
    "weather": {"tmp": 18.0, "demand_forecast": "증가"},
    "summary": "원화 기준 유연탄 원가 전월 대비 +3.2%"
  }
```

### News Agent
```python
입력:
  - keywords: List[str] = ["시멘트", "건설 경기", "유연탄"]

내부 처리:
  1. 네이버 뉴스 API 병렬 호출
  2. Kafka llm.requests 발행 → LLM Consumer가 요약
  3. 요약 결과 수신 후 반환

출력:
  {
    "articles": [...],
    "summary": "시멘트 수요 둔화 우려 지속...",
    "trend": "negative"
  }
```

### RAG Agent
```python
입력:
  - query: str
  - top_k: int = 5

내부 분기:
  - 단순 키워드 → Vector Search (Qdrant)
  - 복합 규제 질의 → Graph Search (Neo4j Cypher)
  - 혼합 → Vector + Graph 결과 병합

출력:
  {
    "vector_results": [...],
    "graph_results": [...],
    "merged_chunks": [...]
  }
```

### ERP Agent
```python
입력:
  - query_type: str  # 'monthly_compare' / 'inventory' / 'trend'
  - period: str = "this_month"
  - product_type: str = None

내부 처리:
  PostgreSQL production_logs 집계 쿼리

출력:
  {
    "current": {"qty": 12500.0, "period": "2025-05"},
    "prev_month": {"qty": 11800.0, "change_pct": +5.9},
    "prev_year": {"qty": 13200.0, "change_pct": -5.3}
  }
```

---

## 6. A2A 프로토콜 인터페이스

```python
class A2AMessage(BaseModel):
    """Agent 간 표준 메시지 포맷"""
    sender: str                # 발신 Agent ID
    receiver: str              # 수신 Agent ID
    message_type: Literal["request", "response", "error"]
    payload: dict
    correlation_id: str        # 요청-응답 매칭
    timestamp: datetime

class BaseAgent(ABC):
    """모든 Sub-Agent 공통 인터페이스"""
    
    @abstractmethod
    async def handle(self, message: A2AMessage) -> A2AMessage:
        ...
    
    async def call_other_agent(
        self, 
        receiver: str, 
        payload: dict
    ) -> A2AMessage:
        """다른 Agent 호출"""
        ...
```

---

## 7. Self-RAG 재검색 루프

```python
async def self_rag_loop(state: AgentState, max_retries: int = 3):
    for attempt in range(max_retries):
        # 1. 검색 실행
        results = await retrieve(state["query"])
        
        # 2. 검색 결과 자가 평가
        quality = await evaluate_retrieval(
            query=state["query"],
            chunks=results
        )
        # quality: 0.0~1.0 (LLM이 판단)
        
        # 3. 충분하면 종료
        if quality >= 0.7:
            return results
        
        # 4. 부족하면 쿼리 재작성 후 재시도
        state["query"] = await rewrite_query(
            original=state["query"],
            failed_chunks=results
        )
        state["retry_count"] = attempt + 1
    
    # 최대 시도 후에도 실패 시 마지막 결과 반환
    return results
```

---

## 8. LangGraph 워크플로우 노드 구성

```python
graph = StateGraph(AgentState)

# 노드 등록
graph.add_node("adaptive_router",   adaptive_router)
graph.add_node("orchestrator",      orchestrator)
graph.add_node("market_agent",      market_agent)
graph.add_node("news_agent",        news_agent)
graph.add_node("rag_agent",         rag_agent)
graph.add_node("erp_agent",         erp_agent)
graph.add_node("self_rag",          self_rag_evaluator)
graph.add_node("synthesizer",       answer_synthesizer)

# 엣지 정의
graph.add_edge(START, "adaptive_router")
graph.add_edge("adaptive_router", "orchestrator")

# Orchestrator → 병렬 Sub-Agent 호출 (Send API)
graph.add_conditional_edges(
    "orchestrator",
    route_to_sub_agents,    # 의도 → Sub-Agent 매핑
    ["market_agent", "news_agent", "rag_agent", "erp_agent"]
)

# RAG Agent만 Self-RAG 루프 적용
graph.add_edge("rag_agent", "self_rag")
graph.add_conditional_edges(
    "self_rag",
    lambda s: "rag_agent" if s["retrieval_quality"] < 0.7 and s["retry_count"] < 3 else "synthesizer"
)

# 나머지 Sub-Agent는 바로 Synthesizer로
for agent in ["market_agent", "news_agent", "erp_agent"]:
    graph.add_edge(agent, "synthesizer")

graph.add_edge("synthesizer", END)
```

---

## 9. 복합 질의 병렬 처리 (LangGraph Send API)

```python
def route_to_sub_agents(state: AgentState):
    """Orchestrator가 분류한 Sub-Agent들을 병렬 실행"""
    return [
        Send(agent_name, {"query": state["query"]})
        for agent_name in state["sub_agents_to_call"]
    ]
```

**예시: "오늘 환율 기준 유연탄 원가랑 관련 뉴스 알려줘"**
```
Orchestrator → ["market_agent", "news_agent"]
    │
    ├─ market_agent 실행  ┐
    │                     ├─ 병렬 (Send API)
    └─ news_agent 실행    ┘
    │
    ▼
Synthesizer (두 결과 통합)
```

---

## 10. Answer Synthesizer

```python
SYNTHESIZER_PROMPT = """
당신은 시멘트 제조업 전문 AI 어시스턴트입니다.
아래 Sub-Agent 결과들을 바탕으로 사용자 질의에 답변하세요.

답변 원칙:
1. 수치 데이터는 정확히 인용 (출처 날짜 포함)
2. 규제 내용은 법령명과 조항 함께 언급
3. 불확실한 내용은 명시적으로 표현
4. 한국어로 간결하게 답변 (200자 이내 권장)
5. 데이터 출처는 답변 끝에 명시
"""

# LLM 백엔드는 LLM_BACKEND 환경변수로 결정
# - local: Ollama / vLLM (Gemma4)
# - bedrock: AWS Bedrock Claude
# - anthropic: Anthropic API
```
