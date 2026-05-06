# 개발 태스크 & 설계 문서 체크리스트

## 설계 문서 목록

설계 문서는 코드 작성 전에 완성해야 합니다.
코드를 짜다가 설계가 바뀌면 비용이 크기 때문에, 각 Phase 시작 전 해당 설계 문서를 먼저 확정합니다.

| # | 문서 | 파일 | 상태 | 선행 조건 |
|---|------|------|------|-----------|
| 01 | 데이터 흐름 설계 | `docs/01_data_flow.md` | ✅ | 없음 |
| 02 | DB 스키마 설계 | `docs/02_db_schema.md` | ✅ | 01 |
| 03 | Agent 설계 | `docs/03_agent_design.md` | ✅ | 01, 02 |
| 04 | API 명세 | `docs/04_api_spec.md` | ✅ | 03 |
| 05 | 환경 설정 가이드 | `docs/05_env_setup.md` | ✅ | 없음 |
| 06 | 검색 품질 평가 기준 | `docs/06_eval_criteria.md` | ✅ | 02, 03 |
| 07 | 모델 서빙 비교 설계 | `docs/07_model_serving.md` | ✅ | 03 |
| 08 | 성능 최적화 설계 | `docs/08_performance.md` | ✅ | 04 |
| 09 | GraphRAG 설계 | `docs/09_graph_rag.md` | ✅ | 02, 03 |
| 10 | Multi-Agent A2A 설계 | `docs/10_multi_agent.md` | ✅ | 03 |
| 11 | 모니터링 설계 | `docs/11_monitoring.md` | ✅ | 04 |
| 12 | Kafka 이벤트 스트리밍 설계 | `docs/12_kafka.md` | ✅ | 01, 02 |
| 13 | Kubernetes 배포 설계 | `docs/13_kubernetes.md` | ✅ | 11, 12 |
| 14 | 온프레미스 / 에어갭 설계 | `docs/14_airgap.md` | ✅ | 05, 13 |
| 15 | 하드웨어 스펙 가이드 | `docs/15_hardware_spec.md` | ✅ | 05, 07 |

> 설계 문서 완료 기준: 코드 작성자가 문서만 보고 구현 가능한 수준

---

## Phase 0 — 설계 확정 (코드 없음)

> 목적: 나중에 설계가 바뀌어서 코드를 갈아엎는 일 방지

- [x] `docs/01_data_flow.md` 작성
- [x] `docs/02_db_schema.md` 작성
  - PostgreSQL 테이블 정의 (DDL 포함)
  - Qdrant 컬렉션 정의 (벡터 차원, payload 스키마)
  - Neo4j 그래프 노드/엣지 스키마
  - Redis 캐시 키 설계
  - 질의 유형별 데이터 접근 패턴
- [x] `docs/03_agent_design.md` 작성
  - LangGraph 상태(State) 정의
  - Router 분류 기준 및 프롬프트
  - Tool별 입출력 스펙
  - Multi-Agent A2A 구조 설계
  - 복합 질의 병렬 처리 전략 (LangGraph Send API)
  - Self-RAG 재검색 루프 설계
  - Adaptive RAG 전략 분기 설계
- [x] `docs/04_api_spec.md` 작성
  - 전체 엔드포인트 목록
  - 요청/응답 스키마 (Pydantic 모델 기준)
  - SSE 스트리밍 엔드포인트 설계
  - 에러 코드 정의
- [x] `docs/05_env_setup.md` 작성
  - 필요한 API 키 목록 및 발급 방법
  - .env.example 파일 구성
  - Docker Compose / K8s 환경 구성
- [x] `docs/06_eval_criteria.md` 작성
  - RAGAS 지표 (Faithfulness, Answer Relevancy, Context Recall)
  - 청킹 전략 A/B 비교 실험 설계
  - Re-ranker 도입 전후 비교 설계
  - 골든 셋 구성 방법
- [x] `docs/07_model_serving.md` 작성
  - Ollama vs vLLM 비교 실험 설계
  - 측정 지표: TPS, TTFT, 동시 요청 처리량
- [x] `docs/08_performance.md` 작성
  - 비동기 처리 설계 (asyncio + httpx)
  - LangGraph 병렬 Tool 실행 (Send API)
  - 순차 vs 병렬 응답 속도 측정 계획
