# 폴더 구조 설계

## 1. 설계 의도

### 핵심 원칙: 교체 가능성

이 프로젝트는 시작부터 **각 컴포넌트를 독립적으로 교체할 수 있어야 한다**는 원칙으로 설계됐다.

실제로 예상되는 교체 시나리오:

| 상황 | 교체 대상 | 영향 범위 |
|------|-----------|-----------|
| 공공 API를 다른 업체로 변경 | `collector/exchange.py` | collector 서비스만 |
| 벡터 DB를 Qdrant → 다른 DB로 | `indexer/qdrant.py` | indexer 서비스만 |
| RAG 엔진 교체 | `indexer/` 전체 | indexer 서비스만 |
| LLM 백엔드 변경 | `agent/llm_backend.py` | agent 서비스만 |
| API 프레임워크 변경 | `gateway/` | gateway 서비스만 |

서비스들이 **Kafka 토픽 인터페이스로만 통신**하기 때문에, 한 서비스를 바꿔도 다른 서비스 코드를 건드리지 않아도 된다.

---

## 2. 구조 변천 과정

### 단계 1 — 초기 모놀리식 구조 (지양)

```
src/app/
├── api/
├── agent/
├── data/
├── indexing/
└── kafka/
```

**문제점**: 모든 코드가 한 덩어리. 환율 API 교체 시 `app/data/collectors/exchange_api.py`만 바꾸면 되지만, 해당 파일이 `app/agent/`, `app/kafka/` 등과 직접 의존하고 있어 파급 범위가 불명확했다.

### 단계 2 — 레이어 분리 시도

```
src/
├── api/
├── agent/
├── pipeline/
└── shared/
```

**문제점**: 레이어는 나뉘었지만 여전히 단일 프로세스. `pipeline/`이 `agent/`를 직접 임포트하는 구조가 되어 결합도가 높았다.

### 단계 3 — MSA 구조 확정 (현재)

```
src/
├── services/      각 서비스 (독립 실행 가능)
│   ├── collector/ 수집
│   ├── indexer/   인덱싱
│   ├── agent/     AI Agent
│   ├── gateway/   API 게이트웨이
│   └── evaluator/ 품질 평가
├── shared/        서비스 간 공통 코드
├── scripts/       초기화
└── tests/         테스트
```

**선택 이유**: 서비스 간 통신을 Kafka 토픽으로만 하면 각 서비스가 완전히 독립적이다. 나중에 `collector`만 새 공공 API 버전으로 교체하거나, `indexer`를 완전히 다른 RAG 엔진으로 바꿔도 다른 서비스에 영향이 없다.

---

## 3. 최종 폴더 구조

```
cement-rag-assistant/
│
├── README.md                     프로젝트 소개
├── .env.example                  환경변수 템플릿
├── .gitignore
│
├── docs/                         모든 문서
│   ├── README.md                 문서 목록 진입점
│   ├── TASK.md                   개발 로드맵
│   ├── HARDWARE.md               하드웨어 스펙
│   ├── GLOSSARY.md               용어 정리
│   ├── design/                   설계 문서 (01~14)
│   │   ├── 01_data_flow.md
│   │   ├── 02_db_schema.md
│   │   └── ...
│   ├── daily/                    데일리 작업 로그
│   │   └── YYYY-MM-DD.md
│   └── runbook/                  단계별 실행 검증 가이드
│       └── 01_setup_verify.md
│
├── src/                          Python 소스 코드
│   ├── services/                 MSA 서비스 (각각 독립 배포 가능)
│   │   │
│   │   ├── collector/            수집 서비스
│   │   │   ├── main.py           Kafka Producer + 스케줄러
│   │   │   ├── exchange.py       한국은행 환율 API
│   │   │   ├── news.py           네이버 뉴스 API
│   │   │   ├── weather.py        기상청 단기예보 API
│   │   │   ├── coal.py           유연탄 가격 CSV
│   │   │   ├── erp.py            ERP 배치 수집
│   │   │   └── Dockerfile
│   │   │
│   │   ├── indexer/              인덱싱 서비스
│   │   │   ├── main.py           Kafka Consumer (indexing.requests)
│   │   │   ├── chunking/         청킹 전략 (semantic / table-aware)
│   │   │   ├── embedding.py      ko-sroberta 임베딩
│   │   │   ├── qdrant.py         Qdrant 벡터 적재
│   │   │   ├── elastic.py        Elasticsearch BM25 적재
│   │   │   ├── graph.py          Neo4j 그래프 적재
│   │   │   └── Dockerfile
│   │   │
│   │   ├── agent/                Agent 서비스
│   │   │   ├── main.py           내부 FastAPI 서버
│   │   │   ├── orchestrator.py   Orchestrator Agent
│   │   │   ├── router.py         Adaptive Router
│   │   │   ├── self_rag.py       Self-RAG 루프
│   │   │   ├── query_rewriter.py Query Rewriting
│   │   │   ├── llm_backend.py    LLM 백엔드 추상화
│   │   │   ├── sub_agents/       Market / News / RAG / ERP Agent
│   │   │   ├── tools/            각 Sub-Agent Tool
│   │   │   └── Dockerfile
│   │   │
│   │   ├── gateway/              API 게이트웨이 서비스
│   │   │   ├── main.py           외부 노출 FastAPI 서버
│   │   │   ├── routers/          chat / market / news / weather / regulations
│   │   │   ├── middleware/       인증, CORS, Rate Limiting
│   │   │   └── Dockerfile
│   │   │
│   │   └── evaluator/            평가 서비스
│   │       ├── main.py           RAGAS 평가 실행
│   │       ├── ragas_runner.py   Faithfulness / Relevancy / Recall
│   │       ├── golden_set.json   평가용 질의-정답 셋
│   │       └── Dockerfile
│   │
│   ├── shared/                   서비스 공통 코드 (pip 패키지처럼 임포트)
│   │   ├── config.py             pydantic-settings 환경변수
│   │   ├── models/               공통 Pydantic 모델
│   │   ├── kafka/                Producer / Consumer 공통 래퍼
│   │   └── db/                   PostgreSQL / Redis / Qdrant / ES 연결
│   │
│   ├── scripts/                  DB 초기화 (1회성 실행)
│   │   ├── init_db.sql
│   │   ├── init_qdrant.py
│   │   ├── init_elasticsearch.py
│   │   ├── init_neo4j.py
│   │   └── init_kafka.py
│   │
│   ├── tests/
│   │   ├── unit/                 서비스별 단위 테스트
│   │   └── integration/          서비스 간 통합 테스트
│   │
│   └── pyproject.toml
│
└── infra/                        인프라 설정 (코드 아님)
    ├── README.md
    ├── Dockerfile                앱 컨테이너 빌드
    ├── docker-compose.yml        로컬 개발 환경
    ├── monitoring/               Prometheus 설정
    └── k8s/                      Kubernetes 매니페스트
        ├── app/
        ├── qdrant/
        ├── postgres/
        ├── redis/
        ├── elasticsearch/
        ├── neo4j/
        ├── kafka/
        ├── ollama/
        ├── vllm/
        ├── monitoring/
        ├── jaeger/
        └── config/
```

