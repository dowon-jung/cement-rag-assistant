# 01. 데이터 흐름 설계

## 1. 데이터 소스 전체 목록

| # | 소스 | 형태 | 수집 방식 | 수집 주기 | 최종 저장 |
|---|------|------|-----------|-----------|-----------|
| 1 | 한국은행 ECOS (환율) | REST JSON | API 호출 | 실시간 (캐시 1h) | PostgreSQL |
| 2 | 네이버 뉴스 검색 | REST JSON | API 호출 | 실시간 (캐시 30m) | PostgreSQL |
| 3 | 기상청 단기예보 | REST JSON | API 호출 | 실시간 (캐시 1h) | PostgreSQL |
| 4 | 환경부 대기오염 배출 기준 | PDF | 파일 다운로드 | 최초 1회 + 개정 시 | Qdrant |
| 5 | 유연탄 가격 통계 | CSV | 파일 다운로드 | 월 1회 | Qdrant + PostgreSQL |
| 6 | 생산 매뉴얼 (시뮬레이션) | PDF | 로컬 파일 | 최초 1회 | Qdrant |
| 7 | ERP 생산·재고 리포트 (시뮬레이션) | CSV | 로컬 파일 | 일 1회 (배치) | PostgreSQL |
| 8 | 품질검사 기준서 (시뮬레이션) | PDF | 로컬 파일 | 최초 1회 | Qdrant |

---

## 2. 전체 데이터 흐름 개요

```
외부 데이터 소스
      │
      ├─ 실시간 API (1, 2, 3) ─────────────────────────────────┐
      │                                                         │
      └─ 정적 문서 (4, 5, 6, 8)   배치 데이터 (7)              │
               │                        │                      │
               ▼                        ▼                      ▼
        [인덱싱 파이프라인]       [배치 수집기]         [실시간 수집기]
        문서 파싱 → 청킹          CSV 파싱 →             API 호출 →
        → 임베딩 → Qdrant         PostgreSQL upsert      캐시 확인 →
                                                         PostgreSQL upsert
               │                        │                      │
               └────────────────────────┴──────────────────────┘
                                        │
                                        ▼
                              [LangGraph Agent]
                              질의 분류 → Tool 실행
                                        │
                                        ▼
                                   최종 응답
```

---

## 3. 실시간 API 흐름 (소스 1, 2, 3)

실시간 API는 매 요청마다 외부 호출을 하지 않고 **PostgreSQL 캐시 레이어**를 먼저 확인합니다.

```
Agent Tool 호출
      │
      ▼
PostgreSQL 캐시 조회
      │
      ├─ HIT (TTL 유효) ──→ 캐시 데이터 반환
      │
      └─ MISS (TTL 만료 or 없음)
               │
               ▼
         외부 API 호출
               │
               ▼
         응답 파싱 및 검증
               │
               ├─ 성공 ──→ PostgreSQL upsert → 데이터 반환
               │
               └─ 실패 ──→ 마지막 캐시 데이터 반환 (fallback)
                           없으면 에러 반환
```

### 3-1. 한국은행 ECOS — 환율

```
[exchange_api.py]

호출 URL:
  GET https://ecos.bok.or.kr/api/StatisticSearch/{API_KEY}/json/kr/1/1
      /731Y001/DD/{YYYYMMDD}/{YYYYMMDD}/0000001

응답 파싱:
  StatisticSearch.row[0].DATA_VALUE → 원/달러 환율

저장:
  PostgreSQL market_rates
  (currency='USD/KRW', rate, base_date)

캐시 TTL: 1시간
  - 한국은행 ECOS는 영업일 오전 11시경 고시
  - 장중 변동 없으므로 1시간 TTL로 충분
```

### 3-2. 네이버 뉴스 검색

```
[news_api.py]

호출 URL:
  GET https://openapi.naver.com/v1/search/news.json
      ?query={keyword}&display=10&sort=date
Headers:
  X-Naver-Client-Id: {CLIENT_ID}
  X-Naver-Client-Secret: {CLIENT_SECRET}

검색 키워드 (순차 호출):
  1. "시멘트 수요"
  2. "건설 경기"
  3. "유연탄 가격"

응답 파싱:
  items[].{title, link, description, pubDate}
  HTML 태그 제거 (title, description)

저장:
  PostgreSQL news_cache
  (keyword, title, link, description, pub_date)
  link 기준 UNIQUE → 중복 방지

캐시 TTL: 30분
```

### 3-3. 기상청 단기예보

```
[weather_api.py]

호출 URL:
  GET https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst
      ?serviceKey={API_KEY}&pageNo=1&numOfRows=1000
      &dataType=JSON&base_date={YYYYMMDD}&base_time={HHmm}
      &nx={nx}&ny={ny}

격자 좌표 기본값 (단양 시멘트 공장 인근):
  nx=83, ny=121

응답 파싱:
  category별 값 추출
  TMP(기온), POP(강수확률), WSD(풍속), SKY(하늘상태)

저장:
  PostgreSQL weather_cache
  (nx, ny, forecast_date, forecast_time, tmp, pop, wsd, sky)

캐시 TTL: 1시간
  - 기상청 단기예보는 3시간 단위 발표
  - 1시간 TTL로 충분
```

---

## 4. 문서 인덱싱 흐름 (소스 4, 5, 6, 8)

문서 인덱싱은 **최초 1회 실행** 또는 **데이터 갱신 시 수동 트리거**합니다.

