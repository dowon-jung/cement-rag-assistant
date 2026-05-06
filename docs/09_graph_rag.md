# 09. GraphRAG 설계

## 1. GraphRAG 도입 목적

벡터 검색만으로는 처리할 수 없는 **관계 기반 질의**를 해결하기 위함입니다.

### Vector RAG의 한계

```
질의: "질소산화물 기준치 초과 시 어떤 조항이 연쇄 적용되나?"
      │
      ▼
Vector Search → "질소산화물" 관련 문서 청크 5개
      │
      ▼
LLM은 청크 5개만 보고 답변
      → 청크 간 의존 관계, 연쇄 조항을 놓침
```

### GraphRAG의 해법

```
질의 → 그래프 탐색
      ┌──────────────────────────────┐
      │  대기환경보전법                │
      │   ├─ 16조 (배출허용기준)      │
      │   │   └─ 질소산화물 0.004     │
      │   │       └─ 초과 시 → 19조   │  ← 연쇄 관계 추적
      │   ├─ 19조 (개선명령)          │
      │   │   └─ 미이행 시 → 41조     │
      │   └─ 41조 (벌칙)              │
      └──────────────────────────────┘
      → LLM에 연쇄 경로 전체 전달
```

---

## 2. 적용 범위

### GraphRAG 사용 케이스
- 법령 간 참조 관계 추적
- 조항의 연쇄 적용 (위반 → 명령 → 벌칙)
- 오염물질-시설-기준의 다중 조건 매칭
- 복합 규제 질의

### Vector RAG 유지 케이스
- 단순 키워드 검색 ("질소산화물 기준이 뭐야?")
- 매뉴얼 일반 검색 ("양생 온도는?")
- 의미 유사 문서 탐색

---

## 3. 그래프 스키마

### 노드 타입

```cypher
(:Law {
    code: "AIR_ENV_LAW",          // 법령 코드 (PK)
    name: "대기환경보전법",
    enacted_date: "2025-01-01"
})

(:Article {
    law_code: "AIR_ENV_LAW",      // 복합 PK
    number: "16",                  // 조항 번호
    title: "배출허용기준"
})

(:Standard {
    id: "NOX_STD_001",
    type: "배출허용기준",
    value: 0.004,
    unit: "kg/Sm³"
})

(:Pollutant {
    name: "질소산화물",            // PK
    category: "대기오염물질"
})

(:Facility {
    type: "시멘트소성로",
    capacity_min: 0,
    capacity_max: 999999
})
```

### 엣지 타입

```cypher
// 법령 구조
(:Law)-[:CONTAINS]->(:Article)

// 규제 관계
(:Article)-[:REGULATES]->(:Standard)
(:Standard)-[:APPLIES_TO]->(:Pollutant)
(:Standard)-[:APPLIES_TO]->(:Facility)

// 조항 간 관계
(:Article)-[:REFERENCES]->(:Article)        // 단순 참조
(:Article)-[:DEPENDS_ON {condition: "위반"}]->(:Article)  // 연쇄 적용
(:Article)-[:OVERRIDES]->(:Article)         // 우선 적용
```

---

## 4. 인덱싱 흐름

```
환경부 PDF 입력
    │
    ▼
[1단계] 텍스트 추출 (PyMuPDF)
    │
    ▼
[2단계] 구조화 파싱 (LLM 또는 규칙 기반)
    - 법령명, 조항 번호, 제목 추출
    - 조항 본문에서 수치 기준 추출
    - 조항 간 참조 관계 식별 ("제19조에 따라" 등)
    │
    ▼
[3단계] Cypher 쿼리 생성
    - 노드 MERGE (이미 있으면 무시)
    - 엣지 CREATE
    │
    ▼
[4단계] Neo4j 적재
    - app/indexing/graph_indexer.py
    - 트랜잭션 단위로 처리
    - 실패 시 Kafka dlq.errors 발행
```

### 구조화 파싱 프롬프트

```python
GRAPH_EXTRACTION_PROMPT = """
다음 법령 조항 텍스트에서 그래프 노드와 엣지를 추출하세요.

입력:
{article_text}

출력 JSON:
{
  "article": {
    "number": "16",
    "title": "배출허용기준"
  },
  "standards": [
    {
      "type": "배출허용기준",
      "value": 0.004,
      "unit": "kg/Sm³",
      "pollutant": "질소산화물",
      "facility": "시멘트소성로"
    }
  ],
  "references": [
    {"article_number": "19", "relation": "DEPENDS_ON", "condition": "위반"}
  ]
}
"""
```

---

## 5. Cypher 쿼리 패턴

### 패턴 1 — 단일 기준 조회
```cypher
MATCH (l:Law)-[:CONTAINS]->(a:Article)-[:REGULATES]->(s:Standard)
      -[:APPLIES_TO]->(p:Pollutant {name: $pollutant})
RETURN l.name, a.number, s.value, s.unit
```

