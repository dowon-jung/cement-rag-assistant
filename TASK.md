# 개발 태스크 & 설계 문서 체크리스트

## 설계 문서 목록

설계 문서는 코드 작성 전에 완성해야 합니다.
코드를 짜다가 설계가 바뀌면 비용이 크기 때문에, 각 Phase 시작 전 해당 설계 문서를 먼저 확정합니다.

| # | 문서 | 파일 | 상태 | 선행 조건 |
|---|------|------|------|-----------|
| 01 | 데이터 흐름 설계 | `docs/01_data_flow.md` | ✅ | 없음 |
| 02 | DB 스키마 설계 | `docs/02_db_schema.md` | ⬜ | 01 |
| 03 | Agent 설계 | `docs/03_agent_design.md` | ⬜ | 01, 02 |
| 04 | API 명세 | `docs/04_api_spec.md` | ⬜ | 03 |
| 05 | 환경 설정 가이드 | `docs/05_env_setup.md` | ⬜ | 없음 |
| 06 | 검색 품질 평가 기준 | `docs/06_eval_criteria.md` | ⬜ | 02, 03 |
| 07 | 모델 서빙 비교 설계 | `docs/07_model_serving.md` | ⬜ | 03 |
| 08 | 성능 최적화 설계 | `docs/08_performance.md` | ⬜ | 04 |
| 09 | GraphRAG 설계 | `docs/09_graph_rag.md` | ⬜ | 02, 03 |
| 10 | Multi-Agent A2A 설계 | `docs/10_multi_agent.md` | ⬜ | 03 |
| 11 | 모니터링 설계 | `docs/11_monitoring.md` | ⬜ | 04 |

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
  - Neo4j 그래프 노드/엣지 스키마
  - Redis 캐시 키 설계
  - 질의 유형별 데이터 접근 패턴
- [ ] `docs/03_agent_design.md` 작성
  - LangGraph 상태(State) 정의
  - Router 분류 기준 및 프롬프트
  - Tool별 입출력 스펙
  - Multi-Agent A2A 구조 설계
  - 복합 질의 병렬 처리 전략 (LangGraph Send API)
  - Self-RAG 재검색 루프 설계
  - Adaptive RAG 전략 분기 설계
- [ ] `docs/04_api_spec.md` 작성
  - 전체 엔드포인트 목록
  - 요청/응답 스키마 (Pydantic 모델 기준)
  - SSE 스트리밍 엔드포인트 설계
  - 에러 코드 정의
- [ ] `docs/05_env_setup.md` 작성
  - 필요한 API 키 목록 및 발급 방법
  - .env.example 파일 구성
  - Docker Compose 전체 서비스 구성
- [ ] `docs/06_eval_criteria.md` 작성
  - RAGAS 지표 (Faithfulness, Answer Relevancy, Context Recall)
  - 청킹 전략 A/B 비교 실험 설계
  - Re-ranker 도입 전후 비교 설계
  - 골든 셋 구성 방법
- [ ] `docs/07_model_serving.md` 작성
  - Ollama vs vLLM 비교 실험 설계
  - 측정 지표: TPS, TTFT, 동시 요청 처리량
- [ ] `docs/08_performance.md` 작성
  - 비동기 처리 설계 (asyncio + httpx)
  - LangGraph 병렬 Tool 실행 (Send API)
  - 순차 vs 병렬 응답 속도 측정 계획
- [ ] `docs/09_graph_rag.md` 작성
  - Neo4j 도입 목적 및 적용 범위
  - 규제 문서 그래프 구조 설계
  - Vector RAG + Graph RAG 결합 전략
- [ ] `docs/10_multi_agent.md` 작성
  - Orchestrator + Sub-Agent 구조 설계
  - A2A 프로토콜 인터페이스 정의
  - Agent 간 상태 전달 방식
- [ ] `docs/11_monitoring.md` 작성
  - Prometheus 메트릭 정의
  - Grafana 대시보드 구성
  - LangSmith 트레이싱 설정

---

## Phase 1 — 프로젝트 뼈대 세팅

> 목적: 이후 모든 코드가 들어갈 구조를 먼저 잡는다
> 선행 조건: Phase 0 완료

- [ ] Python 프로젝트 초기화
  - `pyproject.toml` 작성 (의존성 목록)
  - `.env.example` 작성
  - `.gitignore` 작성
- [ ] 디렉토리 구조 생성
  - `app/api/`, `app/agent/tools/`, `app/agent/sub_agents/`
  - `app/indexing/chunking/`, `app/data/collectors/`
  - `app/core/`, `app/evaluation/`, `app/monitoring/`
