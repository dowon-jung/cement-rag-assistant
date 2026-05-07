-- ============================================
-- cement-rag-assistant PostgreSQL 초기화 스크립트
-- ============================================

-- 환율 영구 저장
CREATE TABLE IF NOT EXISTS market_rates (
    id          SERIAL PRIMARY KEY,
    currency    VARCHAR(10)    NOT NULL,
    rate        NUMERIC(10, 2) NOT NULL,
    base_date   DATE           NOT NULL,
    fetched_at  TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    UNIQUE (currency, base_date)
);
CREATE INDEX IF NOT EXISTS idx_market_rates_date ON market_rates (base_date DESC);

-- 뉴스 영구 저장
CREATE TABLE IF NOT EXISTS news_cache (
    id           SERIAL PRIMARY KEY,
    keyword      VARCHAR(100) NOT NULL,
    title        TEXT         NOT NULL,
    link         TEXT         NOT NULL UNIQUE,
    description  TEXT,
    pub_date     TIMESTAMPTZ,
    fetched_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_news_keyword  ON news_cache (keyword);
CREATE INDEX IF NOT EXISTS idx_news_pub_date ON news_cache (pub_date DESC);

-- 날씨 캐시
CREATE TABLE IF NOT EXISTS weather_cache (
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

-- 유연탄 가격
CREATE TABLE IF NOT EXISTS coal_prices (
    id          SERIAL PRIMARY KEY,
    price_date  DATE           NOT NULL UNIQUE,
    price_usd   NUMERIC(10, 2) NOT NULL,
    price_krw   NUMERIC(12, 2),
    source      VARCHAR(100),
    created_at  TIMESTAMPTZ    NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_coal_prices_date ON coal_prices (price_date DESC);

-- ERP 생산 로그 (시뮬레이션)
CREATE TABLE IF NOT EXISTS production_logs (
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
CREATE INDEX IF NOT EXISTS idx_production_logs_date  ON production_logs (log_date DESC);
CREATE INDEX IF NOT EXISTS idx_production_logs_plant ON production_logs (plant_code);

-- Materialized View: 월별 생산량 집계 (성능 최적화)
CREATE MATERIALIZED VIEW IF NOT EXISTS monthly_production AS
SELECT
    DATE_TRUNC('month', log_date) AS month,
    product_type,
    plant_code,
    SUM(production_qty)  AS total_qty,
    AVG(production_qty)  AS avg_daily_qty,
    COUNT(*)             AS working_days
FROM production_logs
GROUP BY 1, 2, 3;

CREATE UNIQUE INDEX IF NOT EXISTS idx_monthly_production
    ON monthly_production (month, product_type, plant_code);

SELECT 'DB 초기화 완료' AS status;
