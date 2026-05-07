# 🏭 시멘트 제조업 특화 Hybrid RAG 어시스턴트

> 실시간 REST API · 이벤트 스트리밍 · 문서 RAG · 지식 그래프를 결합한  
> **FastAPI + LangGraph + Kafka + Kubernetes** 기반 도메인 특화 AI 어시스턴트

---

## 💡 이 프로젝트를 시작한 이유

현재 한일네트웍스 DI사업부에서 웹 서비스 개발을 담당하며, 실제 업무에 AI를 도입하는 경험을 쌓아왔습니다.

**우덕재단 장학생 선발 시스템**에서 Claude API를 활용해 자기소개서 자동 분석·채점·심층질의 생성 시스템을 직접 설계하고 구현했습니다. Multi-Agent 구조, 코드 리뷰 Agent, SQL 리뷰 Agent를 직접 만들면서 AI가 실제 업무를 바꿀 수 있다는 것을 확인했습니다.

그 과정에서 두 가지 현실적인 문제를 마주쳤습니다.

**첫째, 도메인 데이터와 AI를 어떻게 연결하는가.**
Claude API 단독으로는 사내 문서나 ERP 데이터를 알 수 없습니다. 고객사 고유의 데이터를 AI가 활용하려면 RAG 파이프라인 설계가 필수였고, 단순 벡터 검색만으로는 규제 문서의 복잡한 조항 관계를 처리할 수 없었습니다.

**둘째, 고객 데이터가 외부로 나가면 안 된다.**
시멘트·철강 같은 제조업 고객사는 보안 정책상 사내 데이터가 외부 서버로 전송되는 것을 허용하지 않는 경우가 많습니다. Claude API를 그냥 연결하면 고객 질의가 Anthropic 서버로 전송됩니다. 이를 해결하려면 로컬 LLM 서빙, 에어갭 환경 대응, LLM 백엔드 추상화가 필요했습니다.

이 두 가지 문제를 제대로 풀어보기 위해 시멘트 제조업을 도메인으로 선택하고, 실제 납품 가능한 수준의 AI 파이프라인을 설계·구현하는 것이 이 프로젝트의 출발점입니다.

---

## 📌 프로젝트 개요

시멘트 제조 현장의 실제 질의 유형을 중심으로 설계한 AI 어시스턴트입니다.  
단순 RAG 챗봇이 아니라, **질의 복잡도에 따라 검색 전략이 동적으로 분기**되고  
**전문화된 Sub-Agent들이 병렬로 협업**하는 프로덕션 수준 AI 파이프라인입니다.

### 예시 질의

```
"오늘 환율이랑 유연탄 가격 기준으로 이번 달 생산 원가 어때?"
"시멘트 관련 최신 뉴스 요약하고 수요 전망 알려줘"
"이번 달 생산량 vs 전년 비교해줘"
"환경부 질소산화물 기준치 초과 시 연쇄 적용되는 조항은?"
"오늘 날씨 기준으로 시멘트 수요 예측해줘"
```

---

## 🧠 RAG 구조와 LLM 역할 이해

### LLM은 학습이 아니라 "읽고 답하는" 구조예요

흔한 오해 중 하나가 "DB에 데이터를 넣으면 LLM이 학습한다"는 거예요.  
RAG는 학습이 아니라 **매 질문마다 DB에서 관련 문서를 찾아서 LLM 앞에 펼쳐주는 방식**이에요.

```
사용자: "환경부 질소산화물 배출 기준이 뭐야?"
         │
         ▼
① Qdrant에서 관련 문서 검색
  → "질소산화물 배출 기준: 0.004kg/Sm³ ..." 청크 5개 추출
         │
         ▼
② LLM에게 전달
  [참고 문서] "질소산화물 배출 기준..."  ← DB에서 가져온 것
  [질문]      "질소산화물 배출 기준이 뭐야?"
         │
         ▼
③ LLM이 참고 문서를 읽고 답변 생성
  → "환경부 기준에 따르면 0.004kg/Sm³ 이하입니다."
```

마치 오픈북 시험처럼, DB에서 관련 내용을 꺼내서 LLM 앞에 펼쳐주는 방식이에요.

---

### Claude API vs 로컬 LLM — 동작 방식은 동일, 차이는 LLM 위치

