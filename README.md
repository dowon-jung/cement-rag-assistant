# 🏭 시멘트 제조업 특화 Hybrid RAG 어시스턴트

> 실시간 REST API · 이벤트 스트리밍 · 문서 RAG · 지식 그래프를 결합한  
> **FastAPI + LangGraph + Kafka + Kubernetes** 기반 도메인 특화 AI 어시스턴트

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

## 🏗 시스템 아키텍처

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
│    중간 질의  → Hybrid Search (Vector + BM25 + RRF)                 │
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
| **검색 고도화** | Hybrid Search (Vector+BM25+RRF), Cross-Encoder Re-ranker, Query Rewriting |
| **RAG 전략** | Adaptive RAG, Self-RAG, GraphRAG |
| **Embedding** | `jhgan/ko-sroberta-multitask` (한국어 특화, 768 dim) |
| **Vector DB** | Qdrant |
| **Graph DB** | Neo4j |
| **Cache** | Redis (TTL 기반) |
| **RDB** | PostgreSQL |
| **메시지 큐** | Apache Kafka (KRaft), aiokafka |
| **LLM 서빙** | Gemma4 — Ollama (로컬) / vLLM (프로덕션) |
| **실시간 API** | 한국은행 ECOS, 네이버 뉴스 검색, 기상청 Open API |
| **스트리밍** | FastAPI SSE (Server-Sent Events) |
| **모니터링** | Prometheus, Grafana, LangSmith |
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
│   ├── redis/ neo4j/ kafka/
│   ├── ollama/ monitoring/
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
| 01 | [데이터 흐름 설계](docs/01_data_flow.md) | 수집 흐름, 청킹 전략, 갱신 주기 |
| 02 | DB 스키마 설계 | PostgreSQL / Qdrant / Neo4j / Redis |
| 03 | Agent 설계 | LangGraph 상태, Router, Tool 스펙, A2A |
| 04 | API 명세 | 엔드포인트, Pydantic 스키마, SSE |
| 05 | 환경 설정 가이드 | API 키 발급, Docker / K8s 구성 |
| 06 | 검색 품질 평가 기준 | RAGAS, 청킹 A/B, Re-ranker 비교 |
| 07 | 모델 서빙 비교 설계 | Ollama vs vLLM, TPS / TTFT |
| 08 | 성능 최적화 설계 | 비동기 처리, 병렬 Tool 실행 |
| 09 | GraphRAG 설계 | Neo4j 그래프 구조, Cypher 쿼리 |
| 10 | Multi-Agent A2A 설계 | Orchestrator, Sub-Agent, 인터페이스 |
| 11 | 모니터링 설계 | Prometheus 메트릭, Grafana, LangSmith |
| 12 | Kafka 이벤트 스트리밍 설계 | Topic 구조, DLQ, Consumer 전략 |
| 13 | Kubernetes 배포 설계 | Deployment, HPA, Ingress, PV |

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

---

## 📊 개발 로드맵

| Phase | 내용 | 핵심 기술 |
|-------|------|-----------|
| 0 | 설계 확정 | 설계 문서 13개 |
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