- [ ] Docker Compose 기초 구성
  - Qdrant, PostgreSQL, Redis, Neo4j 컨테이너
- [ ] `app/core/config.py` 작성
  - pydantic-settings 기반 환경변수 로딩
- [ ] DB 초기화 스크립트
  - `scripts/init_db.sql` — PostgreSQL DDL
  - `scripts/init_qdrant.py` — Qdrant 컬렉션 생성
  - `scripts/init_neo4j.py` — Neo4j 제약조건 및 인덱스 생성
  - `scripts/init_redis.py` — Redis 연결 확인

---

## Phase 2 — 데이터 수집 레이어

> 목적: 실제 데이터가 들어오는 파이프라인 완성
> 선행 조건: Phase 1 완료, API 키 발급 완료

- [ ] 한국은행 환율 API 수집기 (`app/data/collectors/exchange_api.py`)
  - async ECOS API 호출 (httpx)
  - **Redis** TTL 캐시 (1시간) → PostgreSQL 영구 저장
- [ ] 네이버 뉴스 API 수집기 (`app/data/collectors/news_api.py`)
  - 키워드 3개 **asyncio.gather 병렬** 호출
  - **Redis** TTL 캐시 (30분) → PostgreSQL 영구 저장
- [ ] 기상청 API 수집기 (`app/data/collectors/weather_api.py`)
  - async 호출, 위경도 → 격자 좌표 변환
  - **Redis** TTL 캐시 (1시간)
- [ ] 유연탄 가격 CSV 수집기 (`app/data/collectors/coal_price.py`)
- [ ] ERP 샘플 데이터 생성 (`app/data/samples/generate_erp.py`)
  - 2년치 일별 생산·재고 데이터 생성
- [ ] 수집기 단위 테스트 작성

---

## Phase 3 — 인덱싱 파이프라인

> 목적: 문서를 Qdrant에 벡터로 저장
> 선행 조건: Phase 2 완료

- [ ] Embedding 모델 래퍼 (`app/indexing/embedding.py`)
  - `jhgan/ko-sroberta-multitask` 로딩, 배치 처리
- [ ] Semantic chunking (`app/indexing/chunking/semantic.py`)
  - chunk_size: 512, overlap: 64
- [ ] Table-aware chunking (`app/indexing/chunking/table_aware.py`)
  - 헤더 + N행 단위, payload에 메타데이터 포함
- [ ] 환경부 PDF, 유연탄 CSV, 매뉴얼/기준서 인덱싱
- [ ] 인덱싱 파이프라인 오케스트레이터 (`app/indexing/pipeline.py`)

---

## Phase 4 — Hybrid Search + 검색 품질 고도화

> 목적: 검색 품질 핵심 구현 + 수치 기반 성능 증명
> 선행 조건: Phase 3 완료

### 기본 Hybrid Search
- [ ] Vector Search (Qdrant cosine)
- [ ] BM25 Sparse Search (Qdrant sparse vector)
- [ ] RRF(Reciprocal Rank Fusion) 결합

### Re-ranker
- [ ] Cross-Encoder Re-ranker (`app/indexing/reranker.py`)
  - 모델: `cross-encoder/ms-marco-MiniLM-L-6-v2`
  - 상위 20개 → Re-ranker → 상위 5개
  - 도입 전/후 정밀도 비교 측정

### Query Rewriting
- [ ] Query Rewriting (`app/agent/query_rewriter.py`)
  - LLM으로 구어체 → 검색 최적화 질의 변환
  - Rewriting 전/후 검색 품질 비교

### RAGAS 평가 파이프라인
- [ ] 골든 셋 구성 (`app/evaluation/golden_set.json`, 질의 20개)
- [ ] RAGAS 평가 스크립트 (`app/evaluation/evaluate.py`)
  - Faithfulness, Answer Relevancy, Context Recall
- [ ] 청킹 A/B 비교 실험
  - chunk_size 256 vs 512 vs 1024
  - overlap 0 vs 64 비교
  - 결과: `docs/eval_results/chunking_ab_test.md`

---

## Phase 5 — GraphRAG (Neo4j)

> 목적: 벡터 검색으로 불가능한 복합 규제 질의 처리
> 선행 조건: Phase 3 완료
> JD 대응: "Graph DB 도입 예정"

- [ ] 규제 문서 → Neo4j 그래프 변환 (`app/indexing/graph_indexer.py`)
  - 노드: 법령, 조항, 수치기준, 오염물질
  - 엣지: CONTAINS(법령→조항), REGULATES(조항→수치기준), APPLIES_TO(기준→오염물질)
