# 01. 데이터 흐름 설계

## 1. 데이터 소스 전체 목록

| # | 소스 | 형태 | 수집 방식 | 수집 주기 | 최종 저장 | 에어갭 대체 |
|---|------|------|-----------|-----------|-----------|-------------|
| 1 | 한국은행 ECOS (환율) | REST JSON | API 호출 | 실시간 (캐시 1h) | Redis → PostgreSQL | 사전 수집 CSV |
| 2 | 네이버 뉴스 검색 | REST JSON | API 호출 | 실시간 (캐시 30m) | Redis → PostgreSQL | 내부 RSS or 샘플 |
| 3 | 기상청 단기예보 | REST JSON | API 호출 | 실시간 (캐시 1h) | Redis | 기상청 FTP or 샘플 |
| 4 | 환경부 대기오염 배출 기준 | PDF | 파일 다운로드 | 최초 1회 + 개정 시 | Qdrant | 사전 반입 파일 |
| 5 | 유연탄 가격 통계 | CSV | 파일 다운로드 | 월 1회 | Qdrant + PostgreSQL | 사전 반입 파일 |
| 6 | 생산 매뉴얼 (시뮬레이션) | PDF | 로컬 파일 | 최초 1회 | Qdrant | 동일 |
| 7 | ERP 생산·재고 리포트 (시뮬레이션) | CSV | 로컬 파일 | 일 1회 배치 | PostgreSQL | 동일 |
| 8 | 품질검사 기준서 (시뮬레이션) | PDF | 로컬 파일 | 최초 1회 | Qdrant | 동일 |

---

## 2. 전체 데이터 흐름 개요

```
외부 데이터 소스 (인터넷)
      │
      ├─ 실시간 API (1, 2, 3)
      │       │
      │       ▼
      │  [수집기: async httpx]
      │  Redis 캐시 확인 → HIT: 반환
      │                 → MISS: API 호출 → Redis upsert → PostgreSQL upsert
      │       │
      │       ▼ Kafka Producer
      │  [market.raw / news.raw / weather.raw Topics]
      │
      └─ 정적 문서 (4, 5, 6, 8) + 배치 데이터 (7)
              │
              ▼ Kafka Producer
         [indexing.requests / erp.updated Topics]
              │
              ▼
    ┌─────────────────────────────┐
    │     Kafka Consumer 레이어   │
    │  인덱싱 Consumer            │
    │  LLM Consumer (뉴스 요약)   │
    │  ERP Consumer               │
    │  DLQ Consumer (실패 재처리) │
    └──────────────┬──────────────┘
                   │
                   ▼
    ┌─────────────────────────────┐
    │        저장 레이어           │
    │  Redis       캐시           │
    │  PostgreSQL  수치·ERP       │
    │  Qdrant      벡터 인덱스    │
    │  Neo4j       규제 그래프    │
    └──────────────┬──────────────┘
                   │
                   ▼
    ┌─────────────────────────────┐
    │     LangGraph Agent         │
    │  질의 → Adaptive RAG        │
    │       → Multi-Agent         │
    │       → 응답 생성           │
    └─────────────────────────────┘
```

---

## 3. 실시간 API 수집 흐름 (소스 1, 2, 3)

### 공통 패턴 — Redis 캐시 레이어

```
Agent Tool 호출
      │
      ▼
Redis 캐시 조회 (key: {source}:{date} 형태)
      │
      ├─ HIT (TTL 유효) ──────────────→ 데이터 반환
      │
      └─ MISS (TTL 만료 or 없음)
               │
               ├─ AIRGAP_MODE=true → 내부 DB 조회 후 반환
               │
               └─ AIRGAP_MODE=false
                        │
                        ▼
                  외부 API 호출 (async httpx)
                        │
                        ├─ 성공 → Redis SET (TTL 적용)
                        │         PostgreSQL upsert (영구 저장)
                        │         Kafka 이벤트 발행
                        │         데이터 반환
                        │
                        └─ 실패 → PostgreSQL 마지막 데이터 fallback
                                  없으면 에러 반환
```

### 3-1. 한국은행 ECOS — 환율

```
파일: app/data/collectors/exchange_api.py

호출 URL:
  GET https://ecos.bok.or.kr/api/StatisticSearch
      /{API_KEY}/json/kr/1/1/731Y001/DD/{YYYYMMDD}/{YYYYMMDD}/0000001

응답 파싱:
  StatisticSearch.row[0].DATA_VALUE → 원/달러 환율

Redis 키: exchange:usd_krw:{YYYYMMDD}
TTL: 3600초 (1시간)
  - 한국은행 ECOS는 영업일 오전 11시 고시
  - 장중 변동 없으므로 1시간 TTL 충분

Kafka 발행 토픽: market.raw
발행 메시지:
  {
    "type": "exchange",
    "currency": "USD/KRW",
    "rate": 1380.0,
    "base_date": "2025-05-06",
    "collected_at": "2025-05-06T11:00:00"
  }

에어갭 대체:
  AIRGAP_MODE=true → PostgreSQL market_rates 테이블 조회
```