- [x] `docs/09_graph_rag.md` 작성
  - Neo4j 도입 목적 및 적용 범위
  - 규제 문서 그래프 구조 설계
  - Vector RAG + Graph RAG 결합 전략
- [x] `docs/10_multi_agent.md` 작성
  - Orchestrator + Sub-Agent 구조 설계
  - A2A 프로토콜 인터페이스 정의
  - Agent 간 상태 전달 방식
- [x] `docs/11_monitoring.md` 작성
  - Prometheus 메트릭 정의
  - Grafana 대시보드 구성
  - LangSmith 트레이싱 설정
- [x] `docs/12_kafka.md` 작성
  - Topic 설계 및 파티셔닝 전략
  - Producer / Consumer 구조 설계
  - Dead Letter Queue 처리 전략
  - Docker Compose vs K8s 환경별 구성
- [x] `docs/13_kubernetes.md` 작성
  - 서비스별 Deployment / Service 설계
  - HPA(HorizontalPodAutoscaler) 설정 기준
  - ConfigMap / Secret 관리 전략
  - Ingress 설계
- [x] `docs/14_airgap.md` 작성
  - 외부 의존성 목록 및 내부화 전략
  - 모델 사전 반입 절차 (ko-sroberta, Gemma4)
  - Harbor 내부 레지스트리 구성
  - LangSmith → Jaeger + OpenTelemetry 대체
  - 실시간 API 대체 전략 (내부 DB 사전 적재)

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
  - `app/kafka/` — Producer / Consumer
  - `k8s/` — Kubernetes 매니페스트
- [ ] Docker Compose 기초 구성
  - Qdrant, PostgreSQL, Redis, Neo4j, Kafka(KRaft), Zookeeper 컨테이너
- [ ] `app/core/config.py` 작성
  - pydantic-settings 기반 환경변수 로딩
- [ ] DB 초기화 스크립트
  - `scripts/init_db.sql` — PostgreSQL DDL
  - `scripts/init_qdrant.py` — Qdrant 컬렉션 생성
  - `scripts/init_neo4j.py` — Neo4j 제약조건 및 인덱스 생성
  - `scripts/init_kafka.py` — Kafka Topic 생성

---

## Phase 2 — 데이터 수집 레이어

> 목적: 실제 데이터가 들어오는 파이프라인 완성
> 선행 조건: Phase 1 완료, API 키 발급 완료

- [ ] 한국은행 환율 API 수집기 (`app/data/collectors/exchange_api.py`)
  - async ECOS API 호출 (httpx)
  - Redis TTL 캐시 (1시간) → PostgreSQL 영구 저장
  - 수집 완료 시 Kafka `market.raw` 토픽에 이벤트 발행
- [ ] 네이버 뉴스 API 수집기 (`app/data/collectors/news_api.py`)
  - 키워드 3개 asyncio.gather 병렬 호출
  - Redis TTL 캐시 (30분) → PostgreSQL 영구 저장
  - 수집 완료 시 Kafka `news.raw` 토픽에 이벤트 발행
- [ ] 기상청 API 수집기 (`app/data/collectors/weather_api.py`)
  - async 호출, 위경도 → 격자 좌표 변환
  - Redis TTL 캐시 (1시간)
  - 수집 완료 시 Kafka `weather.raw` 토픽에 이벤트 발행
- [ ] 유연탄 가격 CSV 수집기 (`app/data/collectors/coal_price.py`)
  - 수집 완료 시 Kafka `indexing.requests` 토픽에 발행
- [ ] ERP 샘플 데이터 생성 (`app/data/samples/generate_erp.py`)
  - 2년치 일별 생산·재고 데이터 생성
  - 배치 완료 시 Kafka `erp.updated` 토픽에 발행
- [ ] 수집기 단위 테스트 작성

---

## Phase 3 — Kafka 이벤트 파이프라인

> 목적: 수집 → 처리 → 인덱싱을 비동기 이벤트 기반으로 분리
> 선행 조건: Phase 2 완료
> 효과: 수집기와 인덱싱 워커의 완전한 디커플링, 장애 격리

### Kafka Topic 설계

