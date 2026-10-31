# Spec: MVP 1순위, 도매 3거래일 후 end-to-end

Status: accepted · Date: 2026-11-01 · 근거: `intent/intent.md`(accepted v3.1), `docs/research/data-sources.md`, `docs/research/eda.md`

> 표기: 표시 없는 항목은 결정된 것. **[미정]**은 아직 정하지 않은 것.
> 범위: 수집 → 기준선 vs 후보 모델 → LLM 설명 → 대시보드 한 화면 + CLI → Docker. 소매·7일 후·RAG·현장 테스트·3자 비교는 범위 밖.

---

## 1. 예측 문제

| 항목 | 내용 |
|---|---|
| 대상 | KAMIS 공표 도매 평균가: 토마토(225/00), 상품(04), 5kg, `평균` 행. = 그날 가격이 있는 시장의 단순 평균 (eda.md §2) |
| 사용 기간 | 2002-11 이후. 그 이전은 3~10월만 있어 제외 |
| 기간 | 거래일 기준 **3거래일 후** (거래일 = `평균` 행이 있는 날) |
| 출력 | `ŷ(t+3)` 가격(원/5kg), 등락률 `(ŷ(t+3) − y(t)) / y(t)`, 방향(상승/보합/하락) |
| 예측 시점 | 거래일 t의 공표가를 받은 뒤 예측한다. t 이후의 정보는 사용하지 않는다 |
| 수집 시각 | 매일 20시. `collect daily`가 최근 7일을 다시 받으므로 공표가 늦어도 다음 수집에서 채워진다(공표 시각 때문에 막히지 않음). 실제 공표 시각은 운영하면서 관찰해 기록한다 |
| 대시보드 날짜 | "3거래일 후 (예상 날짜 YYYY-MM-DD)"로 실제 날짜를 함께 표시 |
| 예상 날짜 계산 | 평일 중 공휴일을 뺀 날을 거래일로 추정. 과거 데이터에 토요일 거래가 92일, 일요일 거래가 2일 있으므로 추정이 틀릴 수 있다는 점을 화면에 명시 |
| 공휴일 목록 | 공공데이터포털 특일 정보 API |

## 2. 평가 지표

모든 지표는 walk-forward 테스트 구간에서, 모든 모델에 대해 같은 예측 시점 집합으로 계산한다.

**가격 오차**
- **MAE (원/5kg)**: 주 지표.
- **MAPE (%)**: 보조. 가격 수준이 다른 시기끼리 비교할 때 쓴다.
- **상대 MAE** = MAE(모델) / MAE(B1 직전가). 1보다 작아야 기준선보다 낫다.
- RMSE: 참고용으로 보고만 한다.

**방향**
- 실제 등락률 `r = (y(t+3) − y(t)) / y(t)`, 보합 폭 **δ = 3%**.
  - 근거: 5kg 2만 원 기준 약 600원으로, 매입 판단에 의미 있는 차이다.
  - 2002-11 이후 |r| ≤ 3%인 날은 38.9%다.
- **상승/하락 적중률 (주 지표)**
  - 대상: 실제 |r| > δ인 날만.
  - 예측: 예측 등락률의 **부호만** 사용한다. 예측 등락률이 0이면 오답으로 센다. 따라서 B1은 0%다.
  - 정의: 예측 부호 = 실제 부호인 비율.
- **3분류 적중률 (보조 지표)**: 실제와 예측 모두 δ로 상승/보합/하락을 나눈 뒤, 예측 = 실제인 비율.

**구간별 보고**
- 전체 테스트 구간과 **급등 구간 2023-09 ~ 2024-12**를 따로 보고한다.
- 급등 구간은 EDA 가격 그래프로 정했고, 모델 결과를 보기 전에 고정했다.

**모델 선택 규칙** (결과를 보기 전에 고정)
1. 전체 테스트 구간에서 상대 MAE < 1인 모델만 남긴다.
2. 그중 MAE가 가장 낮은 모델을 고른다.
3. 단, 상승/하락 적중률이 B2보다 낮은 모델은 제외하고 2를 다시 적용한다.
4. 남는 모델이 없으면 B1을 채택하고, 그 사실을 그대로 보고한다.