RAG 구조 자체는 동일해요. **LLM이 어디 있느냐**가 다를 뿐이에요.

```
[Claude API]
질문 + 검색된 문서 → Anthropic 서버 → 답변
                         ↑
                  데이터가 외부로 전송됨

[로컬 LLM (Gemma4)]
질문 + 검색된 문서 → 내부 서버 → 답변
                         ↑
                  데이터가 외부로 나가지 않음
```

| | Claude API | 로컬 LLM (Gemma4) | AWS Bedrock |
|--|------------|-------------------|-------------|
| **데이터 전송** | Anthropic 서버로 전송 | 내부에서만 처리 | VPC 내 격리 |
| **답변 품질** | 높음 | 상대적으로 낮음 | 높음 |
| **비용** | 토큰당 과금 | GPU 서버 초기비용 | 토큰당 과금 |
| **인터넷** | 필요 | 불필요 | AWS VPC |
| **적합한 상황** | 보안 요구 낮음 | 완전 폐쇄망 | AWS 사용 고객사 |

> **AWS Bedrock(VPC 격리)이란?**  
> AWS에서 제공하는 LLM 매니지드 서비스로, Claude 같은 모델을 AWS 인프라 위에서 호출할 수 있어요.  
> Anthropic API를 직접 호출하면 데이터가 Anthropic 본사 서버로 전송되지만, Bedrock은 **고객사 AWS 계정 안의 VPC(격리된 가상 네트워크)** 에서만 처리돼요.  
> VPC 엔드포인트를 사용하면 인터넷을 거치지 않고 AWS 내부망에서만 호출되기 때문에, Claude의 높은 품질을 유지하면서도 데이터가 외부로 나가지 않는 효과를 얻을 수 있어요.

이 프로젝트는 `LLM_BACKEND` 환경변수 하나로 세 가지를 코드 변경 없이 전환할 수 있도록 설계했어요.  
고객사 보안 정책에 따라 유연하게 대응할 수 있는 구조예요.

---

