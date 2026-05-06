# 02. DB 스키마 설계

## 1. 전체 저장소 구조

```
PostgreSQL (수치 · 캐시 영구화 · ERP)
├── market_rates       환율 영구 저장
├── news_cache         뉴스 영구 저장
├── weather_cache      날씨 영구 저장
├── coal_prices        유연탄 가격 (집계용)
└── production_logs    ERP 생산 로그

Redis (휘발성 캐시)
├── exchange:usd_krw:{YYYYMMDD}        TTL 1h
├── news:{keyword}:{YYYYMMDD_HH}       TTL 30m
└── weather:{nx}_{ny}:{YYYYMMDD_HHmm}  TTL 1h

Qdrant (벡터 검색 전용)
├── regulations         환경부 규제 문서
├── coal_prices         유연탄 가격 (의미 검색)
├── manuals             생산 매뉴얼
└── quality_standards   품질검사 기준서

Elasticsearch (한국어 형태소 BM25 검색)
├── regulations         환경부 규제 문서 (nori 분석)
├── coal_prices         유연탄 가격
├── manuals             생산 매뉴얼
└── quality_standards   품질검사 기준서

Neo4j (지식 그래프)
└── 규제 관계 그래프 (법령 → 조항 → 수치기준 → 오염물질)
```

---

## 2. PostgreSQL 테이블 정의

### market_rates
```sql
CREATE TABLE market_rates (
    id          SERIAL PRIMARY KEY,
    currency    VARCHAR(10)    NOT NULL,
    rate        NUMERIC(10, 2) NOT NULL,
    base_date   DATE           NOT NULL,
    fetched_at  TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    UNIQUE (currency, base_date)
);
CREATE INDEX idx_market_rates_date ON market_rates (base_date DESC);
```

### news_cache
```sql
CREATE TABLE news_cache (
    id           SERIAL PRIMARY KEY,
    keyword      VARCHAR(100) NOT NULL,
    title        TEXT         NOT NULL,
    link         TEXT         NOT NULL UNIQUE,
    description  TEXT,
    pub_date     TIMESTAMPTZ,
    fetched_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_news_keyword    ON news_cache (keyword);
CREATE INDEX idx_news_pub_date   ON news_cache (pub_date DESC);
```

### weather_cache
```sql
CREATE TABLE weather_cache (
    id              SERIAL PRIMARY KEY,
    nx              INTEGER       NOT NULL,
    ny              INTEGER       NOT NULL,
    forecast_date   DATE          NOT NULL,
    forecast_time   VARCHAR(4)    NOT NULL,
    tmp             NUMERIC(5, 1),
    pop             INTEGER,
    wsd             NUMERIC(5, 1),
    sky             INTEGER,
    fetched_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    UNIQUE (nx, ny, forecast_date, forecast_time)
);
```

### coal_prices
```sql
CREATE TABLE coal_prices (
    id          SERIAL PRIMARY KEY,
    price_date  DATE           NOT NULL UNIQUE,
    price_usd   NUMERIC(10, 2) NOT NULL,
    price_krw   NUMERIC(12, 2),
    source      VARCHAR(100),
    created_at  TIMESTAMPTZ    NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_coal_prices_date ON coal_prices (price_date DESC);
```

### production_logs (ERP 시뮬레이션)
```sql
CREATE TABLE production_logs (
    id              SERIAL PRIMARY KEY,
    log_date        DATE           NOT NULL,
    product_type    VARCHAR(50)    NOT NULL,
    production_qty  NUMERIC(12, 2) NOT NULL,
    inventory_qty   NUMERIC(12, 2),
    plant_code      VARCHAR(20)    NOT NULL,
    quality_grade   VARCHAR(10),
    created_at      TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    UNIQUE (log_date, product_type, plant_code)
);
CREATE INDEX idx_production_logs_date  ON production_logs (log_date DESC);
CREATE INDEX idx_production_logs_plant ON production_logs (plant_code);
```

---

## 3. Redis 키 설계

| 용도 | 키 패턴 | TTL | 값 형식 |
|------|---------|-----|---------|
| 환율 캐시 | `exchange:usd_krw:{YYYYMMDD}` | 3600s | JSON |
| 뉴스 캐시 | `news:{keyword}:{YYYYMMDD_HH}` | 1800s | JSON Array |
| 날씨 캐시 | `weather:{nx}_{ny}:{YYYYMMDD}_{HHmm}` | 3600s | JSON |
| 임베딩 캐시 | `embed:{hash(text)}` | 86400s | Float Array |
| 검색 결과 캐시 | `search:{collection}:{hash(query)}` | 300s | JSON |

---

## 4. Qdrant 컬렉션 정의

### 공통 설정
```python
vectors_config = VectorParams(
    size=768,                    # ko-sroberta 출력 차원
    distance=Distance.COSINE
)
```

