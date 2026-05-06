# 개발 태스크 & 설계 문서 체크리스트

## 설계 문서 목록

설계 문서는 코드 작성 전에 완성해야 합니다.
코드를 짜다가 설계가 바뀌면 비용이 크기 때문에, 각 Phase 시작 전 해당 설계 문서를 먼저 확정합니다.

| 문서 | 파일 | 상태 | 선행 조건 |
|------|------|------|-----------|
| 데이터 흐름 설계 | `docs/01_data_flow.md` | ✅ | 없음 — 가장 먼저 |
| DB 스키마 설계 | `docs/02_db_schema.md` | ⬜ | 01 완료 후 |
| Agent 설계 | `docs/03_agent_design.md` | ⬜ | 01, 02 완료 후 |
| API 명세 | `docs/04_api_spec.md` | ⬜ | 03 완료 후 |
| 환경 설정 가이드 | `docs/05_env_setup.md` | ⬜ | 없음 — 병행 가능 |
| 검색 품질 평가 기준 | `docs/06_eval_criteria.md` | ⬜ | 02, 03 완료 후 |
| 모델 서빙 비교 설계 | `docs/07_model_serving.md` | ⬜ | 03 완료 후 |
| 성능 최적화 설계 | `docs/08_performance.md` | ⬜ | 04 완료 후 |

> 설계 문서 완료 기준: 코드 작성자가 문서만 보고 구현 가능한 수준

---

## Phase 0 — 설계 확정 (코드 없음)

> 목적: 나중에 설계가 바뀌어서 코드를 갈아엎는 일 방지

- [x] `docs/01_data_flow.md` 작성
  - 각 데이터 소스별 수집 흐름
  - 청킹 전략 결정 기준
  - 데이터 갱신 주기 및 캐시 전략
- [ ] `docs/02_db_schema.md` 작성
  - PostgreSQL 테이블 정의 (DDL 포함)
  - Qdrant 컬렉션 정의 (벡터 차원, payload 스키마)
  - 질의 유형별 데이터 접근 패턴
- [ ] `docs/03_agent_design.md` 작성
  - LangGraph 상태(State) 정의
  - Router 분류 기준 및 프롬프트
  - Tool별 입출력 스펙
  - 복합 질의 병렬 처리 전략 (LangGraph Send API)
- [ ] `docs/04_api_spec.md` 작성
  - 전체 엔드포인트 목록
  - 요청/응답 스키마 (Pydantic 모델 기준)
  - SSE(Server-Sent Events) 스트리밍 엔드포인트 설계
  - 에러 코드 정의
- [ ] `docs/05_env_setup.md` 작성
  - 필요한 API 키 목록 및 발급 방법
  - .env.example 파일 구성
  - Docker Compose 서비스 구성
- [ ] `docs/06_eval_criteria.md` 작성
  - RAG 검색 품질 평가 지표 (Faithfulness, Answer Relevancy, Context Recall)
  - RAGAS 프레임워크 활용 방법
  - 청킹 전략 A/B 비교 실험 설계
  - 골든 셋 구성 방법
- [ ] `docs/07_model_serving.md` 작성
  - Ollama vs vLLM 비교 실험 설계
  - 측정 지표: TPS, TTFT, 동시 요청 처리량
  - Gemma4 서빙 환경 구성
- [ ] `docs/08_performance.md` 작성
  - 비동기 처리 설계 (asyncio.gather 병렬 API 호출)
  - LangGraph 병렬 Tool 실행 설계 (Send API)
  - 순차 vs 병렬 응답 속도 측정 계획

---

## Phase 1 — 프로젝트 뼈대 세팅

> 목적: 이후 모든 코드가 들어갈 구조를 먼저 잡는다
> 선행 조건: Phase 0 완료

- [ ] Python 프로젝트 초기화
  - `pyproject.toml` 작성 (의존성 목록)
  - `.env.example` 작성
  - `.gitignore` 작성
- [ ] 디렉토리 구조 생성
  - `app/api/`, `app/agent/tools/`, `app/indexing/chunking/`
  - `app/data/collectors/`, `app/core/`, `app/evaluation/`
- [ ] Docker Compose 기초 구성
  - Qdrant 컨테이너
  - PostgreSQL 컨테이너
- [ ] `app/core/config.py` 작성
  - pydantic-settings 기반 환경변수 로딩
- [ ] DB 마이그레이션 스크립트 작성
  - `scripts/init_db.sql` — PostgreSQL DDL
  - `scripts/init_qdrant.py` — Qdrant 컬렉션 생성

---

## Phase 2 — 데이터 수집 레이어

> 목적: 실제 데이터가 들어오는 파이프라인 완성
> 선행 조건: Phase 1 완료, API 키 3개 발급 완료