- [ ] Cypher 쿼리 기반 규제 탐색 (`app/agent/tools/graph_tool.py`)
  - 연쇄 규제 조항 탐색
  - 복합 조건 질의 처리
- [ ] Vector RAG + Graph RAG 결합 전략 구현
  - 단순 질의 → Vector RAG
  - 복합 규제 질의 → Graph RAG
  - 혼합 질의 → 두 결과 병합 후 Synthesizer
- [ ] 비교 실험: Vector only vs GraphRAG vs 결합
  - 결과: `docs/eval_results/graph_rag_eval.md`

---

## Phase 6 — Multi-Agent A2A 구조

> 목적: 단일 Agent → 전문화된 Sub-Agent 분리
> 선행 조건: Phase 5 완료
> JD 대응: "Multi-Agent 구조 확장 및 A2A 기반 연동"

- [ ] Orchestrator Agent 구현 (`app/agent/orchestrator.py`)
  - 질의 수신 → Sub-Agent 라우팅 → 결과 통합
- [ ] Sub-Agent 구현
  - [ ] Market Agent (`app/agent/sub_agents/market_agent.py`)
    - 환율 + 유연탄 + 원가 분석 전담
  - [ ] News Agent (`app/agent/sub_agents/news_agent.py`)
    - 뉴스 수집 + 요약 전담
  - [ ] RAG Agent (`app/agent/sub_agents/rag_agent.py`)
    - 문서 검색 (Vector + Graph) 전담
  - [ ] ERP Agent (`app/agent/sub_agents/erp_agent.py`)
    - 생산·재고 분석 전담
- [ ] A2A 인터페이스 정의 (`app/agent/a2a_protocol.py`)
  - Agent 간 표준 메시지 포맷
  - 비동기 Agent 호출 인터페이스
- [ ] Orchestrator → Sub-Agent 병렬 호출 구현
  - LangGraph Send API 활용

---

## Phase 7 — Adaptive RAG + Self-RAG

> 목적: 질의 복잡도에 따른 동적 검색 전략
> 선행 조건: Phase 4, 5, 6 완료

### Adaptive RAG
- [ ] 질의 난이도 분류기 구현 (`app/agent/adaptive_router.py`)
  - 단순 질의 → Vector Search only (빠름)
  - 중간 질의 → Hybrid Search
  - 복잡 질의 → Hybrid + Re-ranker + Query Rewriting
- [ ] 전략별 응답 속도 및 품질 측정
  - 결과: `docs/eval_results/adaptive_rag_eval.md`

### Self-RAG
- [ ] 검색 결과 자가 평가 구현 (`app/agent/self_rag.py`)
  - LLM이 검색 결과 충분성 판단
  - 불충분 시 쿼리 수정 후 재검색 (최대 3회)
  - 재검색 루프 추적 로깅
- [ ] Self-RAG 도입 전후 Faithfulness 비교
  - 결과: `docs/eval_results/self_rag_eval.md`

---

## Phase 8 — FastAPI 서버 + SSE 스트리밍

> 목적: 외부 호출 가능한 API + 실서비스 수준 UX
> 선행 조건: Phase 7 완료

- [ ] FastAPI 앱 기본 구조 (`app/main.py`)
  - ApiResponse 공통 래퍼
  - GlobalExceptionHandler
  - CORS 설정
- [ ] 일반 엔드포인트
  - [ ] `POST /chat`
  - [ ] `POST /chat/compare`
  - [ ] `GET /market/today`
  - [ ] `GET /news/summary`
  - [ ] `GET /weather/today`
  - [ ] `GET /regulations`
- [ ] **SSE 스트리밍 엔드포인트**
  - [ ] `POST /chat/stream`
    - LangChain StreamingCallback 연결
    - FastAPI `StreamingResponse` + `text/event-stream`
    - 토큰 단위 실시간 출력
- [ ] Swagger 문서 자동화 확인
- [ ] 통합 테스트 작성

---

## Phase 9 — 모델 서빙 비교 실험

> 목적: JD "vLLM 도입 예정" 직접 대응
> 선행 조건: Phase 8 완료
> JD 대응: "vLLM 등 모델 서빙 프레임워크 도입"

- [ ] Ollama 환경 구성
  - Gemma4 로컬 서빙
  - Docker Compose Ollama 서비스 추가
- [ ] vLLM 환경 구성
  - Gemma4 vLLM 서빙 (GPU 필요 시 RunPod/Colab 활용)
  - continuous batching 설정
- [ ] 벤치마크 스크립트 (`scripts/benchmark_llm.py`)
  - 측정 지표: TPS, TTFT, 동시 요청 1 / 5 / 10개
