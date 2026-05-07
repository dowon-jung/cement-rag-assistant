# 06. 검색 품질 평가 기준

## 1. 평가 목적

설계 결정을 **수치 데이터로 증명**하기 위한 평가 파이프라인입니다.  
"왜 이렇게 설계했나요?" 질문에 "이런 이유로 0.15 → 0.78까지 향상되었습니다"로 답하기 위함입니다.

---

## 2. 평가 지표

### RAGAS 핵심 지표

| 지표 | 의미 | 목표 |
|------|------|------|
| **Faithfulness** | 답변이 검색된 문서에 근거하는지 | ≥ 0.85 |
| **Answer Relevancy** | 질의와 답변의 연관성 | ≥ 0.80 |
| **Context Recall** | 필요한 문서가 실제로 검색됐는지 | ≥ 0.75 |
| **Context Precision** | 검색된 문서의 정확도 | ≥ 0.70 |

### 검색 품질 지표

| 지표 | 의미 | 측정 방법 |
|------|------|-----------|
| **MRR@5** | 정답 문서의 평균 역순위 | 정답 위치의 1/rank 평균 |
| **Hit@K** | 상위 K개에 정답 포함 비율 | K=1, 3, 5 |
| **NDCG@K** | 정답 문서의 순위 가중치 평가 | K=5 |

### 응답 성능 지표

| 지표 | 의미 |
|------|------|
| **TTFT** | Time To First Token (스트리밍 시작까지) |
| **Total Latency** | 전체 응답 완료까지 |
| **TPS** | Tokens per Second |

---

## 3. 골든 셋 구성

### 파일 구조 (`app/evaluation/golden_set.json`)

```json
[
  {
    "id": "Q001",
    "query": "환경부 질소산화물 배출 기준은?",
    "category": "regulation",
    "complexity": "medium",
    "expected_docs": [
      "regulations/대기환경보전법_시행규칙_별표_chunk_023.txt"
    ],
    "expected_answer_keywords": [
      "0.004", "kg/Sm³", "대기환경보전법"
    ],
    "ground_truth": "환경부 기준에 따르면 질소산화물 배출 기준은 0.004kg/Sm³ 이하입니다."
  },
  {
    "id": "Q002",
    "query": "오늘 환율 기준 유연탄 원가가 전월 대비 어떻게 됐어?",
    "category": "composite",
    "complexity": "complex",
    "expected_agents": ["market_agent"],
    "expected_data_sources": ["market_rates", "coal_prices"],
    "ground_truth": null,
    "eval_method": "agent_trace",
    "eval_criteria": {
      "note": "ground_truth 없는 복합 질의는 RAGAS 대신 Agent 트레이스 기반 평가",
      "checks": [
        "market_agent 호출 여부",
        "market_rates + coal_prices 양쪽 조회 여부",
        "응답에 환율 수치 포함 여부",
        "응답에 원가 변동률 포함 여부"
      ]
    }
  }
]
```

### 골든 셋 카테고리별 분포

| 카테고리 | 개수 | 비고 |
|----------|------|------|
| regulation (단순) | 5 | Vector Search 검증 |
| regulation (복합) | 3 | GraphRAG 검증 |
| market | 4 | Market Agent 검증 |
| news | 3 | News Agent 검증 |
| production | 3 | ERP Agent 검증 |
| composite | 2 | 병렬 Sub-Agent 검증 |
| **합계** | **20** | |

---

## 4. 평가 실행

### 스크립트 (`app/evaluation/evaluate.py`)

```python
from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_recall,
    context_precision,
)

async def run_evaluation(
    golden_set_path: str,
    config: EvalConfig,
) -> EvalReport:
    """
    config로 청킹 전략, Re-ranker 사용 여부 등 변경 가능
    """
    results = []
    for item in load_golden_set(golden_set_path):
        # Agent 실행
        response = await agent.run(item["query"])
        results.append({
            "question": item["query"],
            "answer": response.answer,
            "contexts": response.sources,
            "ground_truth": item["ground_truth"],
        })
    
    # RAGAS 평가
    scores = evaluate(
        dataset=results,
        metrics=[
            faithfulness,
            answer_relevancy,
            context_recall,
            context_precision,
        ]
    )
    
    return EvalReport(
        config=config,
        scores=scores,
        timestamp=datetime.now()
    )
```