```
python -m app.indexing.pipeline --source {target}
  target: all | regulation | coal | manual | quality
```

### 공통 인덱싱 흐름

```
문서 로드 (PDF or CSV)
      │
      ▼
문서 유형 판별 → 청킹 전략 선택
      │
      ▼
청킹 실행
      │
      ▼
임베딩 생성 (ko-sroberta, 768 dim)
      │
      ▼
Qdrant upsert
(컬렉션별 분리, payload에 메타데이터 포함)
```

### 4-1. 환경부 대기오염 배출 기준 PDF

```
[regulation_pdf.py]

원본: 국가법령정보센터 PDF (대기환경보전법 시행규칙 별표)

처리:
  1. PyMuPDF로 텍스트 추출
  2. Semantic chunking
     - chunk_size: 512 tokens
     - chunk_overlap: 64 tokens
     - 분할 기준: 문단 → 문장 순
  3. 임베딩 생성
  4. Qdrant "regulations" upsert

payload:
  {
    source: "대기환경보전법_시행규칙_별표.pdf",
    law_name: "대기환경보전법",
    page: int,
    chunk_index: int,
    updated_at: "YYYY-MM-DD"
  }
```

### 4-2. 유연탄 가격 CSV

```
[coal_price.py]

원본: 한국자원정보서비스 (kores.net) 월별 가격 CSV
컬럼: 연도, 월, 가격($/톤), 전월비, 전년비

처리 경로 A — Qdrant 인덱싱 (의미 검색용):
  1. Table-aware chunking
     - header + 6행 단위로 묶어 하나의 chunk 생성
     - 각 chunk에 기간 메타데이터 포함
  2. 임베딩 생성
  3. Qdrant "coal_prices" upsert

처리 경로 B — PostgreSQL 저장 (집계 쿼리용):
  1. 행 단위 파싱
  2. PostgreSQL coal_prices upsert
  (집계, 증감률 계산은 SQL로 처리)

payload (Qdrant):
  {
    source: "유연탄_가격_통계.csv",
    year: int,
    month: int,
    price_usd: float,
    period_label: "2024-01 ~ 2024-06"
  }
```

### 4-3. 생산 매뉴얼 / 품질검사 기준서 PDF

```
[manual_indexer.py]

원본: 샘플 PDF (KS L 5201 등 공개 문서 활용)

처리:
  1. PyMuPDF로 텍스트 추출
  2. Semantic chunking (규제 문서와 동일 설정)
  3. 임베딩 생성
  4. Qdrant upsert
     - 매뉴얼 → "manuals" 컬렉션
     - 품질기준 → "quality_standards" 컬렉션

payload:
  {
    source: str,
    section: str,       # 챕터명 (e.g. "3장. 양생 기준")
    page: int,
    chunk_index: int,
    product_type: str   # 해당 시멘트 품종
  }
```

---

## 5. 배치 수집 흐름 (소스 7 — ERP 시뮬레이션)

```
[generate_erp.py] — 최초 1회 샘플 데이터 생성
  2년치 일별 생산·재고 데이터 생성
  제품 유형: 보통포틀랜드, 고로슬래그, 백색 시멘트
  공장 코드: PLANT_A, PLANT_B, PLANT_C
      │
      ▼
PostgreSQL production_logs insert

[erp_batch.py] — 일 1회 배치 (운영 시 사용)
  신규 CSV 파싱 → 검증 → upsert
```

> 포트폴리오 단계에서는 generate_erp.py로 2년치 데이터를 한번에 생성합니다.
> 실제 운영 환경에서는 erp_batch.py를 cron으로 매일 실행하는 구조입니다.

---

## 6. 청킹 전략 결정 기준

```
문서 유형 판별
      │
      ├─ PDF (법령/매뉴얼/기준서)
      │       → Semantic chunking
      │         이유: 문장 간 의미 연결이 중요
      │               단락 경계에서 자르면 맥락 보존
      │               chunk_size 512, overlap 64
      │
      ├─ CSV (시계열/가격 데이터)
      │       → Table-aware chunking
      │         이유: 행·열 관계 파괴 시 수치 의미 손실
      │               header + N행 묶음으로 하나의 chunk 생성
      │               Qdrant payload에 기간 메타데이터 포함
      │
      └─ 실시간 API JSON
              → Structured store (청킹 없음)
                이유: 집계·증감 연산은 SQL이 벡터보다 정확
                      TTL 캐시로 API 호출 최소화
```

---

## 7. 데이터 갱신 전략 요약

| 소스 | 갱신 방식 | 주기 | 비고 |
|------|-----------|------|------|
| 환율 | PostgreSQL TTL 캐시 | 1시간 | 만료 시 ECOS API 재호출 |
| 뉴스 | PostgreSQL TTL 캐시 | 30분 | 만료 시 네이버 API 재호출 |
| 날씨 | PostgreSQL TTL 캐시 | 1시간 | 만료 시 기상청 API 재호출 |
| 유연탄 가격 | 수동 트리거 | 월 1회 | `--source coal` 실행 |
| 환경부 규제 | 수동 트리거 | 법령 개정 시 | `--source regulation` 실행 |
| 생산 매뉴얼 | 수동 트리거 | 매뉴얼 개정 시 | `--source manual` 실행 |
| ERP | 자동 배치 | 일 1회 | 포트폴리오 단계에서는 샘플 데이터 사용 |
