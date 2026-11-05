-- docs/spec.md §7 스키마. `tomato db init`으로 적용한다(여러 번 실행해도 안전).

CREATE TABLE IF NOT EXISTS ingest_run (
  id          bigserial PRIMARY KEY,
  job         text NOT NULL,            -- 'backfill' | 'daily'
  started_at  timestamptz NOT NULL DEFAULT now(),
  finished_at timestamptz,
  status      text NOT NULL,            -- 'running' | 'ok' | 'failed'
  attempts    integer NOT NULL DEFAULT 1,
  rows_upserted integer,
  error       text
);

-- 원본: API 응답을 행 단위로 그대로 보관한다. 평년 행은 저장하지 않는다.
CREATE TABLE IF NOT EXISTS price_raw (
  market_type   text NOT NULL,          -- 'wholesale' | 'retail'
  item_code     text NOT NULL,          -- '225'
  kind_code     text NOT NULL,          -- '00'
  rank_code     text NOT NULL,          -- '04' 상품, '05' 중품
  county        text NOT NULL,          -- '서울'… 또는 '평균'
  market        text NOT NULL DEFAULT '',
  trade_date    date NOT NULL,
  price         integer,                -- 원/조사단위. '-'는 NULL
  unit          text NOT NULL,          -- '5kg'
  fetched_at    timestamptz NOT NULL DEFAULT now(),
  ingest_run_id bigint REFERENCES ingest_run(id),
  PRIMARY KEY (market_type, item_code, kind_code, rank_code, county, market, trade_date)
);

-- 모델 입력의 기준 시계열 (평균 행 + 참여 시장 수)
CREATE OR REPLACE VIEW wholesale_daily AS
SELECT trade_date, rank_code,
       max(price) FILTER (WHERE county = '평균')                       AS avg_price,
       count(*)   FILTER (WHERE county <> '평균' AND price IS NOT NULL) AS n_markets
FROM price_raw
WHERE market_type = 'wholesale' AND item_code = '225' AND kind_code = '00'
GROUP BY trade_date, rank_code;

CREATE TABLE IF NOT EXISTS model_version (
  id          bigserial PRIMARY KEY,
  name        text NOT NULL,            -- 'B1' | 'B2' | 'lgbm' | 'chronos2'
  params      jsonb NOT NULL,
  train_start date, train_end date,
  artifact_path text,                   -- 모델 파일 경로 (Colab 결과 포함)
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS forecast (
  id             bigserial PRIMARY KEY,
  model_version_id bigint NOT NULL REFERENCES model_version(id),
  experiment     text NOT NULL DEFAULT 'live',  -- 'live' | 'window=full' | 'window=5y'
  origin_date    date NOT NULL,         -- t
  horizon_tdays  integer NOT NULL DEFAULT 3,
  target_date_est date NOT NULL,        -- 추정 실제 날짜
  y_origin       integer NOT NULL,
  y_hat          integer NOT NULL,
  change_pct     numeric(6,3) NOT NULL,
  direction      text NOT NULL,         -- 'up' | 'flat' | 'down'
  is_backtest    boolean NOT NULL,
  created_at     timestamptz NOT NULL DEFAULT now(),
  UNIQUE (model_version_id, experiment, origin_date, horizon_tdays, is_backtest)
);

CREATE TABLE IF NOT EXISTS backtest_metric (
  id          bigserial PRIMARY KEY,
  experiment  text NOT NULL,            -- 'window=full' | 'window=5y'
  horizon_tdays integer NOT NULL DEFAULT 3,
  model_name  text NOT NULL,
  segment     text NOT NULL,            -- 'test_all' | 'spike'
  metric      text NOT NULL,            -- 'mae' | 'mape' | 'rel_mae' | 'dir_acc_ud' | 'dir_acc3' | 'rmse' | 'sim_cost_a' | 'sim_cost_b' | 'sim_diff_won' | 'sim_diff_pct'
  value       numeric NOT NULL,
  n           integer NOT NULL,
  created_at  timestamptz NOT NULL DEFAULT now()
);
-- 2단계 전에 만든 DB에도 컬럼을 넣는다. 기존 행은 3거래일 지표이므로 기본값 3이 맞다.
ALTER TABLE backtest_metric ADD COLUMN IF NOT EXISTS horizon_tdays integer NOT NULL DEFAULT 3;

CREATE TABLE IF NOT EXISTS explanation (
  id          bigserial PRIMARY KEY,
  forecast_id bigint NOT NULL REFERENCES forecast(id),
  provider    text NOT NULL, model text NOT NULL,
  input       jsonb NOT NULL,
  output_text text NOT NULL,
  grounded    boolean NOT NULL,         -- 근거 검사 통과 여부
  created_at  timestamptz NOT NULL DEFAULT now()
);
