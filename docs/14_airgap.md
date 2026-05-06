# 14. 온프레미스 / 에어갭 설계

## 1. 도입 목적

제조업 고객사는 보안 정책상 **인터넷이 차단된 폐쇄망 환경**이 일반적입니다.  
이 문서는 외부 의존성을 모두 내부화하여 **전체 시스템이 인터넷 없이 동작**하도록 설계합니다.

또한 고객 데이터가 외부로 나가지 않도록 **LLM 백엔드를 환경변수로 전환**할 수 있는 구조를 제공합니다.

---

## 2. 외부 의존성 분류

### ❌ 인터넷 필요 (대체 필요)

| 항목 | 원인 | 대체 방안 |
|------|------|-----------|
| 한국은행 ECOS API | 외부 API | 사전 수집 데이터 + 주기적 수동 갱신 |
| 네이버 뉴스 API | 외부 API | 내부 RSS 피드 or 샘플 |
| 기상청 Open API | 외부 API | 기상청 FTP 내부망 or 샘플 |
| HuggingFace 모델 | 외부 다운로드 | **사전 반입 후 로컬 저장** |
| Docker Hub | 외부 레지스트리 | **Harbor 내부 레지스트리** |
| PyPI 패키지 | 외부 인덱스 | **devpi / Nexus 내부 미러** |
| LangSmith | SaaS 트레이싱 | **Jaeger + OpenTelemetry** |
| Anthropic API | 외부 LLM | **Ollama / vLLM 로컬 LLM** |

### ✅ 인터넷 없어도 동작

| 항목 |
|------|
| FastAPI, Uvicorn |
| Qdrant, PostgreSQL, Redis, Neo4j |
| Kafka (KRaft 모드) |
| Kubernetes (폐쇄망 클러스터) |
| Prometheus, Grafana |
| Ollama, vLLM (모델 사전 반입 시) |

---

## 3. AIRGAP_MODE 환경변수

### 동작 분기

```python
# app/core/config.py
class Settings(BaseSettings):
    AIRGAP_MODE: bool = False
    
    # 에어갭 시 사용할 모델 경로
    EMBEDDING_MODEL_PATH: str = "./models/ko-sroberta"
    RERANKER_MODEL_PATH: str = "./models/reranker"
    
    # 기타...
```

### 수집기 분기

```python
# app/data/collectors/exchange_api.py
async def fetch_exchange(date: str) -> ExchangeData:
    if settings.AIRGAP_MODE:
        return await fetch_from_internal_db(date)
    
    # 일반 모드: 캐시 → API → 영구 저장
    cached = await redis.get(f"exchange:usd_krw:{date}")
    if cached:
        return ExchangeData.parse_raw(cached)
    
    data = await call_ecos_api(date)
    await redis.setex(f"exchange:usd_krw:{date}", 3600, data.json())
    await save_to_postgres(data)
    return data

async def fetch_from_internal_db(date: str) -> ExchangeData:
    """에어갭 환경: 내부 DB 조회만 사용"""
    row = await postgres.fetch_one(
        "SELECT * FROM market_rates WHERE base_date = $1 ORDER BY fetched_at DESC LIMIT 1",
        date
    )
    if not row:
        raise NoDataAvailableError(f"환율 데이터 없음: {date}")
    return ExchangeData(**row)
```

---

## 4. LLM 백엔드 추상화

### 백엔드 선택 매트릭스

| 보안 요구 | 환경 | 권장 백엔드 | LLM_BACKEND |
|-----------|------|-------------|-------------|
| 최고 (완전 폐쇄망) | 사내 GPU 서버 | vLLM | `local` |
| 최고 (완전 폐쇄망) | CPU만 보유 | Ollama | `local` |
| 중 (AWS 사용) | 고객 VPC | Bedrock Claude | `bedrock` |
| 낮음 (계약 체결) | 인터넷 가능 | Anthropic API | `anthropic` |

### 추상화 구조

```python
# app/core/llm_backend.py
from abc import ABC, abstractmethod

class LLMBackend(ABC):
    @abstractmethod
    async def generate(self, messages: list[dict]) -> str: ...
    
    @abstractmethod
    async def stream(self, messages: list[dict]) -> AsyncIterator[str]: ...

class OllamaBackend(LLMBackend):
    """완전 온프레미스 — 데이터 외부 유출 없음"""
    async def generate(self, messages):
        # ollama Python SDK 호출
        ...

class VLLMBackend(LLMBackend):
    """완전 온프레미스 — GPU 고처리량"""
    async def generate(self, messages):
        # OpenAI 호환 클라이언트로 호출
        ...

class BedrockBackend(LLMBackend):
    """AWS VPC 내 격리"""
    async def generate(self, messages):
        # boto3 bedrock-runtime
        ...

class AnthropicBackend(LLMBackend):
    """Anthropic API — 엔터프라이즈 계약 시"""
    async def generate(self, messages):
        # anthropic SDK
        ...

def get_llm_backend() -> LLMBackend:
    backend = settings.LLM_BACKEND
    return {
        "local": OllamaBackend if settings.OLLAMA_ENABLED else VLLMBackend,
        "bedrock": BedrockBackend,
        "anthropic": AnthropicBackend,
    }[backend]()
```