- [ ] 한국은행 환율 API 수집기 (`app/data/collectors/exchange_api.py`)
  - async ECOS API 호출 (`httpx` 비동기 클라이언트)
  - PostgreSQL `market_rates` upsert
  - TTL 캐시 로직 (1시간)
- [ ] 네이버 뉴스 API 수집기 (`app/data/collectors/news_api.py`)
  - async 키워드별 뉴스 호출
  - 키워드 3개 **병렬** 호출 (`asyncio.gather`)
  - PostgreSQL `news_cache` upsert
  - TTL 캐시 로직 (30분)
- [ ] 기상청 API 수집기 (`app/data/collectors/weather_api.py`)
  - async 호출, 위경도 → 격자 좌표 변환
  - PostgreSQL `weather_cache` upsert
- [ ] 유연탄 가격 CSV 수집기 (`app/data/collectors/coal_price.py`)
  - CSV 파싱 및 PostgreSQL `coal_prices` upsert
- [ ] ERP 샘플 데이터 생성 (`app/data/samples/generate_erp.py`)
  - 현실적인 시멘트 생산량 데이터 생성 (2년치)
  - PostgreSQL `production_logs` insert
- [ ] 수집기 단위 테스트 작성

---

## Phase 3 — 인덱싱 파이프라인

> 목적: 문서를 Qdrant에 벡터로 저장
> 선행 조건: Phase 2 완료

- [ ] Embedding 모델 래퍼 (`app/indexing/embedding.py`)
  - `jhgan/ko-sroberta-multitask` 로딩
  - 배치 임베딩 처리
- [ ] Semantic chunking 구현 (`app/indexing/chunking/semantic.py`)
  - chunk_size: 512, overlap: 64
- [ ] Table-aware chunking 구현 (`app/indexing/chunking/table_aware.py`)
  - 헤더 + N행 단위 청킹
  - payload에 행 메타데이터 포함
- [ ] 환경부 PDF 인덱싱 (`app/data/collectors/regulation_pdf.py`)
- [ ] 유연탄 CSV 인덱싱
- [ ] 생산 매뉴얼 / 품질 기준서 인덱싱
- [ ] 인덱싱 파이프라인 오케스트레이터 (`app/indexing/pipeline.py`)
  - `--source all / regulation / coal / manual` 옵션

---

## Phase 4 — Hybrid Search + 검색 품질 고도화

> 목적: 검색 품질의 핵심 구현 + 수치 기반 성능 증명
> 선행 조건: Phase 3 완료

### 기본 구현
- [ ] Vector Search 기본 구현 (Qdrant cosine)
- [ ] BM25 Sparse Search 구현 (Qdrant sparse vector)
- [ ] RRF(Reciprocal Rank Fusion) 결합 구현

### 고도화 — Re-ranker
- [ ] Cross-Encoder Re-ranker 추가 (`app/indexing/reranker.py`)
  - 모델: `cross-encoder/ms-marco-MiniLM-L-6-v2`
  - Vector+BM25 상위 20개 → Re-ranker → 상위 5개 반환
  - 적용 전/후 검색 정밀도 비교 측정

### 고도화 — Query Rewriting
- [ ] Query Rewriting 구현 (`app/agent/query_rewriter.py`)
  - LLM으로 구어체 질의 → 검색 최적화 질의 변환
  - 예: "유연탄 요즘 얼마야?" → "유연탄 가격 최근 3개월 추이"
  - Rewriting 전/후 검색 품질 비교

### 평가 파이프라인
- [ ] 골든 셋 구성 (`app/evaluation/golden_set.json`)
  - 질의 20개 + 기대 정답 문서 매핑
- [ ] RAGAS 기반 평가 스크립트 (`app/evaluation/evaluate.py`)
  - Faithfulness, Answer Relevancy, Context Recall 측정
- [ ] 청킹 전략 A/B 비교 실험
  - chunk_size 256 vs 512 vs 1024 비교
  - overlap 0 vs 64 비교
  - 결과를 `docs/eval_results/` 에 저장

---

## Phase 5 — LangGraph Agent + 병렬 처리

> 목적: 질의 → 데이터 → 응답 전체 흐름 + 성능 최적화
> 선행 조건: Phase 2, 4 완료

### 기본 Agent 구현
- [ ] Router Agent 구현 (`app/agent/router.py`)
- [ ] 각 Tool 구현
  - [ ] `exchange_tool.py` — 환율 + 유연탄 원가 (async)
  - [ ] `news_tool.py` — 뉴스 수집 + LLM 요약 (async)
  - [ ] `weather_tool.py` — 날씨 + 수요 예측 (async)
  - [ ] `erp_tool.py` — 생산량 집계 분석 (async)
  - [ ] `regulation_tool.py` — 규제 문서 RAG
- [ ] Answer Synthesizer 구현 (`app/agent/synthesizer.py`)

