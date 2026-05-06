# 07. 모델 서빙 비교 설계

## 1. 비교 대상

| 백엔드 | 위치 | 데이터 외부 전송 | 사용 시점 |
|--------|------|------------------|-----------|
| **Ollama** | 로컬 / 사내 서버 | 없음 | 개발, 폐쇄망 고객사 |
| **vLLM** | 로컬 / 사내 서버 | 없음 | 프로덕션, 고처리량 |
| **AWS Bedrock** | 고객 VPC | VPC 내 격리 | AWS 사용 고객사 |
| **Anthropic API** | Anthropic 서버 | 있음 | 엔터프라이즈 계약 시 |

---

## 2. 측정 지표

| 지표 | 의미 | 단위 |
|------|------|------|
| **TTFT** | Time To First Token (스트리밍 첫 토큰까지) | ms |
| **TPS** | Tokens per Second (생성 속도) | tok/s |
| **Total Latency** | 전체 응답 완료 시간 | ms |
| **동시 처리량** | N개 동시 요청 시 평균 응답 시간 | ms |
| **GPU 메모리** | 모델 로딩 + 추론 시 사용량 | GB |
| **품질** | RAGAS Faithfulness | 0~1 |

---

## 3. 실험 시나리오

### 시나리오 A — 단일 요청 성능

| 모델 | 백엔드 | 입력 토큰 | 출력 토큰 | 측정 |
|------|--------|-----------|-----------|------|
| Gemma2:9b | Ollama | 500 | 200 | TTFT, TPS |
| Gemma2:9b | vLLM | 500 | 200 | TTFT, TPS |
| Claude 3.5 Sonnet | Anthropic API | 500 | 200 | TTFT, TPS |
| Claude 3.5 Sonnet | AWS Bedrock | 500 | 200 | TTFT, TPS |

### 시나리오 B — 동시 요청 처리량

| 동시 요청 수 | 측정 항목 |
|--------------|-----------|
| 1 | 평균 응답 시간 |
| 5 | 평균 응답 시간, p95 |
| 10 | 평균 응답 시간, p95, p99 |
| 20 | 평균 응답 시간, 실패율 |

### 시나리오 C — 품질 비교

골든 셋 20개 질의에 대해 백엔드별 RAGAS 점수 비교

---

## 4. Ollama 환경 구성

```bash
# Docker로 기동
docker run -d --gpus all \
  -p 11434:11434 \
  -v ollama_data:/root/.ollama \
  --name ollama \
  ollama/ollama

# 모델 다운로드
docker exec -it ollama ollama pull gemma2:9b

# 동작 확인
curl http://localhost:11434/api/generate \
  -d '{
    "model": "gemma2:9b",
    "prompt": "시멘트가 뭐야?",
    "stream": false
  }'
```

### 장점
- 설치 간편, 로컬 개발에 최적
- 모델 관리 명령어 제공 (pull, list, rm)

### 단점
- 동시 요청 처리 성능 낮음
- continuous batching 미지원

---

## 5. vLLM 환경 구성

```bash
# GPU 필요, RunPod / Colab Pro / 자체 서버
pip install vllm

# OpenAI 호환 서버 기동
python -m vllm.entrypoints.openai.api_server \
  --model google/gemma-2-9b-it \
  --host 0.0.0.0 \
  --port 8001 \
  --max-model-len 4096 \
  --gpu-memory-utilization 0.9
```

### 장점
- **continuous batching**으로 동시 요청 처리량 우수
- PagedAttention으로 메모리 효율 ↑
- OpenAI API 호환

### 단점
- GPU 필수 (CUDA 12.1+)
- 초기 설정 복잡

---

## 6. AWS Bedrock 연동

```python
# app/core/llm_backends/bedrock.py
import boto3

class BedrockBackend:
    def __init__(self):
        self.client = boto3.client(
            "bedrock-runtime",
            region_name=settings.AWS_REGION,
        )
    
    async def stream(self, messages: list[dict]) -> AsyncIterator[str]:
        response = self.client.invoke_model_with_response_stream(
            modelId=settings.BEDROCK_MODEL_ID,
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1024,
                "messages": messages,
            })
        )
        for event in response["body"]:
            chunk = json.loads(event["chunk"]["bytes"])
            if chunk.get("type") == "content_block_delta":
                yield chunk["delta"]["text"]
```

### 장점
- 고객 VPC 내 격리 (VPC 엔드포인트 사용)
- Claude 품질 그대로
- AWS IAM 통합