---

## 5. 모델 사전 반입 절차

### 인터넷 환경에서 모델 다운로드

```bash
# scripts/download_models.py
from sentence_transformers import SentenceTransformer
from huggingface_hub import snapshot_download

# 임베딩 모델
SentenceTransformer("jhgan/ko-sroberta-multitask").save("./models/ko-sroberta")

# Re-ranker 모델
SentenceTransformer("cross-encoder/ms-marco-MiniLM-L-6-v2").save("./models/reranker")

# (선택) Gemma2 GGUF 형식 다운로드
snapshot_download(
    repo_id="google/gemma-2-9b-it",
    local_dir="./models/gemma2-9b",
)
```

### 내부망 서버로 복사

```bash
# 압축
tar -czf models.tar.gz ./models

# 내부망 서버 전송 (USB / 폐쇄망 파일전송 시스템)
# ...

# 내부망 서버에서 압축 해제
tar -xzf models.tar.gz
```

### 코드에서 로컬 경로 참조

```python
# app/indexing/embedding.py
class EmbeddingModel:
    def __init__(self):
        # 우선순위: 환경변수 → 기본값
        model_path = settings.EMBEDDING_MODEL_PATH
        
        if not Path(model_path).exists():
            if settings.AIRGAP_MODE:
                raise FileNotFoundError(
                    f"에어갭 모드에서 모델 파일이 없습니다: {model_path}"
                )
            # 일반 모드면 HuggingFace에서 다운로드
            model_path = "jhgan/ko-sroberta-multitask"
        
        self.model = SentenceTransformer(model_path)
```

---

## 6. Ollama 모델 사전 반입

```bash
# 인터넷 환경에서
ollama pull gemma2:9b

# 모델 파일 위치 확인
ls ~/.ollama/models/
# blobs/  manifests/

# 압축
tar -czf ollama-gemma2.tar.gz ~/.ollama

# 내부망 서버로 복사 후
tar -xzf ollama-gemma2.tar.gz -C ~

# Ollama 서버 재기동
docker restart ollama
docker exec -it ollama ollama list
# gemma2:9b 표시 확인
```

---

## 7. Harbor 내부 컨테이너 레지스트리

### 구성

```yaml
# Docker Compose 또는 K8s Helm 차트로 Harbor 설치
# https://goharbor.io/

services:
  harbor:
    image: goharbor/harbor-core:v2.10.0
    # ...
```

### 이미지 사전 풀 + 푸시

```bash
# 인터넷 환경에서 이미지 pull
docker pull qdrant/qdrant:latest
docker pull postgres:16
docker pull redis:7-alpine
docker pull confluentinc/cp-kafka:7.5.0
docker pull neo4j:5-community
docker pull ollama/ollama:latest
docker pull prom/prometheus:latest
docker pull grafana/grafana:latest
docker pull jaegertracing/all-in-one:latest

# Harbor에 푸시
for img in qdrant/qdrant:latest postgres:16 ...; do
  docker tag $img harbor.internal/cement-rag/$img
  docker push harbor.internal/cement-rag/$img
done
```

### K8s 매니페스트 변경

```yaml
# 변경 전
image: qdrant/qdrant:latest

# 변경 후
image: harbor.internal/cement-rag/qdrant:latest
```

### 이미지 풀 시크릿

```bash
kubectl create secret docker-registry harbor-creds \
  --docker-server=harbor.internal \
  --docker-username=admin \
  --docker-password=xxxx \
  --namespace=cement-rag
```

```yaml
# Deployment에 추가
spec:
  template:
    spec:
      imagePullSecrets:
        - name: harbor-creds
```

---

## 8. PyPI 내부 미러 (devpi)

### 구성

```bash
# 인터넷 환경
pip install devpi-server devpi-client
devpi-server --serverdir=/var/devpi --start

# 인덱스 생성 + 외부 PyPI 미러
devpi user -c admin password=xxxx
devpi login admin --password=xxxx
devpi index -c cement-rag bases=root/pypi
```

### 패키지 사전 다운로드

```bash
# 의존성 일괄 다운로드 후 devpi 업로드
pip download -r requirements.txt -d ./packages
devpi upload ./packages/*
```

### 클라이언트 설정 (내부망)

```bash
# pip.conf
[global]
index-url = http://devpi.internal/admin/cement-rag/+simple/
trusted-host = devpi.internal
```

---