### 고도화 — 병렬 Tool 실행
- [ ] LangGraph `Send` API로 복합 질의 병렬 처리 구현
  - 복합 질의 시 Tool들을 병렬 실행
  - 순차 실행 대비 응답 속도 측정 및 비교
  - 결과를 `docs/eval_results/parallel_perf.md` 에 기록

### 고도화 — Streaming 응답
- [ ] LangChain StreamingCallback 연결
- [ ] FastAPI SSE 엔드포인트 구현 (`POST /chat/stream`)
  - `StreamingResponse` + `text/event-stream`
  - 토큰 단위 실시간 출력

---

## Phase 6 — FastAPI 서버

> 목적: 외부에서 호출 가능한 API 서버 완성
> 선행 조건: Phase 5 완료

- [ ] FastAPI 앱 기본 구조 (`app/main.py`)
  - ApiResponse 공통 래퍼
  - GlobalExceptionHandler
  - CORS 설정
- [ ] 일반 엔드포인트 구현
  - [ ] `POST /chat` — 일반 질의응답
  - [ ] `POST /chat/compare` — 전년 대비 비교
  - [ ] `GET /market/today` — 환율 + 유연탄 원가
  - [ ] `GET /news/summary` — 최신 뉴스 요약
  - [ ] `GET /weather/today` — 날씨 + 수요 예측
  - [ ] `GET /regulations` — 규제 문서 검색
- [ ] **스트리밍 엔드포인트**
  - [ ] `POST /chat/stream` — SSE 토큰 스트리밍
- [ ] Swagger 문서 자동화 확인
- [ ] 통합 테스트 작성

---

## Phase 7 — 모델 서빙 비교 실험

> 목적: JD "vLLM 도입 예정" 직접 대응 + 블로그 소재
> 선행 조건: Phase 6 완료

- [ ] Ollama 환경 구성
  - Gemma4 모델 로컬 서빙
  - Docker Compose에 Ollama 서비스 추가
- [ ] vLLM 환경 구성 (GPU 서버 필요 시 Colab/RunPod 활용)
  - Gemma4 vLLM 서빙
  - continuous batching 설정
- [ ] 비교 측정 스크립트 (`scripts/benchmark_llm.py`)
  - 측정 지표: TPS(Tokens/sec), TTFT(Time To First Token)
  - 동시 요청 1 / 5 / 10개 시나리오
- [ ] 결과 정리 (`docs/eval_results/llm_serving_benchmark.md`)

---

## Phase 8 — 배포 & 포트폴리오 마무리

> 목적: 외부에서 접근 가능한 데모 환경 구성
> 선행 조건: Phase 7 완료

- [ ] Dockerfile 작성
- [ ] Docker Compose 전체 구성 (App + Qdrant + PostgreSQL + Ollama)
- [ ] AWS EC2 or Render 배포
- [ ] Streamlit 데모 UI 작성 (`streamlit_app.py`)
  - 스트리밍 응답 실시간 출력
  - 일반 vs 스트리밍 응답 비교 탭
- [ ] README 최종 정리
  - 설계 문서 링크
  - 실험 결과 요약 (검색 품질 / 응답 속도 / LLM 서빙)
- [ ] 기술 블로그 포스팅
  - [ ] 청킹 전략 A/B 비교 + RAGAS 평가 실험기
  - [ ] Re-ranker 도입 전후 검색 정밀도 비교
  - [ ] LangGraph Send API로 병렬 Tool 실행 구현하기
  - [ ] Ollama vs vLLM — Gemma4 서빙 성능 비교

---

## 의존 관계 요약

```
Phase 0 (설계)
    │
    ▼
Phase 1 (뼈대)
    │
    ├──────────────────┐
    ▼                  ▼
Phase 2 (수집)     Phase 3 (인덱싱)
    │                  │
    └────────┬──────────┘
             ▼
         Phase 4 (Hybrid Search + 평가)
             │
             ▼
         Phase 5 (Agent + 병렬 + 스트리밍)
             │
             ▼
         Phase 6 (FastAPI)
             │
             ▼
         Phase 7 (모델 서빙 비교)
             │
             ▼
         Phase 8 (배포 + 마무리)
```

## 고도화 항목 요약

| 항목 | Phase | 기술 | 어필 포인트 |
|------|-------|------|-------------|
| Re-ranker | 4 | Cross-Encoder | 검색 정밀도 수치 비교 |
| Query Rewriting | 4 | LLM 전처리 | 구어체 질의 대응 |
| RAGAS 평가 | 4 | Faithfulness / Relevancy | 설계 결정 수치로 증명 |
| 청킹 A/B 실험 | 4 | chunk_size / overlap 비교 | 블로그 소재 |
| 병렬 Tool 실행 | 5 | LangGraph Send API | 응답 속도 개선 수치 |
| SSE 스트리밍 | 5, 6 | FastAPI StreamingResponse | 실서비스 수준 UX |
| vLLM vs Ollama | 7 | TPS / TTFT 비교 | JD 직접 대응 |
