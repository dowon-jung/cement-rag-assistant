# 04. API 명세

## 1. 공통 응답 포맷

```python
class ApiResponse(BaseModel):
    success: bool
    data: Optional[Any] = None
    error: Optional[ErrorDetail] = None
    meta: Optional[dict] = None       # 페이지네이션, 처리 시간 등

class ErrorDetail(BaseModel):
    code: str                          # ERR_001 형식
    message: str
    details: Optional[dict] = None
```

### 성공 응답 예시
```json
{
  "success": true,
  "data": { "answer": "...", "sources": [...] },
  "meta": { "elapsed_ms": 1240, "agent_count": 2 }
}
```

### 에러 응답 예시
```json
{
  "success": false,
  "error": {
    "code": "ERR_RAG_001",
    "message": "검색 결과가 충분하지 않습니다",
    "details": { "retry_count": 3 }
  }
}
```

---

## 2. 엔드포인트 목록

| Method | Path | 설명 |
|--------|------|------|
| POST | `/chat` | 일반 질의응답 |
| POST | `/chat/stream` | SSE 토큰 스트리밍 |
| POST | `/chat/compare` | 전년 대비 비교 분석 |
| GET | `/market/today` | 환율 + 유연탄 원가 |
| GET | `/news/summary` | 최신 뉴스 요약 |
| GET | `/weather/today` | 날씨 + 수요 예측 |
| GET | `/regulations` | 규제 문서 검색 |
| GET | `/health` | 헬스체크 |
| GET | `/metrics` | Prometheus 메트릭 |

---

## 3. POST /chat

### 요청
```python
class ChatRequest(BaseModel):
    query: str
    session_id: Optional[str] = None
    context: Optional[dict] = None      # 추가 컨텍스트
```

### 응답
```python
class ChatResponse(BaseModel):
    answer: str
    sources: List[Source]
    agent_trace: List[AgentTrace]       # 디버깅용
    
class Source(BaseModel):
    type: Literal["regulation", "manual", "erp", "market", "news"]
    title: str
    excerpt: str
    metadata: dict

class AgentTrace(BaseModel):
    agent_name: str
    elapsed_ms: int
    status: Literal["success", "error"]
```

### 예시
```bash
POST /chat
{
  "query": "환경부 질소산화물 배출 기준이 뭐야?"
}

→ 200 OK
{
  "success": true,
  "data": {
    "answer": "환경부 기준에 따르면 질소산화물 배출 기준은 0.004kg/Sm³ 이하입니다.",
    "sources": [{
      "type": "regulation",
      "title": "대기환경보전법 시행규칙 별표",
      "excerpt": "질소산화물 배출허용기준은...",
      "metadata": {"law_name": "대기환경보전법", "page": 23}
    }],
    "agent_trace": [
      {"agent_name": "rag_agent", "elapsed_ms": 850, "status": "success"}
    ]
  }
}
```

---

## 4. POST /chat/stream (SSE)

### 요청
```python
# ChatRequest와 동일
```

### 응답 형식
```
Content-Type: text/event-stream

event: token
data: {"text": "환경부 "}

event: token
data: {"text": "기준에 "}

event: source
data: {"type": "regulation", "title": "..."}

event: done
data: {"elapsed_ms": 1240}
```

### 구현 예시
```python
@router.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    async def event_generator():
        async for token in agent.astream(req.query):
            yield f"event: token\ndata: {json.dumps({'text': token})}\n\n"
        yield "event: done\ndata: {}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )
```

---

## 5. POST /chat/compare

### 요청
```python
class CompareRequest(BaseModel):
    metric: Literal["production", "exchange", "coal_price"]
    period: Literal["month", "quarter", "year"]
    target_date: Optional[date] = None
```

### 응답
```python
class CompareResponse(BaseModel):
    metric: str
    current: PeriodData
    previous: PeriodData
    change_pct: float
    analysis: str                       # LLM 생성 분석 코멘트

class PeriodData(BaseModel):
    period: str
    value: float
    unit: str
```

---

## 6. GET /market/today

### 응답
```python
class MarketResponse(BaseModel):
    base_date: date
    usd_krw: float
    coal_price_usd: float
    coal_price_krw: float
    cost_change_pct: float
    cached: bool                        # 캐시 hit 여부
```

---

## 7. GET /news/summary

### 쿼리 파라미터
```python
keywords: Optional[List[str]] = ["시멘트", "건설 경기", "유연탄"]
limit: int = 10
```

### 응답
```python
class NewsResponse(BaseModel):
    articles: List[Article]
    summary: str                        # LLM 요약
    trend: Literal["positive", "neutral", "negative"]

class Article(BaseModel):
    title: str
    link: str
    description: str
    pub_date: datetime
```

---

## 8. GET /weather/today

### 쿼리 파라미터
```python
nx: int = 83
ny: int = 121
```

### 응답
```python
class WeatherResponse(BaseModel):
    forecast_date: date
    tmp: float
    pop: int
    wsd: float
    sky: int
    demand_forecast: Literal["증가", "유지", "감소"]
    reason: str
```

---

## 9. GET /regulations

### 쿼리 파라미터
```python
query: str
top_k: int = 5
use_graph: bool = False                 # GraphRAG 사용 여부
```

### 응답
```python
class RegulationResponse(BaseModel):
    chunks: List[RegulationChunk]
    graph_results: Optional[List[GraphResult]] = None

class RegulationChunk(BaseModel):
    text: str
    law_name: str
    article: str
    page: int
    score: float

class GraphResult(BaseModel):
    cypher_query: str
    related_articles: List[str]
    cascade_path: List[str]             # 연쇄 적용 경로
```

---

## 10. 에러 코드 정의

| 코드 | HTTP | 설명 |
|------|------|------|
| ERR_001 | 400 | 잘못된 요청 형식 |
| ERR_002 | 401 | 인증 실패 |
| ERR_003 | 429 | 요청 제한 초과 |
| ERR_DATA_001 | 503 | 외부 API 호출 실패 |
| ERR_DATA_002 | 503 | DB 연결 실패 |
| ERR_RAG_001 | 422 | 검색 결과 부족 |
| ERR_LLM_001 | 503 | LLM 백엔드 호출 실패 |
| ERR_LLM_002 | 408 | LLM 응답 타임아웃 |
| ERR_KAFKA_001 | 503 | Kafka Producer 실패 |
| ERR_INTERNAL | 500 | 내부 서버 에러 |

---

## 11. CORS 및 인증

```python
# CORS 설정
allow_origins = ["http://localhost:3000", "http://localhost:8501"]  # Streamlit
allow_credentials = True
allow_methods = ["GET", "POST"]
allow_headers = ["*"]

# 인증 (Phase 8 이후)
# - API 키 기반 (X-API-Key 헤더)
# - 또는 JWT (Authorization: Bearer)
```

---

## 12. Rate Limiting

```python
# slowapi 활용
@limiter.limit("60/minute")     # 일반 엔드포인트
@limiter.limit("10/minute")     # /chat (LLM 호출)
@limiter.limit("5/minute")      # /chat/stream
```
