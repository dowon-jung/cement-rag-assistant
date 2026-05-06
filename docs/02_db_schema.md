# DB 스키마 설계

## 1. 전체 구조

```
PostgreSQL (수치·캐시·ERP 데이터)
├── market_rates       환율 캐시
├── news_cache         뉴스 캐시
├── weather_cache      날씨 캐시
├── coal_prices        유연탄 가격 (집계용)
└── production_logs    ERP 생산 로그 (시뮬레이션)

Qdrant (벡터 검색)
├── regulations        환경부 규제 문서
├── coal_prices        유연탄 가격 (의미 검색용)
├── manuals            생산 매뉴얼
└── quality_standards  품질검사 기준서
```

---

## 2. PostgreSQL 테이블 정의

### market_rates (환율 캐시)

```sql
CREATE TABLE market_rates (
    id          SERIAL PRIMARY KEY,
    currency    VARCHAR(10)    NOT NULL,           -- 'USD/KRW'
    rate        NUMERIC(10, 2) NOT NULL,
    base_date   DATE           NOT NULL,
    fetched_at  TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    UNIQUE (currency, base_date)
);

CREATE INDEX idx_market_rates_date ON market_rates (base_date DESC);
```

---

### news_cache (뉴스 캐시)

```sql
CREATE TABLE news_cache (
    id           SERIAL PRIMARY KEY,
    keyword      VARCHAR(100)   NOT NULL,           -- 검색 키워드
    title        TEXT           NOT NULL,
    link         TEXT           NOT NULL UNIQUE,
    description  TEXT,
    pub_date     TIMESTAMPTZ,
    fetched_at   TIMESTAMPTZ    NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_news_cache_keyword    ON news_cache (keyword);
CREATE INDEX idx_news_cache_pub_date   ON news_cache (pub_date DESC);
CREATE INDEX idx_news_cache_fetched_at ON news_cache (fetched_at DESC);
```

---

### weather_cache (날씨 캐시)

```sql
CREATE TABLE weather_cache (
    id              SERIAL PRIMARY KEY,
    nx              INTEGER        NOT NULL,        -- 기상청 격자 X
    ny              INTEGER        NOT NULL,        -- 기상청 격자 Y
    forecast_date   DATE           NOT NULL,
    forecast_time   VARCHAR(4)     NOT NULL,        -- '0600', '1200' 등
    tmp             NUMERIC(5, 1),                  -- 기온 (°C)
    pop             INTEGER,                        -- 강수확률 (%)
    wsd             NUMERIC(5, 1),                  -- 풍속 (m/s)
    sky             INTEGER,                        -- 하늘상태 (1맑음~4흐림)
    fetched_at      TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    UNIQUE (nx, ny, forecast_date, forecast_time)
);
```

---

### coal_prices (유연탄 가격)

```sql
CREATE TABLE coal_prices (
    id          SERIAL PRIMARY KEY,
    price_date  DATE           NOT NULL UNIQUE,
    price_usd   NUMERIC(10, 2) NOT NULL,            -- 달러 기준 가격 ($/톤)
    price_krw   NUMERIC(12, 2),                     -- 원화 환산 (시점 환율 적용)
    source      VARCHAR(100),
    created_at  TIMESTAMPTZ    NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_coal_prices_date ON coal_prices (price_date DESC);
```

---

### production_logs (ERP 생산 로그 — 시뮬레이션)

```sql
CREATE TABLE production_logs (
    id              SERIAL PRIMARY KEY,
    log_date        DATE           NOT NULL,
    product_type    VARCHAR(50)    NOT NULL,        -- '보통포틀랜드', '고로슬래그' 등
    production_qty  NUMERIC(12, 2) NOT NULL,        -- 생산량 (톤)
    inventory_qty   NUMERIC(12, 2),                 -- 재고량 (톤)
    plant_code      VARCHAR(20)    NOT NULL,        -- 공장 코드
    quality_grade   VARCHAR(10),                    -- 품질 등급
    created_at      TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    UNIQUE (log_date, product_type, plant_code)
);

CREATE INDEX idx_production_logs_date  ON production_logs (log_date DESC);
CREATE INDEX idx_production_logs_plant ON production_logs (plant_code);
```

---

## 3. Qdrant 컬렉션 정의

### regulations (환경부 규제)

```python
collection_name = "regulations"

vectors_config = VectorParams(
    size=768,                        # ko-sroberta 출력 차원
    distance=Distance.COSINE
)

# payload 스키마 (필터링용)
payload_schema = {
    "source":      str,              # 파일명 또는 URL
    "law_name":    str,              # 법령명 (e.g. '대기환경보전법')
    "page":        int,              # 원본 PDF 페이지
    "chunk_index": int,              # 문서 내 청크 순번
    "updated_at":  str,              # ISO 날짜
}
```

---

### coal_prices (유연탄 — 의미 검색용)

```python
collection_name = "coal_prices"

vectors_config = VectorParams(
    size=768,
    distance=Distance.COSINE
)

payload_schema = {
    "year":       int,
    "month":      int,
    "price_usd":  float,
    "source":     str,
}
```

---

### manuals (생산 매뉴얼)

```python
collection_name = "manuals"

vectors_config = VectorParams(
    size=768,
    distance=Distance.COSINE
)

payload_schema = {
    "source":       str,
    "section":      str,             # 챕터/섹션명
    "page":         int,
    "chunk_index":  int,
    "product_type": str,             # 해당 시멘트 품종
}
```

---

### quality_standards (품질검사 기준)

```python
collection_name = "quality_standards"

vectors_config = VectorParams(
    size=768,
    distance=Distance.COSINE
)

payload_schema = {
    "source":      str,
    "ks_code":     str,              # KS 기준 코드 (e.g. 'KS L 5201')
    "page":        int,
    "chunk_index": int,
}
```

---

## 4. 데이터 접근 패턴 정리

| 질의 유형 | 접근 대상 | 방식 |
|-----------|-----------|------|
| "오늘 환율은?" | market_rates | PostgreSQL SELECT (캐시 hit) or API 호출 후 upsert |
| "최신 시멘트 뉴스" | news_cache | PostgreSQL SELECT (TTL 체크) or API 호출 후 insert |
| "이번 달 생산량 vs 전년" | production_logs | PostgreSQL GROUP BY + 집계 |
| "유연탄 가격 추이" | coal_prices (PG) | PostgreSQL SELECT + 시계열 집계 |
| "환경부 질소산화물 기준" | regulations (Qdrant) | Hybrid Search (BM25 + Vector) |
| "시멘트 양생 온도 기준" | manuals (Qdrant) | Vector Search |
| "원화 기준 유연탄 원가" | market_rates + coal_prices | JOIN 또는 Tool 2개 순차 호출 |