## 3. 기준선

| ID | 정의 | 비고 |
|---|---|---|
| B1 직전가 | ŷ(t+3) = y(t) | 상대 MAE의 분모 |
| B2 최근 평균 | ŷ(t+3) = 최근 5거래일 평균 (k = 5) | 선택 규칙 3의 비교 대상 |

## 4. 후보 모델

| 모델 | 이유 | 실행 환경 |
|---|---|---|
| **LightGBM** | 6천 행 규모에서 CPU로 빠르게 학습되고, feature 중요도로 설명 근거를 만들 수 있다 | 로컬 CPU |
| **Chronos-2** (시계열 파운데이션 모델, zero-shot) | 학습 없이 예측하므로 트리 모델과 성격이 다르다. 참여 시장 수를 공변량으로 넣을 수 있는지는 구현 때 확인 | Colab A100. CPU에서도 돌아가는지 [미정] |

- **학습 목표**: 3거래일 로그수익률 `log(y(t+3)/y(t))`을 예측한 뒤 가격으로 되돌린다.
- **하이퍼파라미터**: 테스트 시작 전의 검증 구간(2020~2022)에서만 고르고, 테스트 동안에는 고정한다.
- **다음 실험 후보** (이번 범위 제외)
  - TabPFN (회귀, LightGBM과 같은 feature)
  - B3 계절 기준선: ŷ(t+3) = y(t) × 전년 같은 시기 3거래일 변화율

**Feature**: 모두 t 시점까지의 정보만 쓴다.

| 그룹 | feature |
|---|---|
| 가격 이력 | y(t−0…t−9) 지연값, 1·3·5·10거래일 수익률, 5·20거래일 이동평균과 표준편차 |
| 등급·시장 | 중품(05) 평균가와 상품/중품 비율, 시장별 가격의 최댓값−최솟값(spread) |
| 참여 시장 수 | t일 참여 시장 수, 직전 대비 변화 여부 |
| 달력 | 월, 연중 일자(sin/cos), 요일, t+3까지 남은 달력일 수(연휴 길이). **남은 달력일 수는 공휴일 달력으로만 계산하고, 실제 거래 데이터의 미래 날짜는 쓰지 않는다** |
| 계절 | 전년 같은 시기 가격, 같은 달 과거 중앙값 대비 현재가 비율 |
| 제외 | 기상·거래량·뉴스 (출처 미확보, MVP 이후) |

## 5. 검증: walk-forward

- **학습 구간**: 2002-11 ~ 2019-12. 검증(튜닝) 구간: 2020-01 ~ 2022-12.
- **테스트 구간**: 2023-01 ~ 마지막 데이터. 2023~2024 급등을 포함한다.
- **재학습 주기**: 월 1회. 매달 첫 거래일에 그 전날까지의 데이터로 다시 학습하고, 그달 예측에 쓴다.
- **실험: 학습 창 비교**
  - 전체(2002-11~) vs **최근 5년**
  - 같은 fold, 같은 지표로 비교한다.
- **누수 방지**
  - 이동평균 등 모든 feature는 t까지만 사용한다.
  - 테스트 구간 결과를 보고 feature나 지표를 바꾸지 않는다. 바꿔야 하면 사유를 기록하고 처음부터 다시 돌린다.
- **Chronos-2**: 학습이 없으므로 같은 예측 시점마다 그 시점까지의 이력만 넣어 예측한다.

## 6. LLM 설명

- **입력**(JSON)
  - 예측값, 현재가, 차이와 등락률, 방향
  - 3거래일 후 예상 날짜
  - 최근 20거래일 추이 요약, 계절 비교(같은 달 과거 중앙값)
  - 참여 시장 수 변화
  - 모델의 기준선 대비 성능(상대 MAE)