---

## 4. 서비스 간 통신 구조

```
                        ┌─────────────┐
                        │   gateway   │  ← 외부 사용자
                        │  (FastAPI)  │
                        └──────┬──────┘
                               │ HTTP
                        ┌──────▼──────┐
                        │    agent    │
                        │ (LangGraph) │
                        └──────┬──────┘
                               │ DB 직접 조회
                    ┌──────────┼──────────┐
                    ▼          ▼          ▼
              PostgreSQL     Qdrant    Elasticsearch
               (market)      (rag)      (rag)
                    ▲          ▲          ▲
                    │          │          │
             ┌──────┴──────────┴──────────┴──────┐
             │           Kafka Topics              │
             └──────┬──────────────────┬──────────┘
                    │                  │
             ┌──────▼──────┐   ┌───────▼──────┐
             │  collector  │   │   indexer    │
             │  (수집기)   │   │  (인덱싱)    │
             └─────────────┘   └──────────────┘
```

**규칙**: 서비스끼리 직접 임포트 금지. 반드시 Kafka 토픽 또는 DB를 통해서만 통신.

---

## 5. 새 서비스/모듈 추가 시 기준

### 공공 API를 새로 붙이는 경우

`src/services/collector/` 안에 새 파일 추가.

```
src/services/collector/
├── exchange.py       ← 기존
├── news.py           ← 기존
├── price_index.py    ← 신규: 건설자재 가격지수
└── main.py           스케줄러에 신규 수집기 등록만 하면 됨
```

다른 서비스(indexer, agent, gateway)는 전혀 건드리지 않아도 된다.

### RAG 엔진을 교체하는 경우

`src/services/indexer/` 안에서만 수정.

```python
# indexer/main.py
# Kafka Consumer는 동일
# qdrant.py → new_vector_db.py 로 교체만 하면 됨
from indexer.new_vector_db import store  # ← 이것만 바꿈
```

### 새 Sub-Agent를 추가하는 경우

`src/services/agent/sub_agents/` 안에 새 파일 추가.

```
src/services/agent/sub_agents/
├── market.py         ← 기존
├── news.py           ← 기존
├── rag.py            ← 기존
├── erp.py            ← 기존
└── weather_forecast.py  ← 신규: 전문 날씨 예측 Agent
```

Orchestrator에 등록만 하면 다른 서비스에 영향 없음.

---

## 6. shared/ 사용 원칙

`shared/`는 모든 서비스에서 공통으로 쓰는 코드만 넣는다.

**넣어야 하는 것:**
- 환경변수 설정 (`config.py`)
- Kafka Producer/Consumer 공통 래퍼
- DB 연결 공통 함수
- 서비스 간 공유하는 Pydantic 모델

**넣으면 안 되는 것:**
- 특정 서비스 비즈니스 로직
- 서비스 전용 데이터 모델

---

## 7. 변경 이력

| 날짜 | 변경 내용 | 이유 |
|------|-----------|------|
| 2026-05-07 | 모놀리식 `src/app/` 구조로 시작 | Phase 1 초기 뼈대 |
| 2026-05-07 | `docs/` + `src/` + `infra/` 3분리 | MD와 소스 코드 분리 |
| 2026-05-07 | `src/services/` MSA 구조로 전환 | 공공 API 교체, RAG 교체 등 독립적 변경을 위해 |