- [ ] 결과 정리: `docs/eval_results/llm_serving_benchmark.md`

---

## Phase 10 — 모니터링 스택

> 목적: 실서비스 수준 운영 환경 완성
> 선행 조건: Phase 8 완료

### Prometheus + Grafana
- [ ] FastAPI Prometheus 메트릭 노출 (`/metrics`)
  - API 응답 시간 (p50, p95, p99)
  - 엔드포인트별 요청 수 / 에러율
  - LLM 호출 횟수 및 지연 시간
  - 캐시 hit/miss rate (Redis)
- [ ] Grafana 대시보드 구성
  - API 성능 패널
  - 캐시 효율 패널
  - LLM 사용량 패널
- [ ] Docker Compose에 Prometheus + Grafana 추가

### LangSmith 트레이싱
- [ ] LangSmith 프로젝트 연결
- [ ] Agent 실행 트레이스 수집
  - Router 분류 결과
  - 각 Tool 호출 시간
  - Re-ranker / Self-RAG 루프 횟수
- [ ] 트레이싱 기반 병목 구간 분석

---

## Phase 11 — 배포 & 포트폴리오 마무리

> 목적: 외부 접근 가능한 데모 환경 구성
> 선행 조건: Phase 10 완료

- [ ] Dockerfile 최종 작성
- [ ] Docker Compose 전체 구성
  - App + Qdrant + PostgreSQL + Redis + Neo4j + Ollama + Prometheus + Grafana
- [ ] AWS EC2 or Render 배포
- [ ] Streamlit 데모 UI (`streamlit_app.py`)
  - 일반 응답 vs SSE 스트리밍 응답 비교 탭
  - Vector only vs Hybrid vs GraphRAG 검색 비교 탭
  - LangSmith 트레이스 링크 노출
- [ ] README 최종 정리
  - 설계 문서 전체 링크
  - 실험 결과 요약 테이블
- [ ] 기술 블로그 포스팅
  - [ ] 청킹 전략 A/B + RAGAS 평가 실험기
  - [ ] Re-ranker 도입 전후 검색 정밀도 비교
  - [ ] GraphRAG vs Vector RAG 규제 문서 검색 비교
  - [ ] LangGraph Send API로 병렬 Multi-Agent 구현하기
  - [ ] Self-RAG / Adaptive RAG 구현기
  - [ ] Ollama vs vLLM Gemma4 서빙 성능 비교

---

## 전체 의존 관계

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
             │
             ├──────────────────┐
             ▼                  ▼
    Phase 4 (Hybrid+평가)   Phase 5 (GraphRAG)
             │                  │
             └────────┬──────────┘
                      │
                      ▼
             Phase 6 (Multi-Agent A2A)
                      │
                      ▼
             Phase 7 (Adaptive + Self-RAG)
                      │
                      ▼
             Phase 8 (FastAPI + SSE)
                      │
                      ├──────────────────┐
                      ▼                  ▼
             Phase 9 (vLLM 비교)   Phase 10 (모니터링)
                      │                  │
                      └────────┬──────────┘
                               ▼
                      Phase 11 (배포 + 마무리)
```

---

## 고도화 항목 전체 요약

| 항목 | Phase | 기술 | JD 대응 | 어필 포인트 |
|------|-------|------|---------|-------------|
| Redis 캐시 | 2 | Redis TTL | - | 실서비스 캐시 패턴 |
| Re-ranker | 4 | Cross-Encoder | - | 검색 정밀도 수치 비교 |
| Query Rewriting | 4 | LLM 전처리 | - | 구어체 질의 대응 |
| RAGAS 평가 | 4 | Faithfulness 등 | - | 설계 결정 수치 증명 |
| 청킹 A/B 실험 | 4 | chunk_size 비교 | - | 블로그 소재 |
| GraphRAG | 5 | Neo4j | Graph DB 도입 | 복합 규제 질의 처리 |
| Multi-Agent A2A | 6 | LangGraph | A2A 기반 연동 | 아키텍처 설계 역량 |
| Adaptive RAG | 7 | FLARE 패턴 | - | 동적 전략 분기 |
| Self-RAG | 7 | 재검색 루프 | - | 정확도 자가 개선 |
| SSE 스트리밍 | 8 | FastAPI SSE | - | 실서비스 수준 UX |
| vLLM 비교 | 9 | vLLM | vLLM 도입 | 벤치마크 수치 |
| Prometheus | 10 | 메트릭 수집 | - | 실서비스 운영 완성도 |
| Grafana | 10 | 대시보드 | - | 시각화된 성능 증명 |
| LangSmith | 10 | 트레이싱 | - | 디버깅 + 데모 품질 |