> BM25 키워드 검색은 Qdrant Sparse Vector 대신 **Elasticsearch(nori 형태소 분석)**로 처리합니다.
> 한국어 도메인 특성상 형태소 분석 기반 검색이 Sparse Vector보다 정밀도가 높기 때문입니다.
```

### regulations (환경부 규제)
```python
collection_name = "regulations"
payload_schema = {
    "source":      str,
    "law_name":    str,         # 대기환경보전법 등
    "article":     str,         # 조항 번호
    "page":        int,
    "chunk_index": int,
    "updated_at":  str,
}
```

### coal_prices (유연탄)
```python
collection_name = "coal_prices"
payload_schema = {
    "source":     str,
    "year":       int,
    "month":      int,
    "price_usd":  float,
    "period_label": str,
}
```

### manuals (생산 매뉴얼)
```python
collection_name = "manuals"
payload_schema = {
    "source":       str,
    "section":      str,
    "page":         int,
    "chunk_index":  int,
    "product_type": str,
}
```

### quality_standards (품질검사 기준)
```python
collection_name = "quality_standards"
payload_schema = {
    "source":      str,
    "ks_code":     str,         # KS L 5201 등
    "page":        int,
    "chunk_index": int,
}
```

---

## 5. Elasticsearch 인덱스 정의

### 공통 설정 (nori 형태소 분석기)

```json
{
  "settings": {
    "analysis": {
      "analyzer": {
        "korean": {
          "type": "custom",
          "tokenizer": "nori_tokenizer",
          "filter": ["nori_part_of_speech", "lowercase"]
        }
      }
    }
  }
}
```

### regulations 인덱스

```json
{
  "mappings": {
    "properties": {
      "text":       { "type": "text", "analyzer": "korean" },
      "law_name":   { "type": "keyword" },
      "article":    { "type": "keyword" },
      "page":       { "type": "integer" },
      "chunk_index":{ "type": "integer" },
      "updated_at": { "type": "date" }
    }
  }
}
```

### manuals / coal_prices / quality_standards 인덱스

```json
{
  "mappings": {
    "properties": {
      "text":         { "type": "text", "analyzer": "korean" },
      "source":       { "type": "keyword" },
      "section":      { "type": "keyword" },
      "page":         { "type": "integer" },
      "chunk_index":  { "type": "integer" },
      "product_type": { "type": "keyword" }
    }
  }
}
```

---

## 6. Neo4j 그래프 스키마

### 노드 타입
```cypher
(:Law {name, code, enacted_date})
(:Article {number, title, law_code})
(:Standard {value, unit, type})
(:Pollutant {name, category})
(:Facility {type, capacity})
```

### 엣지 타입
```cypher
(:Law)-[:CONTAINS]->(:Article)
(:Article)-[:REGULATES]->(:Standard)
(:Standard)-[:APPLIES_TO]->(:Pollutant)
(:Standard)-[:APPLIES_TO]->(:Facility)
(:Article)-[:REFERENCES]->(:Article)    # 조항 간 참조 관계
(:Article)-[:DEPENDS_ON]->(:Article)    # 연쇄 적용 관계
```

### 제약조건
```cypher
CREATE CONSTRAINT law_code IF NOT EXISTS
  FOR (l:Law) REQUIRE l.code IS UNIQUE;

CREATE CONSTRAINT article_unique IF NOT EXISTS
  FOR (a:Article) REQUIRE (a.law_code, a.number) IS UNIQUE;

CREATE INDEX pollutant_name IF NOT EXISTS
  FOR (p:Pollutant) ON (p.name);
```

### 예시 데이터
```cypher
CREATE (l:Law {name: "대기환경보전법", code: "AIR_ENV_LAW"})
CREATE (a:Article {number: "16", title: "배출허용기준", law_code: "AIR_ENV_LAW"})
CREATE (s:Standard {value: 0.004, unit: "kg/Sm³", type: "배출허용기준"})
CREATE (p:Pollutant {name: "질소산화물", category: "대기오염물질"})
CREATE (l)-[:CONTAINS]->(a)
CREATE (a)-[:REGULATES]->(s)
CREATE (s)-[:APPLIES_TO]->(p)
```

---

## 6. 질의 유형별 데이터 접근 패턴

| 질의 유형 | 접근 대상 | 처리 방식 |
|-----------|-----------|-----------|
| "오늘 환율은?" | Redis → PostgreSQL → API | TTL 캐시 우선 |
| "최신 시멘트 뉴스" | Redis → PostgreSQL → API | TTL 캐시 우선 |
| "이번 달 생산량 vs 전년" | PostgreSQL | GROUP BY + 집계 |
| "유연탄 가격 추이" | PostgreSQL | 시계열 SELECT |
| "환경부 질소산화물 기준" | Qdrant + Elasticsearch | Vector + BM25(nori) + RRF |
| "시멘트 양생 온도 기준" | Qdrant + Elasticsearch | Vector + BM25(nori) + RRF |
| "원화 기준 유연탄 원가" | PostgreSQL JOIN | exchange + coal JOIN |
| "질소산화물 초과 시 연쇄 조항" | Neo4j Cypher | DEPENDS_ON 관계 탐색 |
| "복합 규제 질의" | Neo4j + Qdrant + Elasticsearch | Graph + Hybrid 결합 |