### 패턴 2 — 연쇄 조항 추적
```cypher
MATCH path = (start:Article {number: $article_number})
            -[:DEPENDS_ON*1..5]->
            (target:Article)
WHERE start.law_code = $law_code
RETURN [n in nodes(path) | n.number + ': ' + n.title] AS cascade_path
```

### 패턴 3 — 다중 조건 매칭
```cypher
MATCH (s:Standard)-[:APPLIES_TO]->(p:Pollutant)
MATCH (s)-[:APPLIES_TO]->(f:Facility)
WHERE p.name = $pollutant
  AND f.type = $facility_type
  AND s.value <= $current_value
RETURN s.id, s.value, "초과" AS status
```

### 패턴 4 — 우선 적용 법령
```cypher
MATCH (specific:Article)-[:OVERRIDES]->(general:Article)
WHERE general.law_code = $law_code
  AND general.number = $article_number
RETURN specific.law_code, specific.number, specific.title
```

---

## 6. RAG Agent 내부 분기

```python
async def rag_agent(query: str) -> dict:
    # 1. 질의 유형 판별
    query_type = await classify_rag_query(query)
    # query_type: "vector" | "graph" | "hybrid"
    
    if query_type == "vector":
        return await vector_search_only(query)
    
    elif query_type == "graph":
        return await graph_search_only(query)
    
    else:  # hybrid
        # 병렬 실행
        vector_results, graph_results = await asyncio.gather(
            vector_search(query),
            graph_search(query),
        )
        return merge_results(vector_results, graph_results)
```

### 질의 유형 분류 프롬프트

```python
RAG_TYPE_CLASSIFIER = """
사용자 질의가 어떤 검색이 필요한지 분류하세요.

- vector: 단순 키워드/의미 검색
  예) "질소산화물 기준이 뭐야?"
- graph: 관계/연쇄 추적 필요
  예) "기준 초과 시 어떤 조항이 연쇄 적용되나?"
- hybrid: 둘 다 필요
  예) "시멘트 공장에 적용되는 모든 대기 규제와 위반 시 처벌은?"

JSON: {"type": "vector|graph|hybrid", "reasoning": "..."}
"""
```

---

## 7. Vector + Graph 결합 전략

### 결과 병합 방식

```python
def merge_results(
    vector_results: List[VectorChunk],
    graph_results: GraphResult,
) -> List[MergedChunk]:
    merged = []
    
    # 1. Graph 결과의 각 조항을 Vector에서 풀텍스트 검색
    for article in graph_results.articles:
        text_chunks = vector_search_by_metadata(
            law_name=article.law_name,
            article_number=article.number,
        )
        merged.append(MergedChunk(
            text=text_chunks,
            graph_context=article,
            source="graph+vector"
        ))
    
    # 2. Vector 결과 중 Graph에 없는 것 추가
    for vchunk in vector_results:
        if not any(m.matches(vchunk) for m in merged):
            merged.append(MergedChunk(
                text=vchunk.text,
                graph_context=None,
                source="vector"
            ))
    
    return merged
```

### Synthesizer에 전달

```
[참고 문서]

1. 대기환경보전법 제16조 (배출허용기준) — 본문
   "질소산화물 배출허용기준은 0.004kg/Sm³ 이하..."

2. 연쇄 적용 경로 (Graph)
   16조 → 19조 (개선명령) → 41조 (벌칙)

3. 대기환경보전법 제19조 (개선명령) — 본문
   "환경부장관은 배출허용기준을 초과한 사업자에 대하여..."

[질문]
질소산화물 기준 초과 시 어떻게 되나?
```

---

## 8. 비교 실험

### 실험 — Vector only vs GraphRAG vs 결합

골든 셋 중 복합 규제 질의 5개에 대해 비교.

| 실험 | Faithfulness | Context Recall | 응답 시간 |
|------|--------------|----------------|-----------|
| Vector only | 측정 예정 | 측정 예정 | 측정 예정 |
| Graph only | 측정 예정 | 측정 예정 | 측정 예정 |
| Vector + Graph | 측정 예정 | 측정 예정 | 측정 예정 |

**가설**:
- Vector only — 기본 키워드는 잡지만 연쇄 관계 누락
- Graph only — 연쇄는 잡지만 본문 디테일 부족
- 결합 — Faithfulness 가장 높음, 응답 시간은 약간 증가

결과는 `docs/eval_results/graph_rag_eval.md`에 기록.

---

## 9. 운영 고려사항

### 그래프 갱신 전략
- 법령 개정 시 영향받는 노드/엣지만 부분 갱신
- 전체 재인덱싱은 분기마다 1회

### 그래프 크기 추정
- 환경부 주요 대기 관련 법령 5개
- 평균 조항 수 50개 → 250 Article 노드
- 수치 기준 약 500개 → 500 Standard 노드
- 오염물질 30종, 시설 50종
- **총 노드 ~1,000개, 엣지 ~3,000개**

소규모이므로 Neo4j Community Edition으로 충분.

### 백업
- 주 1회 `neo4j-admin database dump` 실행
- S3 또는 내부 백업 서버에 저장
