# 🏭 시멘트 제조업 특화 Hybrid RAG 어시스턴트

> 실시간 REST API(환율 · 뉴스 · 날씨)와 문서 RAG(환경 규제 · 유연탄 가격)를 결합한  
> **FastAPI + LangChain + LangGraph + Qdrant** 기반 도메인 특화 AI 어시스턴트

---

## 📌 프로젝트 개요

시멘트 제조 현장에서 실제로 발생하는 질의 유형을 중심으로 설계한 AI 어시스턴트입니다.  
단순 문서 검색 챗봇이 아니라, **질의 유형에 따라 데이터 소스와 처리 전략이 분기**되는 Multi-Tool Agent 구조를 채택했습니다.

### 예시 질의

```
"오늘 환율이랑 유연탄 가격 기준으로 이번 달 생산 원가 어때?"
"시멘트 관련 최신 뉴스 요약하고 수요 전망 알려줘"
"이번 달 생산량 vs 전년 비교해줘"
"환경부 규제 기준에 우리 공장 적합한가?"
"오늘 날씨 기준으로 시멘트 수요 예측해줘"
```

---

## 🏗 시스템 아키텍처

```
┌──────────────────────────────────────────────────────────────────┐
│                          데이터 소스                              │
│  [실시간 REST API]               [문서 RAG]      [사내 데이터]    │
│  한국은행 환율 API          +   환경부 규제 PDF  + 생산 매뉴얼    │
│  네이버 뉴스 검색 API       +   유연탄 가격 CSV  + ERP 리포트     │
│  기상청 단기예보 API                              + 품질검사 기준 │
└─────────────┬────────────────────────┬────────────────────────────┘
              │    인덱싱 파이프라인    │
              ▼                        ▼
┌──────────────────────────────────────────────────────────────────┐
│  문서 전처리 → Embedding (ko-sroberta) → Qdrant / PostgreSQL     │
│  유형별 청킹 전략 분기                                            │
│  • PDF 규제 문서  → Semantic chunking (512 token, overlap 64)    │
│  • 유연탄 CSV     → Table-aware chunking (행·열 구조 보존)       │
│  • 실시간 API     → Structured store (청킹 없이 DB 직접 저장)    │
└─────────────┬────────────────────────────────────────────────────┘
              │
              ▼
┌──────────────────────────────────────────────────────────────────┐
│                    LangGraph Agent 레이어                         │
│                                                                  │
│  [Router Agent] ──→ [환율 Tool]     → 원가 분석                  │
│       질의 분류 ──→ [뉴스 Tool]     → 최신 뉴스 요약             │
│                ──→ [날씨 Tool]      → 수요 예측                  │
│                ──→ [ERP Tool]       → 생산 분석                  │
│                ──→ [규제 Tool]      → 문서 검색                  │
│                ──→ [Hybrid Search]  → 벡터 + BM25                │
│                            ↓                                     │
│               [Answer Synthesizer: Gemma4 / Claude API]          │
└─────────────┬────────────────────────────────────────────────────┘
              │
              ▼
┌──────────────────────────────────────────────────────────────────┐
│                        FastAPI 서버                               │
│  POST /chat             일반 질의응답                             │
│  POST /chat/compare     전년 대비 비교 분석                       │
│  GET  /market/today     환율 + 유연탄 가격 + 원가 분석           │
│  GET  /news/summary     최신 시멘트 뉴스 요약                    │
│  GET  /weather/today    날씨 + 시멘트 수요 예측                  │
│  GET  /regulations      환경부 규제 문서 검색                    │
└─────────────┬────────────────────────────────────────────────────┘
              │
              ▼
     Streamlit UI / Swagger Docs / Docker 배포
```

---

## 🛠 기술 스택

| 레이어 | 기술 |
|--------|------|
| **Backend** | Python 3.11, FastAPI, Uvicorn |
| **Agent / RAG** | LangChain, LangGraph |
| **Embedding** | `jhgan/ko-sroberta-multitask` (한국어 특화) |
| **Vector DB** | Qdrant (Docker 로컬 + Cloud 무료 티어) |
| **RDB** | PostgreSQL (수치 · ERP 데이터 전용) |
| **LLM** | Gemma4 (vLLM/Ollama 로컬 서빙) + Claude API (비교 실험) |
| **실시간 API** | 한국은행 ECOS API, 네이버 뉴스 검색 API, 기상청 Open API |
| **문서 데이터** | 환경부 법령 PDF, 한국자원정보서비스 유연탄 가격 CSV |
| **Infra** | Docker, Docker Compose, AWS EC2 or Render |
| **UI** | Streamlit (데모), FastAPI Swagger (API 문서) |

