# Agent 설계

## 1. 전체 흐름

```
사용자 질의
    │
    ▼
[Router Agent]
  질의 분류 → 어떤 Tool(들)을 호출할지 결정
    │
    ├─ 단일 Tool → 해당 Tool 직접 호출
    └─ 복합 질의 → Tool 순차 or 병렬 호출
    │
    ▼
[Tool 실행]
  각 Tool은 독립적으로 데이터 반환
    │
    ▼
[Answer Synthesizer]
  Tool 결과들을 LLM으로 통합 → 최종 응답 생성
    │
    ▼
사용자 응답
```

---

## 2. LangGraph 상태 정의

```python
class AgentState(TypedDict):
    query: str                        # 원본 사용자 질의
    intent: str                       # Router가 분류한 의도
    tools_to_call: List[str]          # 호출할 Tool 목록
    tool_results: Dict[str, Any]      # Tool별 실행 결과
    final_answer: str                 # 최종 응답
    error: Optional[str]              # 에러 메시지
```

---

## 3. Router Agent

### 분류 기준

| 의도 (intent) | 키워드 / 패턴 | 호출 Tool |
|---------------|---------------|-----------|
| `market_analysis` | 환율, 달러, 유연탄, 원가, 생산 비용 | `exchange_tool` + `coal_tool` |
| `news_summary` | 뉴스, 최신, 동향, 시황 | `news_tool` |
| `weather_forecast` | 날씨, 기온, 강수, 수요 예측 | `weather_tool` |
| `production_analysis` | 생산량, 재고, 전년 대비, 실적 | `erp_tool` |
| `regulation_search` | 규제, 기준, 법령, 허용치, 적합 | `regulation_tool` |
| `manual_search` | 매뉴얼, 방법, 절차, 기준서 | `hybrid_search_tool` |
| `composite` | 위 의도 2개 이상 혼합 | 복수 Tool 조합 |

### 프롬프트 설계

```python
ROUTER_SYSTEM_PROMPT = """
당신은 시멘트 제조업 AI 어시스턴트의 라우터입니다.
사용자 질의를 분석하여 아래 의도 중 하나 또는 여러 개로 분류하세요.

가능한 의도:
- market_analysis: 환율, 유연탄 가격, 생산 원가 관련
- news_summary: 시멘트/건설 업계 최신 뉴스
- weather_forecast: 날씨 및 시멘트 수요 예측
- production_analysis: ERP 생산량, 재고, 실적 분석
- regulation_search: 환경부 규제, 법령 기준 검색
- manual_search: 생산 매뉴얼, 품질 기준서 검색

반드시 JSON 형식으로만 응답하세요:
{"intent": ["market_analysis"], "reasoning": "환율 관련 질의이므로"}
"""
```

---

## 4. Tool 스펙

### exchange_tool (환율 + 원가 분석)

```python
입력:
  - query: str          # 원본 질의 (컨텍스트용)
  - date: str = "today" # 조회 날짜

처리:
  1. PostgreSQL market_rates 캐시 확인 (TTL 1시간)
  2. 캐시 miss → 한국은행 ECOS API 호출 → 캐시 저장
  3. coal_prices 테이블에서 최근 유연탄 가격 조회
  4. 원화 기준 유연탄 원가 계산 (price_usd × rate)

출력:
  {
    "usd_krw": 1380.0,
    "coal_price_usd": 142.5,      # $/톤
    "coal_price_krw": 196650.0,   # 원/톤
    "base_date": "2025-05-06",
    "cost_change_pct": +3.2       # 전월 대비 변동률
  }
```

---

### news_tool (뉴스 수집 + 요약)

```python
입력:
  - keywords: List[str] = ["시멘트", "건설 경기", "유연탄"]
  - display: int = 10

처리:
  1. PostgreSQL news_cache 확인 (TTL 30분)
  2. 캐시 miss → 네이버 뉴스 API 호출 → 캐시 저장
  3. LLM으로 뉴스 헤드라인 요약 (3줄 이내)

출력:
  {
    "articles": [{"title": ..., "link": ..., "pub_date": ...}],
    "summary": "시멘트 수요 둔화 우려가 지속되는 가운데..."
  }
```

---

### weather_tool (날씨 + 수요 예측)

