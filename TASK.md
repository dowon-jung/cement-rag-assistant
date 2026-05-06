# 개발 태스크 & 설계 문서 체크리스트

## 설계 문서 목록

설계 문서는 코드 작성 전에 완성해야 합니다.
코드를 짜다가 설계가 바뀌면 비용이 크기 때문에, 각 Phase 시작 전 해당 설계 문서를 먼저 확정합니다.

| 문서 | 파일 | 상태 | 선행 조건 |
|------|------|------|-----------|
| 데이터 흐름 설계 | `docs/01_data_flow.md` | ⬜ | 없음 — 가장 먼저 |
| DB 스키마 설계 | `docs/02_db_schema.md` | ⬜ | 01 완료 후 |
| Agent 설계 | `docs/03_agent_design.md` | ⬜ | 01, 02 완료 후 |
| API 명세 | `docs/04_api_spec.md` | ⬜ | 03 완료 후 |
| 환경 설정 가이드 | `docs/05_env_setup.md` | ⬜ | 없음 — 병행 가능 |
| 검색 품질 평가 기준 | `docs/06_eval_criteria.md` | ⬜ | 02, 03 완료 후 |

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
  - 복합 질의 처리 전략
- [ ] `docs/04_api_spec.md` 작성
  - 전체 엔드포인트 목록
  - 요청/응답 스키마 (Pydantic 모델 기준)
  - 에러 코드 정의
- [ ] `docs/05_env_setup.md` 작성
  - 필요한 API 키 목록 및 발급 방법
  - .env.example 파일 구성
  - Docker Compose 서비스 구성
- [ ] `docs/06_eval_criteria.md` 작성
  - RAG 검색 품질 평가 지표 (MRR, NDCG, Hit Rate)
  - 평가용 질의-정답 셋 (골든 셋) 구성 방법
  - 기준점(baseline) 정의

---

## Phase 1 — 프로젝트 뼈대 세팅

> 목적: 이후 모든 코드가 들어갈 구조를 먼저 잡는다
> 선행 조건: Phase 0 완료

- [ ] Python 프로젝트 초기화
  - `pyproject.toml` 작성 (의존성 목록)
  - `.env.example` 작성
  - `.gitignore` 작성 (`.env`, `__pycache__`, `*.pyc` 등)
- [ ] 디렉토리 구조 생성
  - `app/api/`, `app/agent/tools/`, `app/indexing/chunking/`, `app/data/collectors/`, `app/core/`
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
  - ECOS API 호출
  - PostgreSQL `market_rates` upsert
  - TTL 캐시 로직
- [ ] 네이버 뉴스 API 수집기 (`app/data/collectors/news_api.py`)
  - 키워드별 뉴스 호출
  - PostgreSQL `news_cache` upsert
  - TTL 캐시 로직
- [ ] 기상청 API 수집기 (`app/data/collectors/weather_api.py`)
  - 위경도 → 격자 좌표 변환
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
  - RecursiveCharacterTextSplitter 활용
- [ ] Table-aware chunking 구현 (`app/indexing/chunking/table_aware.py`)
  - 헤더 + N행 단위 청킹
  - payload에 행 메타데이터 포함
- [ ] 환경부 PDF 인덱싱 (`app/data/collectors/regulation_pdf.py`)
  - PDF 파싱 → Semantic chunking → Qdrant `regulations` 적재
- [ ] 유연탄 CSV 인덱싱
  - Table-aware chunking → Qdrant `coal_prices` 적재
- [ ] 생산 매뉴얼 / 품질 기준서 인덱싱 (샘플 문서 활용)
- [ ] 인덱싱 파이프라인 오케스트레이터 (`app/indexing/pipeline.py`)
  - `--source all / regulation / coal / manual` 옵션

---

## Phase 4 — RAG + Hybrid Search

> 목적: 검색 품질의 핵심인 Hybrid Search 구현
> 선행 조건: Phase 3 완료

- [ ] Vector Search 기본 구현
  - Qdrant 유사도 검색 (cosine)
- [ ] BM25 Sparse Search 구현
  - Qdrant sparse vector 활용 or 별도 BM25 인덱스
- [ ] RRF(Reciprocal Rank Fusion) 결합 구현
- [ ] Hybrid Search Tool 완성 (`app/agent/tools/hybrid_search.py`)
- [ ] 검색 품질 평가 스크립트 작성
  - 골든 셋 기반 MRR, Hit@K 측정

---

## Phase 5 — LangGraph Agent

> 목적: 질의 → 데이터 → 응답 전체 흐름 완성
> 선행 조건: Phase 2, 4 완료

- [ ] Router Agent 구현 (`app/agent/router.py`)
  - 의도 분류 프롬프트 튜닝
- [ ] 각 Tool 구현
  - [ ] `exchange_tool.py` — 환율 + 유연탄 원가
  - [ ] `news_tool.py` — 뉴스 수집 + LLM 요약
  - [ ] `weather_tool.py` — 날씨 + 수요 예측
  - [ ] `erp_tool.py` — 생산량 집계 분석
  - [ ] `regulation_tool.py` — 규제 문서 RAG
- [ ] LangGraph 워크플로우 연결 (`app/agent/graph.py`)
- [ ] Answer Synthesizer 구현 (`app/agent/synthesizer.py`)
  - LLM: Gemma4 (Ollama) 우선, Claude API 선택 가능
- [ ] 복합 질의 테스트 (예시 질의 5개 이상)

---

## Phase 6 — FastAPI 서버

> 목적: 외부에서 호출 가능한 API 서버 완성
> 선행 조건: Phase 5 완료

- [ ] FastAPI 앱 기본 구조 (`app/main.py`)
  - ApiResponse 공통 래퍼
  - GlobalExceptionHandler
  - CORS 설정
- [ ] 엔드포인트 구현
  - [ ] `POST /chat`
  - [ ] `POST /chat/compare`
  - [ ] `GET /market/today`
  - [ ] `GET /news/summary`
  - [ ] `GET /weather/today`
  - [ ] `GET /regulations`
- [ ] Swagger 문서 자동화 확인
- [ ] 통합 테스트 작성

---

## Phase 7 — 배포 & 포트폴리오 마무리

> 목적: 외부에서 접근 가능한 데모 환경 구성
> 선행 조건: Phase 6 완료

- [ ] Dockerfile 작성
- [ ] Docker Compose 전체 구성 완성 (App + Qdrant + PostgreSQL)
- [ ] AWS EC2 or Render 배포
- [ ] Streamlit 데모 UI 작성 (`streamlit_app.py`)
- [ ] README 최종 정리 (설계 문서 링크 포함)
- [ ] 기술 블로그 포스팅
  - [ ] 청킹 전략별 검색 품질 비교 실험기
  - [ ] LangGraph로 Multi-Tool RAG 구현하기
  - [ ] 환율 + 유연탄 가격으로 시멘트 원가 분석하기

---

## 의존 관계 요약

```
Phase 0 (설계)
    │
    ▼
Phase 1 (뼈대)
    │
    ├─────────────────┐
    ▼                 ▼
Phase 2 (수집)    Phase 3 (인덱싱)
    │                 │
    └────────┬────────┘
             ▼
         Phase 4 (RAG)
             │
             ▼
         Phase 5 (Agent)
             │
             ▼
         Phase 6 (API)
             │
             ▼
         Phase 7 (배포)
```