---

## 📁 프로젝트 구조

```
cement-rag-assistant/
├── app/
│   ├── main.py                    # FastAPI 앱 진입점
│   ├── api/
│   │   ├── chat.py                # /chat 엔드포인트
│   │   ├── market.py              # /market 엔드포인트 (환율 + 유연탄)
│   │   ├── news.py                # /news 엔드포인트
│   │   ├── weather.py             # /weather 엔드포인트
│   │   └── regulations.py        # /regulations 엔드포인트
│   ├── agent/
│   │   ├── graph.py               # LangGraph 워크플로우 정의
│   │   ├── router.py              # Router Agent (질의 분류)
│   │   ├── tools/
│   │   │   ├── exchange_tool.py   # 한국은행 환율 API + 원가 분석
│   │   │   ├── news_tool.py       # 네이버 뉴스 검색 + 요약
│   │   │   ├── weather_tool.py    # 기상청 API + 수요 예측
│   │   │   ├── erp_tool.py        # ERP 데이터 검색 · 집계
│   │   │   ├── regulation_tool.py # 규제 문서 RAG
│   │   │   └── hybrid_search.py   # 벡터 + BM25 Hybrid Search
│   │   └── synthesizer.py         # Answer Synthesizer
│   ├── indexing/
│   │   ├── pipeline.py            # 인덱싱 파이프라인 오케스트레이터
│   │   ├── chunking/
│   │   │   ├── semantic.py        # Semantic chunking
│   │   │   ├── table_aware.py     # Table-aware chunking
│   │   │   └── structured.py      # 구조화 데이터 저장
│   │   └── embedding.py           # Embedding 모델 래퍼
│   ├── data/
│   │   ├── collectors/
│   │   │   ├── exchange_api.py    # 한국은행 ECOS API 수집
│   │   │   ├── news_api.py        # 네이버 뉴스 API 수집
│   │   │   ├── weather_api.py     # 기상청 API 수집
│   │   │   ├── coal_price.py      # 유연탄 가격 CSV 수집
│   │   │   └── regulation_pdf.py  # 환경부 문서 크롤링
│   │   └── samples/               # 시뮬레이션용 샘플 데이터 (ERP 등)
│   └── core/
│       ├── config.py              # 환경변수 · 설정
│       └── dependencies.py        # FastAPI DI 컨테이너
├── streamlit_app.py               # Streamlit 데모 UI
├── docker-compose.yml             # Qdrant + PostgreSQL + App
├── Dockerfile
├── pyproject.toml
└── README.md
```

---

## 🚀 빠른 시작

### 사전 요구사항

- Python 3.11+
- Docker & Docker Compose
- API 키 3개 (아래 발급 안내 참고)

### API 키 발급

