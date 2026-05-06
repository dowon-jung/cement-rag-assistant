# 데이터 흐름 설계

## 1. 데이터 소스 분류

| 구분 | 소스 | 형태 | 수집 주기 | 저장 대상 |
|------|------|------|-----------|-----------|
| 실시간 API | 한국은행 ECOS (환율) | REST JSON | 호출 시 실시간 | PostgreSQL |
| 실시간 API | 네이버 뉴스 검색 | REST JSON | 호출 시 실시간 | PostgreSQL (캐시) |
| 실시간 API | 기상청 단기예보 | REST JSON | 호출 시 실시간 | PostgreSQL |
| 문서 RAG | 환경부 대기오염 배출 기준 | PDF | 최초 1회 + 법령 개정 시 | Qdrant |
| 문서 RAG | 유연탄 가격 통계 | CSV | 월 1회 | Qdrant + PostgreSQL |
| 사내 시뮬레이션 | 생산 매뉴얼 | PDF | 최초 1회 | Qdrant |
| 사내 시뮬레이션 | ERP 생산·재고 리포트 | CSV | 일 1회 (배치) | PostgreSQL |
| 사내 시뮬레이션 | 품질검사 기준서 | PDF | 최초 1회 | Qdrant |

---

## 2. 수집 파이프라인

### 2-1. 실시간 API — 한국은행 환율 (ECOS)

```
호출 트리거: GET /market/today 또는 Agent Tool 호출
      │
      ▼
[exchange_api.py]
  ECOS API 호출
  통계표 코드: 731Y001 (원/달러 매매기준율)
      │
      ▼
  응답 파싱 (날짜, 환율값)
      │
      ├─ PostgreSQL market_rates 테이블 upsert (캐시, TTL 1시간)
      │
      └─ Agent에 반환
```

**API 스펙**
```
GET https://ecos.bok.or.kr/api/StatisticSearch/{API_KEY}/json/kr/1/1/731Y001/DD/{날짜}/{날짜}/0000001
응답: {"StatisticSearch": {"row": [{"TIME": "20250506", "DATA_VALUE": "1380.0"}]}}
```

---

### 2-2. 실시간 API — 네이버 뉴스 검색

```
호출 트리거: GET /news/summary 또는 Agent Tool 호출
      │
      ▼
[news_api.py]
  키워드: "시멘트 수요", "건설 경기", "유연탄 가격" 등
  Naver Search API 호출 (display=10, sort=date)
      │
      ▼
  응답 파싱 (제목, 링크, 요약, 날짜)
      │
      ├─ PostgreSQL news_cache 테이블 upsert (TTL 30분)
      │
      └─ LLM 요약 후 Agent에 반환
```

**API 스펙**
```
GET https://openapi.naver.com/v1/search/news.json?query=시멘트&display=10&sort=date
Headers: X-Naver-Client-Id, X-Naver-Client-Secret
```

---

### 2-3. 실시간 API — 기상청 단기예보

```
호출 트리거: GET /weather/today 또는 Agent Tool 호출
      │
      ▼
[weather_api.py]
  격자 좌표 변환 (위경도 → nx, ny)
  단기예보 API 호출
      │
      ▼
  응답 파싱 (기온, 강수확률, 풍속)
      │
      ├─ PostgreSQL weather_cache 테이블 upsert (TTL 1시간)
      │
      └─ Agent에 반환
```

---

### 2-4. 문서 RAG — 환경부 PDF

```
트리거: python -m app.indexing.pipeline --source regulation
      │
      ▼
[regulation_pdf.py]
  PDF 다운로드 or 로컬 파일 로드
      │
      ▼
[chunking/semantic.py]
  Semantic chunking
  - chunk_size: 512 tokens
  - chunk_overlap: 64 tokens
  - splitter: RecursiveCharacterTextSplitter
      │
      ▼
[embedding.py]
  jhgan/ko-sroberta-multitask
  벡터 생성 (768 dim)
      │
      ▼
  Qdrant "regulations" 컬렉션 upsert
  payload: {source, page, chunk_index, law_name, updated_at}
```

---

### 2-5. 문서 RAG — 유연탄 가격 CSV

```
트리거: python -m app.indexing.pipeline --source coal
      │
      ▼
[coal_price.py]
  한국자원정보서비스 CSV 로드
      │
      ├─ [chunking/table_aware.py]
      │    행 단위 청킹 (월별 가격 데이터)
      │    헤더 + N행 묶음으로 청킹
      │         │
      │         ▼
      │    Qdrant "coal_prices" 컬렉션 upsert
      │    payload: {year, month, price_usd, source}
      │
      └─ PostgreSQL coal_prices 테이블 upsert (집계 쿼리용)
```

---

### 2-6. 사내 시뮬레이션 — ERP CSV (배치)

```
트리거: 일 1회 배치 (cron) or 수동 실행
      │
      ▼
[erp_collector.py]
  samples/erp_daily.csv 로드 (시뮬레이션)
      │
      ▼
  데이터 검증 (날짜, 수량, 품목 유효성)
      │
      ▼
  PostgreSQL production_logs 테이블 upsert
  (벡터 인덱싱 없음 — SQL 집계로만 활용)
```

---

## 3. 청킹 전략 결정 기준

```
문서 유형 판별
      │
      ├─ PDF이고 법령/매뉴얼 텍스트 → Semantic chunking
      │    이유: 문장 간 의미 연결이 중요, 단락 경계에서 분할
      │
      ├─ CSV이고 시계열/가격 데이터 → Table-aware chunking
      │    이유: 행·열 관계 파괴 시 수치 의미 손실
      │    방식: header + N rows 단위로 묶어 하나의 chunk 생성
      │
      └─ 실시간 API JSON → Structured store (청킹 없음)
           이유: 집계/증감 연산은 SQL이 벡터 검색보다 정확
```

---

## 4. 데이터 갱신 전략

| 데이터 | 갱신 방식 | TTL / 주기 |
|--------|-----------|------------|
| 환율 | PostgreSQL 캐시 + TTL | 1시간 |
| 뉴스 | PostgreSQL 캐시 + TTL | 30분 |
| 날씨 | PostgreSQL 캐시 + TTL | 1시간 |
| 유연탄 가격 | 월 1회 배치 재인덱싱 | 월 1회 |
| 환경부 PDF | 법령 개정 시 수동 트리거 | 수시 |
| ERP | 일 1회 배치 upsert | 1일 |