```
market.raw        환율 수집 이벤트
news.raw          뉴스 수집 이벤트
weather.raw       날씨 수집 이벤트
erp.updated       ERP 배치 완료 이벤트
indexing.requests 인덱싱 요청 (PDF/CSV 처리 요청)
indexing.results  인덱싱 완료 이벤트
llm.requests      LLM 비동기 처리 요청 (뉴스 요약 등)
llm.results       LLM 처리 완료 이벤트
dlq.errors        Dead Letter Queue (처리 실패 메시지)
```

### Producer 구현
- [ ] Kafka Producer 래퍼 (`app/kafka/producer.py`)
  - aiokafka 기반 async Producer
  - 메시지 직렬화 (JSON + 스키마 버전 관리)
  - 발행 실패 시 재시도 로직 (3회, exponential backoff)

### Consumer 구현
- [ ] 인덱싱 Consumer (`app/kafka/consumers/indexing_consumer.py`)
  - `indexing.requests` 구독
  - PDF/CSV 유형 감지 → 청킹 전략 분기 → Qdrant 적재
  - 처리 완료 시 `indexing.results` 발행
  - 실패 시 `dlq.errors` 발행
- [ ] LLM Consumer (`app/kafka/consumers/llm_consumer.py`)
  - `llm.requests` 구독
  - 뉴스 요약 / Self-RAG 재검색 비동기 처리
  - 완료 시 `llm.results` 발행
- [ ] ERP Consumer (`app/kafka/consumers/erp_consumer.py`)
  - `erp.updated` 구독
  - PostgreSQL production_logs upsert
- [ ] Dead Letter Queue 처리기 (`app/kafka/consumers/dlq_consumer.py`)
  - `dlq.errors` 구독
  - 실패 메시지 로깅 및 알림

### 인덱싱 파이프라인 (Kafka 연동)
- [ ] Embedding 모델 래퍼 (`app/indexing/embedding.py`)
- [ ] Semantic chunking (`app/indexing/chunking/semantic.py`)
- [ ] Table-aware chunking (`app/indexing/chunking/table_aware.py`)
- [ ] 인덱싱 파이프라인 오케스트레이터 (`app/indexing/pipeline.py`)
  - Kafka Consumer에서 메시지 수신 → 파이프라인 실행

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
  - chunk_size 256 vs 512 vs 1024 / overlap 0 vs 64
  - 결과: `docs/eval_results/chunking_ab_test.md`

---

## Phase 5 — GraphRAG (Neo4j)

> 목적: 벡터 검색으로 불가능한 복합 규제 질의 처리
> 선행 조건: Phase 3 완료
> 도입 배경: 복합 규제 질의 처리를 위한 그래프 DB 필요성

- [ ] 규제 문서 → Neo4j 그래프 변환 (`app/indexing/graph_indexer.py`)
  - 노드: 법령, 조항, 수치기준, 오염물질
  - 엣지: CONTAINS / REGULATES / APPLIES_TO
- [ ] Cypher 쿼리 기반 규제 탐색 (`app/agent/tools/graph_tool.py`)
- [ ] Vector RAG + Graph RAG 결합 전략 구현
- [ ] 비교 실험: Vector only vs GraphRAG vs 결합
  - 결과: `docs/eval_results/graph_rag_eval.md`

---

## Phase 6 — Multi-Agent A2A 구조

> 목적: 단일 Agent → 전문화된 Sub-Agent 분리
> 선행 조건: Phase 5 완료
> 도입 배경: 단일 Agent 한계 극복 및 Agent 간 표준 통신 프로토콜 필요

- [ ] Orchestrator Agent (`app/agent/orchestrator.py`)
- [ ] Sub-Agent 구현
  - [ ] Market Agent — 환율 + 유연탄 + 원가
  - [ ] News Agent — 뉴스 수집 + 요약
  - [ ] RAG Agent — 문서 검색 (Vector + Graph)
  - [ ] ERP Agent — 생산·재고 분석
- [ ] A2A 인터페이스 정의 (`app/agent/a2a_protocol.py`)
- [ ] Orchestrator → Sub-Agent 병렬 호출 (LangGraph Send API)

---

## Phase 7 — Adaptive RAG + Self-RAG

> 목적: 질의 복잡도에 따른 동적 검색 전략
> 선행 조건: Phase 4, 5, 6 완료