### 실행 명령
```bash
# 기본 평가
python -m app.evaluation.evaluate

# 특정 설정으로 평가
python -m app.evaluation.evaluate \
  --chunk-size 512 --overlap 64 --use-reranker

# 결과 저장 위치
docs/eval_results/{date}_{config_hash}.md
```

---

## 5. A/B 비교 실험 설계

### 실험 1 — 청킹 전략 비교

| 실험 | chunk_size | overlap | 측정 |
|------|------------|---------|------|
| A | 256 | 0 | Context Recall, MRR@5 |
| B | 256 | 32 | 동일 |
| C | 512 | 64 | 동일 |
| D | 1024 | 128 | 동일 |

**가설**: 너무 짧으면 맥락 손실, 너무 길면 노이즈 → 512 + overlap 64가 최적

### 실험 2 — Re-ranker 도입 전후

| 실험 | 검색 방식 | 측정 |
|------|-----------|------|
| Baseline | Vector only | MRR@5, Hit@1 |
| +ES BM25 | Vector + Elasticsearch(nori) Hybrid | 동일 |
| +Re-ranker | Hybrid + Cross-Encoder | 동일 |

**가설**: Re-ranker가 상위 K개 정밀도를 크게 향상

### 실험 3 — Query Rewriting 효과

| 실험 | 처리 | 측정 |
|------|------|------|
| Raw query | 사용자 질의 그대로 | Context Recall |
| Rewritten | LLM 재작성 후 검색 | 동일 |

**가설**: 구어체 질의에서 효과가 큼

### 실험 4 — Vector vs GraphRAG vs 결합

| 실험 | 방식 | 측정 |
|------|------|------|
| A | Vector only | Faithfulness |
| B | GraphRAG only | 동일 |
| C | Vector + Graph 결합 | 동일 |

**가설**: 복합 규제 질의에서 GraphRAG가 우위, 일반 질의는 Vector가 충분

### 실험 5 — Self-RAG 효과

| 실험 | 처리 | 측정 |
|------|------|------|
| Without | 단일 검색 | Faithfulness |
| With Self-RAG | 자가 평가 + 재검색 | 동일 + 평균 retry 횟수 |

**가설**: 정확도 향상, 단 응답 시간 증가 트레이드오프

### 실험 6 — Adaptive RAG 응답 시간

| 실험 | 전략 | 측정 |
|------|------|------|
| Always Complex | 모든 질의에 풀 파이프라인 | 평균 응답 시간 |
| Adaptive | 난이도별 전략 분기 | 동일 |

**가설**: 평균 응답 시간 단축, 품질은 유지

---

## 6. 결과 기록 포맷 (`docs/eval_results/{experiment}.md`)

```markdown
# 청킹 전략 A/B 실험 결과

## 환경
- 실행일: 2026-XX-XX
- 골든 셋: golden_set_v1.json (20개 질의)
- LLM: Gemma2:9b (Ollama)

## 결과

| 실험 | chunk_size | overlap | Faithfulness | Context Recall | MRR@5 |
|------|------------|---------|--------------|----------------|-------|
| A    | 256        | 0       | 0.72         | 0.61           | 0.43  |
| B    | 256        | 32      | 0.78         | 0.69           | 0.51  |
| C    | 512        | 64      | 0.86         | 0.78           | 0.67  |
| D    | 1024       | 128     | 0.81         | 0.74           | 0.59  |

## 결론

chunk_size 512 + overlap 64가 모든 지표에서 최고 성능.
설계 문서 01에 명시한 기본값 유효성 입증.
```

---

## 7. CI 통합

```yaml
# .github/workflows/eval.yml
on:
  pull_request:
    paths:
      - 'app/indexing/**'
      - 'app/agent/**'

jobs:
  evaluate:
    steps:
      - run: python -m app.evaluation.evaluate --quick
      - run: |
          # 주요 지표 회귀 시 PR 차단
          python scripts/check_regression.py
```

PR마다 골든 셋 일부(5개)로 빠른 평가를 돌려 회귀를 방지합니다.