| API | 발급 URL |
|-----|---------|
| 한국은행 ECOS | [ecos.bok.or.kr](https://ecos.bok.or.kr/api/#/DevGuide/TopPage) |
| 네이버 검색 | [developers.naver.com](https://developers.naver.com/apps/#/register) |
| 기상청 Open API | [data.go.kr](https://data.go.kr) → "단기예보" 검색 |

### 환경 설정

```bash
git clone https://github.com/dowon-jung/cement-rag-assistant.git
cd cement-rag-assistant

cp .env.example .env
# .env 에 발급받은 API 키 입력
# BOK_API_KEY=...
# NAVER_CLIENT_ID=...
# NAVER_CLIENT_SECRET=...
# WEATHER_API_KEY=...
# ANTHROPIC_API_KEY=...  (선택)
```

### 실행

```bash
# Qdrant + PostgreSQL 컨테이너 시작
docker-compose up -d qdrant postgres

# 패키지 설치
pip install -e ".[dev]"

# 인덱싱 파이프라인 실행 (최초 1회)
python -m app.indexing.pipeline --source all

# FastAPI 서버 실행
uvicorn app.main:app --reload

# Streamlit 데모 실행 (별도 터미널)
streamlit run streamlit_app.py
```

API 문서: `http://localhost:8000/docs`

---

## 🔬 핵심 설계 결정

### 1. 청킹 전략 분기 — 왜 데이터마다 다른가?

| 데이터 유형 | 전략 | 이유 |
|------------|------|------|
| PDF 규제 문서 | Semantic chunking | 설명 문장이 맥락 단위로 이어지므로 의미 경계에서 분할 |
| 유연탄 가격 CSV | Table-aware chunking | 행·열 관계 파괴 시 수치 의미 손실 |
| 실시간 API 응답 | Structured store | 집계 연산(평균·증감률)은 SQL이 벡터 검색보다 정확 |

### 2. Hybrid Search — 벡터만으로 부족한 이유

규제 문서에서 "질소산화물 배출 기준 0.004kg/Sm³" 같은 수치 조건은 벡터 유사도로 정확히 매칭하기 어렵습니다.  
**BM25(키워드) + 벡터(의미)** 점수를 RRF(Reciprocal Rank Fusion)로 결합해 검색 정밀도를 높였습니다.

### 3. 환율 + 유연탄 조합 — 왜 이 두 가지인가?

시멘트 제조 원가에서 유연탄이 차지하는 비중은 약 30~40%이며, 유연탄은 달러로 거래됩니다.  
한국은행 환율 API와 유연탄 가격을 결합하면 **"원화 기준 실질 원가 변동"** 을 실시간으로 계산할 수 있어  
단순 날씨 예측보다 비즈니스 임팩트가 큰 질의응답이 가능합니다.

### 4. LangGraph Router — 왜 단순 Chain이 아닌가?

질의에 따라 실시간 API 호출, DB 집계, RAG 검색이 혼합되어야 합니다.  
LangGraph의 상태 그래프 구조로 각 Tool의 실행 조건과 순서를 명시적으로 제어합니다.

---

## 📊 개발 로드맵

```
Phase 1 (1~3주)   데이터 수집 & 전처리 파이프라인
                  ⬜ 한국은행 환율 API 연동
                  ⬜ 네이버 뉴스 검색 API 연동
                  ⬜ 기상청 API 연동
                  ⬜ 환경부 PDF 크롤링
                  ⬜ 유연탄 가격 CSV 수집
                  ⬜ ERP 샘플 데이터 생성
                  ⬜ 청킹 전략 구현

Phase 2 (4~7주)   RAG 파이프라인 구축
                  ⬜ ko-sroberta Embedding 연동
                  ⬜ Qdrant 컬렉션 설계 및 인덱싱
                  ⬜ Hybrid Search (BM25 + Vector) 구현
                  ⬜ 검색 품질 평가 (MRR, NDCG)

Phase 3 (8~10주)  FastAPI 서버 완성
                  ⬜ 전체 엔드포인트 구현
                  ⬜ ApiResponse 래퍼, GlobalExceptionHandler
                  ⬜ Swagger 문서 자동화

Phase 4 (11~13주) LangGraph Agent 구조
                  ⬜ Router Agent 구현
                  ⬜ 6개 Tool 구현 및 통합
                  ⬜ Gemma4 로컬 서빙 (vLLM/Ollama)
                  ⬜ Claude API 비교 실험

Phase 5 (14주)    배포 & 포트폴리오 정리
                  ⬜ Docker Compose 구성
                  ⬜ EC2 or Render 배포
                  ⬜ Streamlit 데모 UI
                  ⬜ 기술 블로그 포스팅
```

---

## 🔮 향후 개선 계획

- **Graph DB 연동**: 규제 항목 간 의존 관계를 Neo4j로 구조화하여 복합 규제 질의 지원
- **vLLM 모델 서빙**: 추론 속도 최적화 및 배치 처리
- **평가 파이프라인 자동화**: RAGAS 프레임워크로 검색·생성 품질 지속 측정
- **MCP / A2A 연동**: 외부 에이전트와의 표준 프로토콜 기반 협업

---

## 📄 라이선스

MIT License

---

> **관련 포스팅**
> - [청킹 전략별 검색 품질 비교 실험기](#) *(작성 예정)*
> - [LangGraph로 Multi-Tool RAG 구현하기](#) *(작성 예정)*
> - [환율 + 유연탄 가격으로 시멘트 원가 분석하기](#) *(작성 예정)*