### 3-2. 네이버 뉴스 검색

```
파일: app/data/collectors/news_api.py

호출 URL:
  GET https://openapi.naver.com/v1/search/news.json
      ?query={keyword}&display=10&sort=date
Headers:
  X-Naver-Client-Id / X-Naver-Client-Secret

검색 키워드 (asyncio.gather로 3개 병렬 호출):
  1. "시멘트 수요"
  2. "건설 경기"
  3. "유연탄 가격"

응답 파싱:
  items[].{title, link, description, pubDate}
  HTML 태그 제거 (bleach 라이브러리)

Redis 키: news:{keyword}:{YYYYMMDD_HH}
TTL: 1800초 (30분)

Kafka 발행 토픽: news.raw
  → LLM Consumer가 구독하여 비동기 요약 처리

에어갭 대체:
  AIRGAP_MODE=true → PostgreSQL news_cache 최근 데이터 조회
```

### 3-3. 기상청 단기예보

```
파일: app/data/collectors/weather_api.py

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

Redis 키: weather:{nx}_{ny}:{YYYYMMDD}_{base_time}
TTL: 3600초 (1시간)
  - 기상청 단기예보는 3시간 단위 발표

에어갭 대체:
  AIRGAP_MODE=true → 최근 PostgreSQL weather_cache 조회
```

---

## 4. 문서 인덱싱 흐름 (소스 4, 5, 6, 8)

### 트리거 방식

```bash
# 수동 트리거 (최초 1회 or 갱신 시)
python -m app.indexing.pipeline --source {target}
  target: all | regulation | coal | manual | quality

# 실행 시 Kafka indexing.requests 토픽에 메시지 발행
# → 인덱싱 Consumer가 비동기로 처리
```

### 공통 인덱싱 흐름

```
문서 로드 (PDF or CSV)
      │
      ▼
문서 유형 판별 → 청킹 전략 선택
      │
      ├─ PDF → Semantic chunking
      ├─ CSV (가격/시계열) → Table-aware chunking
      └─ CSV (ERP 수치) → 청킹 없이 PostgreSQL 직접 저장
      │
      ▼
임베딩 생성 (ko-sroberta-multitask, 768 dim)
  - 에어갭: 로컬 모델 파일 로드 (./models/ko-sroberta/)
      │
      ▼
Qdrant upsert (컬렉션별 분리)
      │
      ▼
Kafka indexing.results 발행 (완료 이벤트)
실패 시 → Kafka dlq.errors 발행
```

### 4-1. 환경부 대기오염 배출 기준 PDF

```
파일: app/data/collectors/regulation_pdf.py

원본: 국가법령정보센터 PDF (대기환경보전법 시행규칙 별표)

처리:
  1. PyMuPDF(fitz)로 텍스트 추출
  2. Semantic chunking
     - chunk_size: 512 tokens
     - chunk_overlap: 64 tokens
     - splitter: RecursiveCharacterTextSplitter
  3. 임베딩 생성
  4. Qdrant "regulations" upsert
  5. Neo4j 그래프 변환 (graph_indexer.py 별도 실행)
     - 노드: 법령, 조항, 수치기준, 오염물질
     - 엣지: CONTAINS / REGULATES / APPLIES_TO

Qdrant payload:
  {
    "source": "대기환경보전법_시행규칙_별표.pdf",
    "law_name": "대기환경보전법",
    "page": int,
    "chunk_index": int,
    "updated_at": "YYYY-MM-DD"
  }
```

### 4-2. 유연탄 가격 CSV

```
파일: app/data/collectors/coal_price.py

원본: 한국자원정보서비스 (kores.net) 월별 가격 CSV
컬럼: 연도, 월, 가격($/톤), 전월비, 전년비

처리 경로 A — Qdrant (의미 검색용):
  1. Table-aware chunking
     - header + 6행 단위 chunk
     - 기간 메타데이터 payload 포함
  2. 임베딩 → Qdrant "coal_prices" upsert

처리 경로 B — PostgreSQL (집계 쿼리용):
  1. 행 단위 파싱
  2. PostgreSQL coal_prices upsert
  (증감률 계산, 집계는 SQL로 처리)

Qdrant payload:
  {
    "source": "유연탄_가격_통계.csv",
    "year": int,
    "month": int,
    "price_usd": float,
    "period_label": "2024-01 ~ 2024-06"
  }
```

### 4-3. 생산 매뉴얼 / 품질검사 기준서