```
┌─────────────────────────────────────────────────────────────────────┐
│                           데이터 소스                                │
│  [실시간 REST API]              [문서 RAG]          [사내 데이터]    │
│  한국은행 환율 API         +   환경부 규제 PDF   +  생산 매뉴얼      │
│  네이버 뉴스 검색 API      +   유연탄 가격 CSV   +  ERP 리포트       │
│  기상청 단기예보 API                               +  품질검사 기준서 │
└──────────────┬──────────────────────┬──────────────────────────────┘
               │                      │
               ▼                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       Kafka 이벤트 파이프라인                         │
│  수집기 → Producer → [market/news/weather/indexing/llm Topics]      │
│                    → Consumer → 인덱싱 워커 / LLM 워커 / ERP 워커   │
│                    → Dead Letter Queue (실패 메시지 재처리)           │
└──────────────┬──────────────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    저장 레이어                                        │
│  Redis          API 응답 캐시 (TTL 30m ~ 1h)                        │
│  PostgreSQL     수치 데이터, ERP, 환율, 뉴스 영구 저장               │
│  Qdrant         문서 벡터 (regulations / coal / manuals / quality)  │
│  Neo4j          규제 지식 그래프 (법령 → 조항 → 수치기준)            │
└──────────────┬──────────────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    RAG 검색 레이어                                    │
│  Adaptive RAG   질의 난이도 → 검색 전략 동적 분기                    │
│    단순 질의  → Vector Search only                                   │
│    중간 질의  → Hybrid Search (Qdrant Vector + ES BM25 + RRF)       │
│    복잡 질의  → Hybrid + Re-ranker + Query Rewriting                │
│  Self-RAG       검색 결과 자가 평가 → 불충분 시 재검색 (최대 3회)    │
│  GraphRAG       Neo4j Cypher → 복합 규제 조항 연쇄 탐색              │
└──────────────┬──────────────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                 LangGraph Multi-Agent (A2A)                          │
│                                                                     │
│  [Orchestrator Agent]                                               │
│       │ ──→ [Market Agent]   환율 + 유연탄 + 원가 분석              │
│       │ ──→ [News Agent]     뉴스 수집 + LLM 요약                   │
│       │ ──→ [RAG Agent]      문서 검색 (Vector + Graph)             │
│       │ ──→ [ERP Agent]      생산·재고 집계 분석                    │
│       │           ↓ 병렬 실행 (LangGraph Send API)                  │
│       └──→ [Answer Synthesizer]  결과 통합 → 최종 응답              │
│                    LLM: Gemma4 (vLLM / Ollama)                      │
└──────────────┬──────────────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      FastAPI 서버                                    │
│  POST /chat              일반 질의응답                               │
│  POST /chat/stream       SSE 토큰 스트리밍                           │
│  POST /chat/compare      전년 대비 비교 분석                         │
│  GET  /market/today      환율 + 유연탄 원가                          │
│  GET  /news/summary      최신 뉴스 요약                             │
│  GET  /weather/today     날씨 + 수요 예측                           │
│  GET  /regulations       규제 문서 검색                             │
└──────────────┬──────────────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Kubernetes (EKS / GKE)                            │
│  Deployment + HPA (FastAPI, Kafka Consumer)                         │
│  StatefulSet (Qdrant, PostgreSQL, Neo4j, Kafka)                     │
│  Prometheus + Grafana + LangSmith 트레이싱                          │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🛠 기술 스택

| 레이어 | 기술 |
|--------|------|
| **Backend** | Python 3.11, FastAPI, Uvicorn |
| **Agent / RAG** | LangChain, LangGraph (Multi-Agent A2A) |
| **검색 고도화** | Hybrid Search (Qdrant Vector + Elasticsearch BM25 + RRF), Cross-Encoder Re-ranker, Query Rewriting |
| **RAG 전략** | Adaptive RAG, Self-RAG, GraphRAG |
| **Embedding** | `jhgan/ko-sroberta-multitask` (한국어 특화, 768 dim) |
| **Vector DB** | Qdrant |
| **키워드 검색** | Elasticsearch (nori 한국어 형태소 분석) |
| **Graph DB** | Neo4j |
| **Cache** | Redis (TTL 기반) |
| **RDB** | PostgreSQL |
| **메시지 큐** | Apache Kafka (KRaft), aiokafka |
| **LLM 서빙** | Gemma4 — Ollama (로컬) / vLLM (프로덕션) |
| **실시간 API** | 한국은행 ECOS, 네이버 뉴스 검색, 기상청 Open API |
| **스트리밍** | FastAPI SSE (Server-Sent Events) |
| **모니터링** | Prometheus, Grafana, LangSmith (인터넷) / Jaeger + OpenTelemetry (에어갭) |
| **컨테이너** | Docker, Docker Compose |
| **오케스트레이션** | Kubernetes (minikube → EKS/GKE), HPA |
| **평가** | RAGAS (Faithfulness, Answer Relevancy, Context Recall) |
| **에어갭 대응** | Harbor 내부 레지스트리, Jaeger + OpenTelemetry, 오프라인 모델 서빙 |

---

## 📁 프로젝트 구조

```
cement-rag-assistant/
├── app/
│   ├── main.py
│   ├── api/                      # FastAPI 엔드포인트
│   ├── agent/
│   │   ├── orchestrator.py       # Orchestrator Agent
│   │   ├── sub_agents/           # Market / News / RAG / ERP Agent
│   │   ├── tools/                # 각 Tool 구현
│   │   ├── adaptive_router.py    # Adaptive RAG 전략 분기
│   │   ├── self_rag.py           # Self-RAG 재검색 루프
│   │   ├── query_rewriter.py     # Query Rewriting
│   │   └── a2a_protocol.py       # A2A 인터페이스
│   ├── indexing/
│   │   ├── chunking/             # Semantic / Table-aware chunking
│   │   ├── embedding.py
│   │   ├── reranker.py           # Cross-Encoder Re-ranker
│   │   ├── graph_indexer.py      # Neo4j 그래프 변환
│   │   └── pipeline.py
│   ├── kafka/
│   │   ├── producer.py           # aiokafka Producer
│   │   └── consumers/            # 인덱싱 / LLM / ERP / DLQ Consumer
│   ├── data/
│   │   ├── collectors/           # API 수집기 (환율/뉴스/날씨/유연탄)
│   │   └── samples/              # ERP 샘플 데이터 생성
│   ├── evaluation/               # RAGAS 평가 + 골든 셋
│   ├── monitoring/               # Prometheus 메트릭
│   └── core/                     # Config, Dependencies
├── k8s/                          # Kubernetes 매니페스트
│   ├── app/ qdrant/ postgres/
│   ├── redis/ elasticsearch/ neo4j/ kafka/
│   ├── ollama/ vllm/ monitoring/
│   ├── jaeger/                   # 에어갭 환경 트레이싱
│   ├── config/                   # ConfigMap / Secret
│   ├── ingress.yaml
│   └── hpa.yaml
├── scripts/
│   ├── init_db.sql
│   ├── init_qdrant.py
│   ├── init_neo4j.py
│   ├── init_kafka.py
│   └── benchmark_llm.py
├── docs/                         # 설계 문서 (아래 참고)
├── streamlit_app.py
├── docker-compose.yml
├── Dockerfile
└── pyproject.toml
```

---

## 📚 설계 문서

| # | 문서 | 내용 |
|---|------|------|
| 01 | [데이터 흐름 설계](docs/design/01_data_flow.md) | 수집 흐름, 청킹 전략, 갱신 주기 |
| 02 | [DB 스키마 설계](docs/design/02_db_schema.md) | PostgreSQL / Qdrant / Neo4j / Redis |
| 03 | [Agent 설계](docs/design/03_agent_design.md) | LangGraph 상태, Router, Tool 스펙, A2A |
| 04 | [API 명세](docs/design/04_api_spec.md) | 엔드포인트, Pydantic 스키마, SSE |
| 05 | [환경 설정 가이드](docs/design/05_env_setup.md) | API 키 발급, Docker / K8s 구성 |
| 06 | [검색 품질 평가 기준](docs/design/06_eval_criteria.md) | RAGAS, 청킹 A/B, Re-ranker 비교 |
| 07 | [모델 서빙 비교 설계](docs/design/07_model_serving.md) | Ollama vs vLLM vs Bedrock vs Anthropic |
| 08 | [성능 최적화 설계](docs/design/08_performance.md) | 비동기 처리, 병렬 Tool 실행, 4-tier 캐시 |
| 09 | [GraphRAG 설계](docs/design/09_graph_rag.md) | Neo4j 그래프 구조, Cypher 쿼리 |
| 10 | [Multi-Agent A2A 설계](docs/design/10_multi_agent.md) | Orchestrator, Sub-Agent, AgentBus |
| 11 | [모니터링 설계](docs/design/11_monitoring.md) | Prometheus, Grafana, LangSmith / Jaeger |
| 12 | [Kafka 이벤트 스트리밍 설계](docs/design/12_kafka.md) | Topic 9종, DLQ, Consumer 전략 |
| 13 | [Kubernetes 배포 설계](docs/design/13_kubernetes.md) | Deployment, HPA, Ingress, KEDA |
| 14 | [온프레미스 / 에어갭 설계](docs/design/14_airgap.md) | AIRGAP_MODE, Harbor, LLM 백엔드 추상화 |
| 15 | [하드웨어 스펙 가이드](docs/HARDWARE.md) | 구성요소별 CPU/RAM/GPU, 도입 시나리오 3종 |

---

## 🚀 빠른 시작

### API 키 발급

| API | 발급 URL |
|-----|---------|
| 한국은행 ECOS | [ecos.bok.or.kr](https://ecos.bok.or.kr/api/#/DevGuide/TopPage) |
| 네이버 검색 | [developers.naver.com](https://developers.naver.com/apps/#/register) |
| 기상청 Open API | [data.go.kr](https://data.go.kr) |

### Docker Compose (개발 환경)

```bash
git clone https://github.com/dowon-jung/cement-rag-assistant.git
cd cement-rag-assistant