- [ ] Adaptive RAG — 질의 난이도 분류기 (`app/agent/adaptive_router.py`)
  - 단순 → Vector only / 중간 → Hybrid / 복잡 → Hybrid + Re-ranker + Rewriting
  - 결과: `docs/eval_results/adaptive_rag_eval.md`
- [ ] Self-RAG — 검색 결과 자가 평가 (`app/agent/self_rag.py`)
  - 불충분 시 최대 3회 재검색
  - LLM 비동기 처리는 Kafka `llm.requests` 통해 전달
  - 결과: `docs/eval_results/self_rag_eval.md`

---

## Phase 8 — FastAPI 서버 + SSE 스트리밍

> 목적: 외부 호출 가능한 API + 실서비스 수준 UX
> 선행 조건: Phase 7 완료

- [ ] FastAPI 앱 기본 구조 (`app/main.py`)
  - ApiResponse 공통 래퍼 / GlobalExceptionHandler / CORS
- [ ] 일반 엔드포인트
  - [ ] `POST /chat` / `POST /chat/compare`
  - [ ] `GET /market/today` / `GET /news/summary`
  - [ ] `GET /weather/today` / `GET /regulations`
- [ ] SSE 스트리밍 엔드포인트
  - [ ] `POST /chat/stream` — StreamingResponse + text/event-stream
- [ ] Swagger 문서 자동화 / 통합 테스트

---

## Phase 9 — 모델 서빙 비교 실험

> 목적: 프로덕션급 LLM 서빙 프레임워크 검증
> 선행 조건: Phase 8 완료
> 도입 배경: continuous batching 기반 고처리량 LLM 서빙 필요

- [ ] Ollama 환경 구성 — Gemma4 로컬 서빙
- [ ] vLLM 환경 구성 — continuous batching (GPU 필요 시 RunPod 활용)
- [ ] 벤치마크 스크립트 (`scripts/benchmark_llm.py`)
  - TPS, TTFT, 동시 요청 1 / 5 / 10개 시나리오
- [ ] 결과: `docs/eval_results/llm_serving_benchmark.md`

---

## Phase 10 — 모니터링 스택

> 목적: 실서비스 수준 운영 환경 완성
> 선행 조건: Phase 8 완료

### Prometheus + Grafana
- [ ] FastAPI `/metrics` 엔드포인트
  - API 응답 시간 (p50, p95, p99) / 에러율
  - LLM 호출 횟수 및 지연 / Redis 캐시 hit·miss율
  - **Kafka Consumer lag** (파이프라인 처리 지연 모니터링)
- [ ] Grafana 대시보드 구성
  - API 성능 / 캐시 효율 / LLM 사용량 / Kafka 처리량 패널
- [ ] Docker Compose에 Prometheus + Grafana 추가

### LangSmith 트레이싱
- [ ] LangSmith 프로젝트 연결
- [ ] Agent 실행 트레이스 수집 (Router 분류, Tool 호출 시간, Self-RAG 루프)
- [ ] 트레이싱 기반 병목 구간 분석

---

## Phase 11 — Kubernetes 배포

> 목적: 프로덕션 수준 오케스트레이션 환경 구성
> 선행 조건: Phase 10 완료
> 도구: minikube(로컬) → EKS or GKE(클라우드)

### 매니페스트 작성 (`k8s/`)
- [ ] Namespace 정의 (`k8s/namespace.yaml`)
- [ ] 각 서비스 Deployment + Service
  - [ ] `k8s/app/` — FastAPI 앱
  - [ ] `k8s/qdrant/` — Qdrant (StatefulSet)
  - [ ] `k8s/postgres/` — PostgreSQL (StatefulSet)
  - [ ] `k8s/redis/` — Redis
  - [ ] `k8s/neo4j/` — Neo4j (StatefulSet)
  - [ ] `k8s/kafka/` — Kafka (KRaft 모드, StatefulSet)
  - [ ] `k8s/ollama/` — Ollama LLM 서빙 (CPU / 소규모 GPU)
  - [ ] `k8s/vllm/` — vLLM LLM 서빙 (GPU 고처리량)
  - [ ] `k8s/jaeger/` — Jaeger 트레이싱 (에어갭 환경용)
  - [ ] `k8s/monitoring/` — Prometheus + Grafana