```
파일: app/indexing/pipeline.py (manual / quality 옵션)

원본: KS L 5201 등 공개 문서 활용 (시뮬레이션)

처리:
  1. PyMuPDF 텍스트 추출
  2. Semantic chunking (규제 문서와 동일 설정)
  3. 임베딩 생성
  4. Qdrant upsert
     - 매뉴얼 → "manuals" 컬렉션
     - 품질기준 → "quality_standards" 컬렉션

Qdrant payload (manuals):
  {
    "source": str,
    "section": str,        # 챕터명 (e.g. "3장. 양생 기준")
    "page": int,
    "chunk_index": int,
    "product_type": str    # 시멘트 품종
  }
```

---

## 5. Kafka 이벤트 파이프라인 흐름

```
Topic 목록:
  market.raw          환율 수집 완료 이벤트
  news.raw            뉴스 수집 완료 이벤트
  weather.raw         날씨 수집 완료 이벤트
  erp.updated         ERP 배치 완료 이벤트
  indexing.requests   인덱싱 요청 (문서 처리)
  indexing.results    인덱싱 완료 이벤트
  llm.requests        LLM 비동기 처리 요청 (뉴스 요약 등)
  llm.results         LLM 처리 완료 이벤트
  dlq.errors          Dead Letter Queue (실패 메시지)

Consumer 구성:
  indexing_consumer  indexing.requests 구독
                     → 청킹 → 임베딩 → Qdrant 적재
                     → 완료: indexing.results 발행
                     → 실패: dlq.errors 발행

  llm_consumer       llm.requests 구독
                     → 뉴스 요약 / Self-RAG 재검색 처리
                     → 완료: llm.results 발행

  erp_consumer       erp.updated 구독
                     → PostgreSQL production_logs upsert

  dlq_consumer       dlq.errors 구독
                     → 실패 메시지 로깅 및 재시도 (최대 3회)
```

---

## 6. ERP 배치 수집 흐름 (소스 7 — 시뮬레이션)

```
초기 단계 (샘플 데이터):
  python app/data/samples/generate_erp.py
  → 2년치 일별 생산·재고 샘플 데이터 생성
  → 제품 유형: 보통포틀랜드, 고로슬래그, 백색시멘트
  → 공장 코드: PLANT_A, PLANT_B, PLANT_C
  → PostgreSQL production_logs insert
  → Kafka erp.updated 발행

실운영 시:
  일 1회 cron → erp_batch.py 실행
  → 신규 CSV 파싱 → 검증 → PostgreSQL upsert
  → Kafka erp.updated 발행 → erp_consumer 처리
```

---

## 7. 청킹 전략 결정 기준

```
문서 유형 판별
      │
      ├─ PDF (법령 / 매뉴얼 / 기준서)
      │       → Semantic chunking
      │         chunk_size: 512 tokens
      │         chunk_overlap: 64 tokens
      │         이유: 문장 간 의미 연결 중요, 단락 경계에서 분할
      │
      ├─ CSV (시계열 / 가격 데이터)
      │       → Table-aware chunking
      │         header + 6행 단위 chunk
      │         이유: 행·열 관계 파괴 시 수치 의미 손실
      │
      └─ CSV (ERP 수치 / 실시간 API)
              → Structured store (청킹 없음)
                이유: 집계·증감 연산은 SQL이 벡터보다 정확
```

---

## 8. LLM 백엔드별 데이터 흐름 차이

```
LLM_BACKEND=local (Ollama/vLLM)
  고객 질의 → 내부 LLM 서버 → 응답
  데이터 외부 전송: 없음 ✅

LLM_BACKEND=bedrock (AWS Bedrock)
  고객 질의 → 고객 AWS VPC 내 Bedrock 엔드포인트 → 응답
  데이터 외부 전송: VPC 내 격리 △

LLM_BACKEND=anthropic (Anthropic API)
  고객 질의 → Anthropic API 서버 → 응답
  데이터 외부 전송: 있음 (엔터프라이즈 계약 필요) ○

→ app/core/llm_backend.py 에서 동일 인터페이스로 추상화
→ 환경변수 변경만으로 백엔드 전환 가능
```

---

## 9. 데이터 갱신 전략 요약

| 소스 | 갱신 방식 | 주기 | 비고 |
|------|-----------|------|------|
| 환율 | Redis TTL → API 재호출 | 1시간 | 에어갭: PostgreSQL fallback |
| 뉴스 | Redis TTL → API 재호출 | 30분 | 에어갭: 내부 DB fallback |
| 날씨 | Redis TTL → API 재호출 | 1시간 | 에어갭: 최근 캐시 fallback |
| 유연탄 가격 | 수동 트리거 | 월 1회 | `--source coal` |
| 환경부 규제 | 수동 트리거 | 법령 개정 시 | `--source regulation` |
| 생산 매뉴얼 | 수동 트리거 | 매뉴얼 개정 시 | `--source manual` |
| ERP | Kafka 배치 | 일 1회 | 초기에는 샘플 데이터로 시작 |