cp .env.example .env
# .env에 API 키 입력

docker-compose up -d
pip install -e ".[dev]"

# Kafka Topic + DB 초기화
python scripts/init_kafka.py
python scripts/init_qdrant.py
python scripts/init_neo4j.py
python scripts/init_elasticsearch.py
psql -f scripts/init_db.sql

# 인덱싱 파이프라인 실행
python -m app.indexing.pipeline --source all

# FastAPI 서버
uvicorn app.main:app --reload

# Streamlit 데모
streamlit run streamlit_app.py
```

### Kubernetes (프로덕션)

```bash
# minikube 로컬 환경
minikube start --cpus=4 --memory=8g
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/config/
kubectl apply -f k8s/
```

API 문서: `http://localhost:8000/docs`  
Grafana: `http://localhost:3000`

---

## 🔬 핵심 설계 결정

### 왜 Adaptive RAG인가?
모든 질의에 Hybrid + Re-ranker를 적용하면 단순 질의에도 불필요한 지연이 발생합니다.  
질의 난이도를 분류해 전략을 동적으로 선택함으로써 **응답 속도와 정확도를 동시에 최적화**합니다.

### 왜 GraphRAG + Vector RAG를 병행하는가?
"질소산화물 기준치 초과 시 연쇄 적용 조항"처럼 **관계 탐색이 필요한 규제 질의**는 벡터 유사도로 처리할 수 없습니다.  
Neo4j 그래프로 법령 간 의존 관계를 구조화하면 이런 질의를 정확히 처리할 수 있습니다.