- [ ] ConfigMap / Secret 분리 (`k8s/config/`)
- [ ] Ingress 설정 (`k8s/ingress.yaml`)
  - 도메인 라우팅 및 TLS 설정
- [ ] HPA 설정 (`k8s/hpa.yaml`)
  - FastAPI Pod: CPU 70% 초과 시 스케일 아웃 (max 5)
  - Kafka Consumer Pod: Consumer lag 기반 스케일 아웃
- [ ] PersistentVolume 설정
  - Qdrant, PostgreSQL, Neo4j, Kafka 데이터 영속화

### 배포 검증
- [ ] minikube로 로컬 전체 스택 구동 확인
- [ ] 롤링 업데이트 동작 확인
- [ ] HPA 스케일 아웃 동작 확인 (부하 테스트)
- [ ] Kafka Consumer lag 모니터링 확인

---

## Phase 12 — 온프레미스 / 에어갭 대응

> 목적: 인터넷 차단 폐쇄망 환경에서도 전체 스택 동작
> 선행 조건: Phase 11 완료
> 도입 효과: 제조업 고객사 보안 환경에서도 납품 가능

### 외부 의존성 내부화

- [ ] HuggingFace 모델 사전 반입 (`scripts/download_models.py`)
  - `jhgan/ko-sroberta-multitask` → `./models/ko-sroberta/` 로컬 저장
  - `cross-encoder/ms-marco-MiniLM-L-6-v2` → `./models/reranker/` 로컬 저장
  - 모델 로더가 로컬 경로 우선 참조하도록 수정
- [ ] Ollama / vLLM 모델 사전 반입
  - Gemma4 모델 파일 내부망 서버로 복사
  - `ollama create` 로컬 모델 등록 스크립트 작성
- [ ] Harbor 내부 컨테이너 레지스트리 구성
  - 모든 Docker 이미지 사전 pull → Harbor push
  - `docker-compose.yml` / K8s 매니페스트 이미지 경로 변경
    ```yaml
    # 변경 전
    image: qdrant/qdrant:latest
    # 변경 후
    image: harbor.internal/cement-rag/qdrant:latest
    ```
- [ ] Python 패키지 내부 미러 구성
  - pip 내부 PyPI 미러 (devpi or Nexus)
  - `pyproject.toml` 에 내부 인덱스 URL 추가

### 실시간 API 대체 전략

외부 API를 사용할 수 없으므로 내부 데이터로 대체합니다.

| 외부 API | 에어갭 대체 방안 |
|----------|-----------------|
| 한국은행 환율 API | 사전 수집 환율 CSV → PostgreSQL 적재 후 주기적 수동 갱신 |
| 네이버 뉴스 API | 내부 RSS 피드 or 샘플 뉴스 데이터 |
| 기상청 Open API | 기상청 FTP 내부망 연동 or 지역 기상 데이터 CSV 적재 |

- [ ] 에어갭 모드 환경변수 추가 (`AIRGAP_MODE=true`)
  - `true` 시 외부 API 호출 대신 내부 DB 조회로 자동 전환
  - 수집기 코드 분기 처리

### 모니터링 대체

- [ ] LangSmith → **Jaeger + OpenTelemetry** 대체
  - FastAPI + LangChain에 OpenTelemetry 계측 추가
  - Jaeger UI로 Agent 실행 트레이스 시각화
  - Docker Compose / K8s에 Jaeger 서비스 추가
- [ ] Grafana 대시보드에 Jaeger 데이터소스 연동

### LLM 백엔드 선택 전략 — 고객 보안 요구 수준별 대응

고객사의 보안 정책에 따라 LLM 백엔드를 환경변수 하나로 전환할 수 있도록 설계합니다.

```
LLM_BACKEND=local      완전 온프레미스 (Ollama/vLLM) — 데이터 외부 유출 없음
LLM_BACKEND=bedrock    AWS Bedrock Claude — 고객 VPC 안에서만 처리
LLM_BACKEND=anthropic  Anthropic API — 엔터프라이즈 계약 + 데이터 보존 0일
```

| 백엔드 | 데이터 외부 전송 | 성능 | 비용 | 적합한 상황 |
|--------|----------------|------|------|-------------|
| local (Ollama/vLLM) | ❌ 없음 | 중 | 초기 GPU 비용 | 완전 폐쇄망, 최고 보안 요구 |
| bedrock | △ AWS VPC 내 격리 | 상 | 사용량 기반 | AWS 사용 고객사 |
| anthropic | ○ 계약적 보호 | 상 | 사용량 기반 | 엔터프라이즈 계약 체결 시 |