## 9. LangSmith → Jaeger 대체

### LangSmith의 한계
- SaaS 서비스 → 외부 전송 필수
- 폐쇄망 환경에서 사용 불가

### Jaeger + OpenTelemetry 구성

```python
# app/monitoring/tracing.py
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

def setup_tracing(app, service_name: str):
    provider = TracerProvider()
    
    if settings.AIRGAP_MODE or not settings.LANGSMITH_TRACING:
        # Jaeger 사용
        jaeger_exporter = JaegerExporter(
            agent_host_name=settings.JAEGER_HOST,
            agent_port=6831,
        )
        provider.add_span_processor(
            BatchSpanProcessor(jaeger_exporter)
        )
    
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app)
    HTTPXClientInstrumentor().instrument()

tracer = trace.get_tracer(__name__)
```

### 트레이스 시각화
- Jaeger UI: `http://jaeger.internal:16686`
- Agent 실행 트리, Tool 호출 시간, LLM 호출 추적 모두 시각화

---

## 10. 실시간 API 대체 데이터 준비

### 환율 — 사전 수집 CSV

```bash
# 인터넷 환경에서 1년치 환율 수집
python scripts/collect_historical_exchange.py \
  --start 2024-01-01 --end 2025-12-31 \
  --output ./data/historical/exchange.csv

# 내부망에서 PostgreSQL 적재
python scripts/load_historical_exchange.py
```

### 뉴스 — 내부 RSS 또는 샘플

```python
# 옵션 1: 사내 뉴스 시스템 RSS 파싱
# 옵션 2: 사전 수집된 1주일치 뉴스 샘플 사용

# app/data/samples/sample_news.json
[
    {
        "title": "시멘트 수요 둔화 우려",
        "link": "internal://news/001",
        "description": "...",
        "pub_date": "2025-05-06T09:00:00"
    }
]
```

### 날씨 — 기상청 FTP 또는 샘플

```bash
# 옵션 1: 기상청 FTP 내부망 연동 (필요 시 별도 협의)
# 옵션 2: 샘플 데이터 활용
```

---

## 11. 에어갭 배포 절차

```bash
# === 인터넷 환경 (사전 작업) ===

# 1. 모델 다운로드
python scripts/download_models.py

# 2. Docker 이미지 풀 + Harbor 푸시
bash scripts/push_to_harbor.sh

# 3. PyPI 패키지 다운로드 + devpi 업로드
pip download -r requirements.txt -d ./packages
devpi upload ./packages/*

# 4. Ollama 모델 다운로드
ollama pull gemma2:9b
tar -czf ollama-models.tar.gz ~/.ollama

# 5. 모든 자료 압축
tar -czf cement-rag-airgap-v0.1.0.tar.gz \
    ./models \
    ./packages \
    ./ollama-models.tar.gz \
    ./k8s \
    ./scripts \
    ./docker-compose.yml

# === 내부망 반입 ===
# (USB / 폐쇄망 파일전송 시스템)

# === 내부망 환경 ===

# 1. 압축 해제
tar -xzf cement-rag-airgap-v0.1.0.tar.gz

# 2. Harbor에서 이미지 풀
# (이미 사전 푸시되어 있음)

# 3. 환경변수 설정
export AIRGAP_MODE=true
export LLM_BACKEND=local
export EMBEDDING_MODEL_PATH=./models/ko-sroberta

# 4. K8s 배포
kubectl apply -f k8s/

# 5. 동작 확인
curl http://cement-rag.internal/health
```

---

## 12. 에어갭 검증 체크리스트

- [ ] 모든 K8s Pod 정상 기동 (외부 이미지 풀 시도 없음)
- [ ] Ollama 모델 로딩 확인 (`docker exec ollama ollama list`)
- [ ] 임베딩 모델 로딩 확인 (로컬 경로에서)
- [ ] `AIRGAP_MODE=true` 상태로 예시 질의 5개 정상 응답
- [ ] 외부 API 호출 시도 없음 (네트워크 모니터링)
- [ ] Jaeger 트레이스 정상 수집
- [ ] Grafana 대시보드 정상 표시
- [ ] LLM 응답이 외부로 전송되지 않음 확인 (방화벽 로그)

---

## 13. 도입 효과

이 설계로 얻을 수 있는 효과는 다음과 같습니다.

1. **고객 보안 정책 직접 대응** — 시멘트·철강 제조업 고객사의 폐쇄망 환경에서도 동작 가능
2. **데이터 외부 유출 차단** — `LLM_BACKEND=local` + `AIRGAP_MODE=true` 조합으로 모든 데이터가 내부에서만 처리
3. **단일 환경변수 전환** — 고객사 보안 수준에 따라 코드 변경 없이 백엔드 전환
4. **실 납품 가능성** — 실제 고객사 납품 가능한 수준의 설계