- **출력**: 예상가격, 현재가와 차이, 주요 변동 요인, 주의사항을 쉬운 문장 4~6개로. 예측이 틀릴 수 있다는 문구를 포함한다.
- **근거 검사**: 출력에 나온 숫자가 모두 입력에 있는지 코드로 검사한다. 실패하면 템플릿 문장으로 대체한다.
- **모델**: 소형 모델을 쓴다. 제공자를 바꿀 수 있도록 호출은 `explain/llm.py` 한 곳에만 둔다.
- **제공자·모델명**: [미정]
- **비용 상한**: 월 [미정: 사용자가 정할 값]
- **MVP 범위**: 뉴스는 넣지 않는다. 뉴스 출처는 [미정].

## 7. 데이터 스키마 (PostgreSQL, `src/tomato/db/schema.sql`로 관리)

```sql
CREATE TABLE ingest_run (
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
CREATE TABLE price_raw (
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
CREATE VIEW wholesale_daily AS
SELECT trade_date, rank_code,
       max(price) FILTER (WHERE county = '평균')                       AS avg_price,
       count(*)   FILTER (WHERE county <> '평균' AND price IS NOT NULL) AS n_markets
FROM price_raw
WHERE market_type = 'wholesale' AND item_code = '225' AND kind_code = '00'
GROUP BY trade_date, rank_code;

CREATE TABLE model_version (
  id          bigserial PRIMARY KEY,
  name        text NOT NULL,            -- 'B1' | 'B2' | 'lgbm' | 'chronos2'
  params      jsonb NOT NULL,
  train_start date, train_end date,
  artifact_path text,                   -- 모델 파일 경로 (Colab 결과 포함)
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE forecast (
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

CREATE TABLE backtest_metric (
  id          bigserial PRIMARY KEY,
  experiment  text NOT NULL,            -- 'window=full' | 'window=5y'
  model_name  text NOT NULL,
  segment     text NOT NULL,            -- 'test_all' | 'spike'
  metric      text NOT NULL,            -- 'mae' | 'mape' | 'rel_mae' | 'dir_acc_ud' | 'dir_acc3' | 'rmse'
  value       numeric NOT NULL,
  n           integer NOT NULL,
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE explanation (
  id          bigserial PRIMARY KEY,
  forecast_id bigint NOT NULL REFERENCES forecast(id),
  provider    text NOT NULL, model text NOT NULL,
  input       jsonb NOT NULL,
  output_text text NOT NULL,
  grounded    boolean NOT NULL,         -- 근거 검사 통과 여부
  created_at  timestamptz NOT NULL DEFAULT now()
);
```
- 마이그레이션 도구는 쓰지 않는다. 스키마는 `schema.sql` 한 파일로 관리한다.

## 8. 모듈 구조

```
src/tomato/
  config.py            # .env 로드 (키 출력 금지)
  collectors/kamis.py  # scripts/fetch_kamis.py를 옮긴 것. 재시도·ingest_run 기록
  db/schema.sql, db/repo.py
  calendar.py          # 공휴일 달력(특일 API), 거래일 계산, t+3 예상 날짜
  features.py          # §4 feature (t 시점까지만)
  models/baselines.py, models/lgbm.py, models/chronos.py
  evaluation/walkforward.py, evaluation/metrics.py
  explain/llm.py, explain/grounding.py, explain/template.py
  api/main.py          # FastAPI: /forecast/latest, /prices, /health
  web/                 # 대시보드 한 화면: FastAPI 템플릿 + JS 차트
  cli.py
tests/                 # metrics, calendar, feature 누수 검사부터
docker-compose.yml, Dockerfile
```
- 의존성 관리 도구(pip+requirements, uv 등): [미정]
- Chronos-2는 Colab에서 돌리고, 결과 파일(예측 CSV)을 `backtest import`로 DB에 넣는다 (intent Constraints).

## 9. CLI 명령

컨테이너 안에서 `docker compose run --rm app tomato <명령>` 형태로 실행한다.