- [ ] LLM 백엔드 추상화 레이어 구현 (`app/core/llm_backend.py`)
  - `LLM_BACKEND` 환경변수로 백엔드 선택
  - 동일한 인터페이스로 Ollama / Bedrock / Anthropic API 호출
  - 백엔드 전환 시 코드 변경 없이 동작
- [ ] AWS Bedrock Claude 연동 옵션 추가
  - boto3 기반 Bedrock 클라이언트
  - VPC 엔드포인트 설정 가이드
- [ ] 백엔드별 동작 확인 테스트 (`tests/test_llm_backends.py`)

- [ ] 인터넷 완전 차단 환경에서 전체 스택 기동 확인
  - Docker Compose 오프라인 기동 테스트
  - K8s 오프라인 배포 테스트
- [ ] `AIRGAP_MODE=true` 상태로 예시 질의 5개 정상 동작 확인
- [ ] 에어갭 배포 가이드 문서 작성 (`docs/airgap_deploy_guide.md`)
  - 반입 파일 목록 (모델, 이미지, 패키지)
  - 단계별 설치 절차
  - 트러블슈팅 가이드

---

## Phase 13 — 데모 및 문서 마무리

> 목적: 사내 시연 가능한 데모 환경 + 문서 완성
> 선행 조건: Phase 12 완료

- [ ] Streamlit 데모 UI (`streamlit_app.py`)
  - 일반 응답 vs SSE 스트리밍 응답 비교 탭
  - Vector only vs Hybrid vs GraphRAG 검색 비교 탭
  - LangSmith 트레이스 링크 노출
  - Kafka Consumer lag 실시간 표시
- [ ] README 최종 정리
  - 전체 아키텍처 다이어그램
  - 설계 문서 링크 테이블
  - 실험 결과 요약 (검색 품질 / 응답 속도 / LLM 서빙)
- [ ] 기술 블로그 포스팅
  - [ ] 청킹 전략 A/B + RAGAS 평가 실험기
  - [ ] Re-ranker 도입 전후 검색 정밀도 비교
  - [ ] GraphRAG vs Vector RAG 규제 문서 검색 비교
  - [ ] Kafka로 인덱싱 파이프라인 비동기화하기
  - [ ] LangGraph Send API로 병렬 Multi-Agent 구현하기
  - [ ] Self-RAG / Adaptive RAG 구현기
  - [ ] Ollama vs vLLM Gemma4 서빙 성능 비교
  - [ ] 폐쇄망 온프레미스 환경에서 AI 시스템 구축하기

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
Phase 2 (수집)     Phase 3 (Kafka + 인덱싱)
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
                      Phase 11 (Kubernetes)
                               │
                               ▼
                      Phase 12 (에어갭 대응)
                               │
                               ▼
                      Phase 13 (마무리)
```

---

## 고도화 항목 전체 요약

| 항목 | Phase | 기술 | 도입 배경 | 도입 효과 |
|------|-------|------|---------|-------------|
| Redis 캐시 | 2 | Redis TTL | - | 실서비스 캐시 패턴 |
| Kafka 이벤트 파이프라인 | 3 | aiokafka | - | 수집·처리 디커플링 |
| Kafka DLQ | 3 | Dead Letter Queue | - | 장애 격리 및 재처리 |
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
| Grafana | 10 | 대시보드 | - | Kafka lag 포함 시각화 |
| LangSmith | 10 | 트레이싱 | - | 디버깅 + 데모 품질 |
| Kubernetes | 11 | K8s + HPA | - | 프로덕션 오케스트레이션 |
| Kafka HPA | 11 | Consumer lag 기반 | - | 동적 스케일 아웃 |
| 에어갭 대응 | 12 | Harbor + Jaeger | - | 제조업 폐쇄망 환경 직접 대응 |
| AIRGAP_MODE | 12 | 환경변수 분기 | - | 외부 API 없이 완전 동작 |
| LLM 백엔드 추상화 | 12 | Ollama / Bedrock / Anthropic | - | 고객 보안 수준별 선택 가능 |