### 단점
- AWS 계정 필수
- 리전별 모델 가용성 차이

---

## 7. Anthropic API 연동

```python
# app/core/llm_backends/anthropic_api.py
from anthropic import AsyncAnthropic

class AnthropicBackend:
    def __init__(self):
        self.client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    
    async def stream(self, messages: list[dict]) -> AsyncIterator[str]:
        async with self.client.messages.stream(
            model="claude-opus-4-7",
            max_tokens=1024,
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                yield text
```

### 장점
- 최고 품질 (Claude 직접 사용)
- 빠른 응답 시간

### 단점
- 데이터 외부 전송 (엔터프라이즈 계약 필요)
- 인터넷 연결 필수

---

## 8. LLM 백엔드 추상화 레이어

```python
# app/core/llm_backend.py
from abc import ABC, abstractmethod

class LLMBackend(ABC):
    @abstractmethod
    async def generate(self, messages: list[dict]) -> str: ...
    
    @abstractmethod
    async def stream(self, messages: list[dict]) -> AsyncIterator[str]: ...

def get_llm_backend() -> LLMBackend:
    """환경변수 LLM_BACKEND에 따라 백엔드 반환"""
    backend = settings.LLM_BACKEND
    if backend == "local":
        return OllamaBackend()
    elif backend == "vllm":
        return VLLMBackend()
    elif backend == "bedrock":
        return BedrockBackend()
    elif backend == "anthropic":
        return AnthropicBackend()
    raise ValueError(f"Unknown backend: {backend}")
```

---

## 9. 벤치마크 스크립트

```python
# scripts/benchmark_llm.py
import asyncio
import time
from app.core.llm_backend import get_llm_backend

async def benchmark(backend_name: str, concurrent: int):
    backend = get_llm_backend(backend_name)
    
    async def single_request():
        start = time.time()
        first_token_time = None
        token_count = 0
        
        async for token in backend.stream(test_messages):
            if first_token_time is None:
                first_token_time = time.time()
            token_count += 1
        
        end = time.time()
        return {
            "ttft_ms": (first_token_time - start) * 1000,
            "total_ms": (end - start) * 1000,
            "tps": token_count / (end - first_token_time),
        }
    
    # 동시 요청 실행
    results = await asyncio.gather(*[
        single_request() for _ in range(concurrent)
    ])
    
    return aggregate(results)

# 실행
for backend in ["ollama", "vllm", "bedrock", "anthropic"]:
    for concurrent in [1, 5, 10, 20]:
        result = await benchmark(backend, concurrent)
        save_result(backend, concurrent, result)
```

---

## 10. 결과 정리 포맷 (`docs/eval_results/llm_serving_benchmark.md`)

```markdown
# LLM 서빙 벤치마크 결과

## 환경
- GPU: RTX 4090 24GB (vLLM/Ollama)
- 네트워크: 100Mbps (Bedrock/Anthropic)

## TTFT 비교 (단일 요청)

| 백엔드 | TTFT (ms) | TPS | Total (ms) |
|--------|-----------|-----|------------|
| Ollama | 320 | 45 | 4,800 |
| vLLM | 150 | 95 | 2,250 |
| Bedrock | 480 | 65 | 3,560 |
| Anthropic | 290 | 110 | 2,090 |

## 동시 요청 처리량 (10개 동시)

| 백엔드 | 평균 (ms) | p95 (ms) | 실패율 |
|--------|-----------|----------|--------|
| Ollama | 12,400 | 18,300 | 5% |
| vLLM | 3,200 | 4,800 | 0% |
| Bedrock | 4,100 | 5,900 | 0% |
| Anthropic | 2,600 | 3,400 | 0% |

## 결론
- 개발/폐쇄망: Ollama 충분
- 프로덕션 고처리량: vLLM 권장
- 최고 품질 + 보안 절충: Bedrock
```

---

## 11. 백엔드 선택 가이드

```
시작
  │
  ▼
인터넷 차단 환경?
  ├─ Yes → Ollama or vLLM (로컬)
  │         │
  │         ▼
  │      GPU 보유?
  │         ├─ Yes → vLLM (고처리량)
  │         └─ No  → Ollama (CPU 가능)
  │
  └─ No → 데이터 외부 전송 허용?
          ├─ No  → Ollama / vLLM
          ├─ AWS 사용 → Bedrock
          └─ 엔터프라이즈 계약 → Anthropic API
```