| 명령 | 역할 |
|---|---|
| `tomato db init` | `schema.sql` 적용 |
| `tomato collect backfill --market wholesale --from 2002-11-01 [--to …]` | 1년 단위로 나눠 받아 upsert |
| `tomato collect daily [--days 7]` | 최근 7일을 다시 받아 upsert. 실패 시 재시도(3회, 간격 증가), `ingest_run`에 기록 |
| `tomato backtest --models B1,B2,lgbm [--window full\|5y]` | walk-forward 실행, `backtest_metric` 저장, 표 출력 |
| `tomato backtest import --model chronos2 --file …` | Colab 결과 가져오기 |
| `tomato train --model lgbm` | 최신 데이터로 학습해 `model_version` 등록 |
| `tomato predict [--origin YYYY-MM-DD]` | 3거래일 후 예측을 `forecast`에 저장 |
| `tomato explain [--forecast-id N]` | LLM 설명 생성과 근거 검사. 실패하면 템플릿 문장 |
| `tomato show latest` | 현재가, 예측, 설명 조회 |

- **스케줄**: 호스트 cron이 매일 20시에 `collect daily` → `predict` → `explain`을 컨테이너 안에서 실행한다.

## 10. 구현 순서

1. **B1으로 end-to-end**: 수집 → DB → B1 예측 → 템플릿 설명 → 대시보드 → Docker
2. **LightGBM + backtest**: B1·B2·LightGBM, 학습 창 2종, 선택 규칙 적용
3. **LLM 설명**: `llm.py`, 근거 검사, 템플릿 대체
4. **Chronos-2** (Colab): 같은 예측 시점으로 예측 → `backtest import` → 선택 규칙 다시 적용

## 11. 완료 기준 (MVP 1순위)

1. `docker compose up`으로 DB·API·대시보드가 뜬다.
2. `collect backfill` 결과 DB 행 수가 `data-manifest.md`의 2002-11 이후 도매 행 수와 일치한다. `-` 가격은 NULL로 들어간다.
3. `collect daily`가 실패하면 재시도하고, 실패 사유를 `ingest_run`에 남긴다. 실패 상황은 네트워크 차단으로 재현해 확인한다.
4. `backtest`가 B1·B2와 후보 모델을 **같은 fold, 같은 지표**로 비교한 표를 낸다.
   - 전체 테스트와 급등 구간을 따로 낸다.
   - 학습 창 비교(전체 vs 최근 5년)를 포함한다.
   - 기준선을 못 이기면 그대로 보고한다.
5. §2 선택 규칙으로 모델 1개를 고르고(B1일 수도 있음), 근거를 `docs/decisions.md`에 기록한다.
6. `predict`와 `explain`이 최신 거래일 기준 예측과 설명을 만든다. 설명은 근거 검사를 통과하거나, 실패하면 템플릿 문장으로 대체된다.
7. 대시보드 한 화면에 다음이 표시된다.
   - 현재 공표가
   - 3거래일 후 예상가와 예상 날짜
   - 최근 가격 그래프와 예측점
   - 자연어 설명
   - 모델 성능 한 줄 (예: "직전가 대비 오차 x% 감소")
8. 테스트가 통과한다.
   - metrics 계산
   - 거래일 계산
   - feature 누수 검사: t 이후 값을 쓰면 실패하고, **남은 달력일 수가 공휴일 달력이 아닌 실제 거래 데이터로 계산되면 실패**한다.

---

## 남은 [미정]

| 항목 | 비고 |
|---|---|
| LLM 제공자·모델명 | 소형 모델, `llm.py`에 격리 |
| LLM 월 비용 상한 | 사용자가 정할 값 |
| 뉴스 출처 | MVP 이후 |
| 의존성 관리 도구 | 구현 1단계 시작 전 |
| Chronos-2 CPU 실행 가능 여부 | 구현 4단계에서 확인 |
| KAMIS 실제 공표 시각 | 운영하면서 관찰해 기록 (비차단) |