### 왜 Kafka인가?
수집기와 인덱싱 워커를 동기로 연결하면 대용량 PDF 처리 시 API 타임아웃이 발생합니다.  
Kafka로 분리하면 **수집과 처리가 완전히 디커플링**되고, Dead Letter Queue로 실패 메시지를 안전하게 재처리할 수 있습니다.

### 왜 Kubernetes + HPA인가?
Kafka Consumer lag이 쌓일 때 Consumer Pod를 자동으로 스케일 아웃하면  
**인덱싱 파이프라인 처리량을 부하에 따라 탄력적으로 조정**할 수 있습니다.

### 왜 에어갭 대응인가?
시멘트·철강 등 제조업 고객사는 보안 정책상 **인터넷이 차단된 폐쇄망 환경**이 일반적입니다.  
Harbor 내부 레지스트리, 오프라인 모델 서빙(Ollama), Jaeger 트레이싱으로 외부 의존성을 전부 내부화하여  
`AIRGAP_MODE=true` 하나로 폐쇄망 전환이 가능하도록 설계했습니다.

### 왜 LLM 백엔드를 추상화하는가?
고객사마다 보안 요구 수준이 다릅니다.  
`LLM_BACKEND` 환경변수 하나로 **Ollama(완전 온프레미스) → AWS Bedrock(VPC 격리) → Anthropic API(엔터프라이즈 계약)** 를 코드 변경 없이 전환할 수 있도록 설계하여, 고객 보안 정책에 유연하게 대응합니다.

---

## 📊 개발 로드맵

| Phase | 내용 | 핵심 기술 |
|-------|------|-----------|
| 0 | 설계 확정 | 설계 문서 15개 (docs 14개 + HARDWARE.md) |
| 1 | 프로젝트 뼈대 | Docker Compose, 디렉토리 구조 |
| 2 | 데이터 수집 | httpx async, Redis, asyncio.gather |
| 3 | Kafka 파이프라인 | aiokafka, DLQ, 인덱싱 워커 |
| 4 | Hybrid Search + 평가 | BM25+RRF, Re-ranker, RAGAS |
| 5 | GraphRAG | Neo4j, Cypher |
| 6 | Multi-Agent A2A | LangGraph, Orchestrator |
| 7 | Adaptive + Self-RAG | FLARE 패턴, 재검색 루프 |
| 8 | FastAPI + SSE | StreamingResponse |
| 9 | 모델 서빙 비교 | vLLM vs Ollama 벤치마크 |
| 10 | 모니터링 | Prometheus, Grafana, LangSmith |
| 11 | Kubernetes | HPA, StatefulSet, Ingress |
| 12 | 온프레미스 / 에어갭 | Harbor, Jaeger, AIRGAP_MODE, 오프라인 모델 |
| 13 | 마무리 | Streamlit 데모, 블로그 포스팅 |

---

## 🔮 실험 결과 (작성 예정)

| 실험 | 지표 | 결과 |
|------|------|------|
| 청킹 전략 A/B (256 vs 512 vs 1024) | Context Recall | - |
| Re-ranker 도입 전후 | MRR@5 | - |
| Vector only vs GraphRAG vs 결합 | Faithfulness | - |
| 순차 vs 병렬 Tool 실행 | 응답 시간 (ms) | - |
| Ollama vs vLLM (동시 요청 10) | TPS / TTFT | - |

---

## 📄 라이선스

MIT License