```python
입력:
  - nx: int = 60        # 기상청 격자 (서울 기본값)
  - ny: int = 127
  - date: str = "today"

처리:
  1. PostgreSQL weather_cache 확인 (TTL 1시간)
  2. 캐시 miss → 기상청 API 호출 → 캐시 저장
  3. 기온·강수확률 기반 수요 예측 (규칙 기반)
     - 기온 < 5°C or 강수 > 60% → 수요 감소 예측
     - 기온 15~25°C, 강수 < 30% → 수요 증가 예측

출력:
  {
    "tmp": 18.0,
    "pop": 20,
    "sky": 1,
    "demand_forecast": "증가",
    "reason": "양호한 날씨로 건설 현장 작업 가능"
  }
```

---

### erp_tool (생산·재고 분석)

```python
입력:
  - query_type: str     # 'monthly_compare', 'inventory', 'trend'
  - period: str = "this_month"
  - product_type: str = None   # 특정 품종 필터

처리:
  1. PostgreSQL production_logs 집계 쿼리
  2. query_type에 따라 SQL 분기
     - monthly_compare: 전월/전년 동월 비교
     - inventory: 현재 재고 현황
     - trend: 최근 N개월 추이

출력:
  {
    "current": {"qty": 12500.0, "period": "2025-05"},
    "prev_month": {"qty": 11800.0, "change_pct": +5.9},
    "prev_year": {"qty": 13200.0, "change_pct": -5.3}
  }
```

---

### regulation_tool (규제 문서 RAG)

```python
입력:
  - query: str          # 규제 관련 질의
  - top_k: int = 5

처리:
  1. query 임베딩 생성 (ko-sroberta)
  2. Qdrant "regulations" 컬렉션 Hybrid Search
     - Vector Search (의미 유사도)
     - BM25 Sparse Search (키워드 매칭)
     - RRF로 결과 통합
  3. 상위 K개 청크 반환

출력:
  {
    "chunks": [
      {
        "text": "질소산화물 배출 기준...",
        "law_name": "대기환경보전법",
        "page": 23,
        "score": 0.91
      }
    ]
  }
```

---

### hybrid_search_tool (통합 문서 검색)

```python
입력:
  - query: str
  - collections: List[str] = ["manuals", "quality_standards", "regulations"]
  - top_k: int = 5

처리:
  1. 지정된 컬렉션 전체에 Hybrid Search
  2. 컬렉션 간 점수 정규화
  3. 통합 랭킹 반환

출력:
  {
    "results": [
      {
        "collection": "manuals",
        "text": "...",
        "score": 0.88,
        "metadata": {...}
      }
    ]
  }
```

---

## 5. Answer Synthesizer

```python
SYNTHESIZER_SYSTEM_PROMPT = """
당신은 시멘트 제조업 전문 AI 어시스턴트입니다.
아래 Tool 실행 결과들을 바탕으로 사용자 질의에 답변하세요.

답변 원칙:
1. 수치 데이터는 정확히 인용 (출처 날짜 포함)
2. 규제 내용은 법령명과 조항 함께 언급
3. 불확실한 내용은 명시적으로 표현
4. 한국어로 간결하게 답변 (200자 이내 권장)
"""
```

---

## 6. LangGraph 워크플로우 노드 구성

```python
# 노드 정의
graph.add_node("router",      router_agent)
graph.add_node("exchange",    exchange_tool)
graph.add_node("news",        news_tool)
graph.add_node("weather",     weather_tool)
graph.add_node("erp",         erp_tool)
graph.add_node("regulation",  regulation_tool)
graph.add_node("hybrid",      hybrid_search_tool)
graph.add_node("synthesizer", answer_synthesizer)

# 엣지 정의
graph.add_edge(START, "router")

graph.add_conditional_edges(
    "router",
    route_to_tools,          # intent → Tool 매핑 함수
    {
        "exchange":   "exchange",
        "news":       "news",
        "weather":    "weather",
        "erp":        "erp",
        "regulation": "regulation",
        "hybrid":     "hybrid",
    }
)

# 모든 Tool → synthesizer
for tool in ["exchange", "news", "weather", "erp", "regulation", "hybrid"]:
    graph.add_edge(tool, "synthesizer")

graph.add_edge("synthesizer", END)
```

---

## 7. 복합 질의 처리 전략

복합 의도 감지 시 Tool을 순차 실행합니다.

**예시: "오늘 환율 기준 유연탄 원가랑 관련 뉴스 알려줘"**

```
Router → intent: ["market_analysis", "news_summary"]
    │
    ├─ exchange_tool 실행 → {usd_krw, coal_price_krw, ...}
    ├─ news_tool 실행     → {articles, summary}
    │
    ▼
Synthesizer → 두 결과 통합하여 최종 응답 생성
```

병렬 실행은 Phase 4에서 LangGraph의 `Send` API로 확장 예정.
