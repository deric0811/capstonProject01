# Spec: MVP 1순위, 도매 3·7거래일 후 end-to-end

Status: accepted · Date: 2026-11-01 · 개정: 2026-11-05 (7거래일 평가, 매입 시뮬레이션, 범위 축소. 2단계 결과를 보기 전에 고정), 2026-11-09 (B3, 오라클 시뮬레이션, h = 21 사전 등록), 2026-11-10 (시뮬레이션 표기 통일, LLM 증류 범위 복귀, Chronos-2 사전 등록, LLM 해설 증류 사전 등록) · 근거: `intent/intent.md`(accepted v3.1), `docs/research/data-sources.md`, `docs/research/eda.md`

> 표기: 표시 없는 항목은 결정된 것. **[미정]**은 아직 정하지 않은 것.
> 범위: 수집 → 기준선 vs 후보 모델 → LLM 설명 → 대시보드 한 화면 + CLI → Docker. 소매·RAG·현장 테스트·3자 비교는 범위 밖. 7거래일은 평가와 `predict` 저장까지만 하고, 대시보드와 설명은 3거래일을 유지한다.

---

## 1. 예측 문제

| 항목 | 내용 |
|---|---|
| 대상 | KAMIS 공표 도매 평균가: 토마토(225/00), 상품(04), 5kg, `평균` 행. = 그날 가격이 있는 시장의 단순 평균 (eda.md §2) |
| 사용 기간 | 2002-11 이후. 그 이전은 3~10월만 있어 제외 |
| 기간 | 거래일 기준 **h = 3, 7거래일 후** (`forecast.horizon_tdays`). 거래일 = `평균` 행이 있는 날. h = 21(약 30일)은 평가만 한다(§2, predict 저장 없음) |
| 출력 | 기간별 `ŷ(t+h)` 가격(원/5kg), 등락률 `(ŷ(t+h) − y(t)) / y(t)`, 방향(상승/보합/하락) |
| 예측 시점 | 거래일 t의 공표가를 받은 뒤 예측한다. t 이후의 정보는 사용하지 않는다 |
| 수집 시각 | 매일 20시. `collect daily`가 최근 7일을 다시 받으므로 공표가 늦어도 다음 수집에서 채워진다(공표 시각 때문에 막히지 않음). 실제 공표 시각은 운영하면서 관찰해 기록한다 |
| 대시보드 날짜 | "3거래일 후 (예상 날짜 YYYY-MM-DD)"로 실제 날짜를 함께 표시. 대시보드는 h = 3만 표시한다 |
| 예상 날짜 계산 | 평일 중 공휴일을 뺀 날을 거래일로 추정. 과거 데이터에 토요일 거래가 92일, 일요일 거래가 2일 있으므로 추정이 틀릴 수 있다는 점을 화면에 명시 |
| 공휴일 목록 | Python `holidays` 라이브러리(KR). 대체·임시공휴일이 빠질 수 있다 (docs/decisions.md 2026-11-01) |

## 2. 평가 지표

모든 지표는 walk-forward 테스트 구간에서, 모든 모델에 대해 같은 예측 시점 집합으로 계산한다.
- h = 21: MAE, MAPE, 상대 MAE, 상승/하락 적중률, 3분류 적중률, 모델 선택 규칙을 같은 방식으로 적용한다. 매입 시뮬레이션은 적용하지 않는다.
- 결과표에는 항상 B1·B2·B3를 함께 싣는다. B3는 가격을 내지 않으므로 MAE 계열과 3분류 칸은 "—"로 둔다.

지표와 표는 h별로 따로 낸다. 예측 시점 집합은 h 안에서 모델 간에 같다. h = 7은 끝부분 예측 시점이 더 적으므로 h끼리 총액을 직접 비교하지 않는다.

**가격 오차**
- **MAE (원/5kg)**: 주 지표.
- **MAPE (%)**: 보조. 가격 수준이 다른 시기끼리 비교할 때 쓴다.
- **상대 MAE** = MAE(모델) / MAE(B1 직전가). 1보다 작아야 기준선보다 낫다.
- RMSE: 참고용으로 보고만 한다.

**방향**
- 실제 등락률 `r = (y(t+h) − y(t)) / y(t)`, 보합 폭 **δ = 3%** (두 기간 모두).
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
h별로 따로 적용한다. 기간마다 다른 모델이 뽑힐 수 있다.
2단계 후보는 h별로 B2와 LightGBM(검증 구간에서 고른 학습 창) 하나다. 다른 창은 §5 비교 실험으로 보고만 한다 (docs/decisions.md 2026-11-05).
4단계 후보는 h별로 B2, LightGBM full, Chronos-2(검증에서 고른 입력)이다. 규칙 1~4는 그대로다. Chronos-2가 선택되면 그 h의 운영 모델을 Chronos-2로 바꾼다 (docs/decisions.md 2026-11-10).
1. 전체 테스트 구간에서 상대 MAE < 1인 모델만 남긴다.
2. 그중 MAE가 가장 낮은 모델을 고른다.
3. 단, 상승/하락 적중률이 B2보다 낮은 모델은 제외하고 2를 다시 적용한다.
4. 남는 모델이 없으면 B1을 채택하고, 그 사실을 그대로 보고한다.

**매입 시뮬레이션** (결과를 보기 전에 고정. 보고만 하고 모델 선택 규칙에는 쓰지 않는다)
- 가정: 테스트 구간의 예측 시점 t마다 h거래일 안에 반드시 상품 5kg 1단위를 산다.
- 매입 가격은 **t+1 이후의 공표가만** 쓴다. y(t)는 예측 시점에 이미 경매가 끝난 가격이라 실제로 살 수 없고, 전략 B에 유리한 편향이 생기므로 넣지 않는다.
- 전략 A: 항상 t+1에 산다. 비용 y(t+1)
- 전략 B: 모델의 방향이 상승(예측 등락률 > +δ, δ = 3%)이면 t+1에 산다. 비용 y(t+1). 보합·하락이면 기간 마지막 날에 산다. 비용 y(t+h)
- 지표 (h별, 모델별, 전체·급등 구간별. 구간은 예측 시점 t로 나눈다. 모든 모델에 같은 규칙)
  - 총 매입비 A, B (원)
  - 절감액(원) = A − B, 절감(%) = (A − B) / A × 100. 양수면 B가 싸다
  - 2026-11-10 개정: 보고 기준(A − B)으로 표기를 통일했다. 수치는 바뀌지 않는다. DB 저장값 `sim_diff_won`, `sim_diff_pct`는 B − A 그대로다(부호만 반대)
- 한계
  - 기간이 겹치는 매입이라 관측이 독립이 아니다
  - 수수료·보관비·품질 변화는 넣지 않았다
  - B1은 예측 등락률이 항상 0이므로 B1의 전략 B는 "항상 마지막 날 매입"이다
  - 현장 검증을 하지 않으므로 효용은 이 시뮬레이션으로만 간접 확인한다. 보고서에 이 한계를 명시한다 (docs/decisions.md 2026-11-05)
- B3의 전략 B: 상승 = y(t) > 최근 5거래일 평균(t 포함). B3는 등락 폭이 없으므로 δ를 쓰지 않는다. 같은 값이면 상승이 아니다(t+h에 산다).
- 오라클 (h = 3, 7. 절감액의 상한으로 보고하고 선택에는 쓰지 않는다)
  - 오라클-최적: 비용 min(y(t+1), y(t+h)). t+1과 t+h 중 하나를 고르는 어떤 전략도 이보다 싸게 살 수 없다.
  - 오라클-규칙: 같은 규칙의 예측 등락률 자리에 실제 등락률 (y(t+h) − y(t)) / y(t)를 넣는다. 엄밀한 상한은 아니다. 실제 r ≤ 3%인데 y(t+1) < y(t+h)인 날에는 모델이 더 싸게 살 수 있다.

**h = 21 Diebold-Mariano 검정** (사전 등록. 보고만 하고 모델 선택 규칙에는 쓰지 않는다)
- 비교: LightGBM(검증에서 고른 창) vs B1. 손실 = 절대오차, d = |e_LightGBM| − |e_B1|.
- 분산: lag h−1 = 20까지의 자기공분산 합(직사각형 커널). 0 이하면 같은 lag의 Bartlett(Newey-West) 가중으로 바꾸고 그 사실을 보고한다.
- 판정: 양측 정규근사 p값. 검정 2개(전체, 급등)에 본페로니 보정을 적용해 각각 α = 0.05 / 2 = **0.025** 미만이면 유의로 본다.
- 한계: 21거래일 예측은 서로 많이 겹쳐 유효 표본이 작고(약 n/21), 검정력이 낮다.

**Chronos-2 Diebold-Mariano 검정** (사전 등록 2026-11-10. 보고만 하고 모델 선택 규칙에는 쓰지 않는다)
- 판정 대상: Chronos-2 vs LightGBM full, 전체 구간, h = 3·7·21 (3개). 손실 = 절대오차, lag h−1, 직사각형 커널(0 이하면 Bartlett로 바꾸고 보고).
- 판정: 양측 정규근사 p값이 본페로니 α = 0.05 / 3 ≈ 0.0167 미만이면 유의.
- 참고(판정 대상 아님): Chronos-2 vs B1, 그리고 급등 구간.
- 해석: 선택은 규칙(MAE)대로 한다. 선택된 모델과 LightGBM의 DM이 유의하지 않으면 "선택됐지만 차이는 유의하지 않음"으로 함께 보고한다.

## 3. 기준선

| ID | 정의 | 비고 |
|---|---|---|
| B1 직전가 | ŷ(t+h) = y(t) | 상대 MAE의 분모 |
| B2 최근 평균 | ŷ(t+h) = 최근 5거래일 평균 (k = 5, 두 기간 모두) | 선택 규칙 3의 비교 대상 |
| B3 추세 규칙 | 방향만: y(t) > 최근 5거래일 평균이면 상승, < 이면 하락, 같으면 예측 없음(오답) | 방향 지표·매입 시뮬레이션에만 쓴다. 선택 후보 아님 |

## 4. 후보 모델

| 모델 | 이유 | 실행 환경 |
|---|---|---|
| **LightGBM** | 6천 행 규모에서 CPU로 빠르게 학습되고, feature 중요도로 설명 근거를 만들 수 있다 | 로컬 CPU |
| **Chronos-2** (시계열 파운데이션 모델, zero-shot) | 학습 없이 예측하므로 트리 모델과 성격이 다르다. 과거값 공변량을 지원한다 | 로컬 CPU (`docs/research/chronos2-precheck.md`) |

- **학습 목표**: h거래일 로그수익률 `log(y(t+h)/y(t))`을 예측한 뒤 가격으로 되돌린다. h별로 모델을 따로 학습한다.
- **하이퍼파라미터**: h별로, 테스트 시작 전의 검증 구간(2020~2022)에서만 고르고, 테스트 동안에는 고정한다. h = 21도 같은 24조합, 같은 검증 구간을 쓰고, 테스트 실행 전에 `lgbm_params.json`을 커밋한다.
- **향후 과제** (이번 범위 제외. docs/decisions.md 2026-11-05)
  - TabPFN (회귀, LightGBM과 같은 feature)
  - B3 계절 기준선: ŷ(t+3) = y(t) × 전년 같은 시기 3거래일 변화율
  - 요인 그룹 추가 실험: 가격만 → +반입량 → +기상(주산지 관측소), 같은 walk-forward로 비교. 반입량 출처·주산지는 `docs/research/data-sources.md`에서 조사 후 결정
  - Chronos-2 fine-tuning(Colab A100) vs zero-shot 비교

**Feature**: 모두 t 시점까지의 정보만 쓴다.

| 그룹 | feature |
|---|---|
| 가격 이력 | y(t−0…t−9) 지연값, 1·3·5·10거래일 수익률, 5·20거래일 이동평균과 표준편차 |
| 등급·시장 | 중품(05) 평균가와 상품/중품 비율, 시장별 가격의 최댓값−최솟값(spread) |
| 참여 시장 수 | t일 참여 시장 수, 직전 대비 변화 여부 |
| 달력 | 월, 연중 일자(sin/cos), 요일, t+h까지 남은 달력일 수(연휴 길이). **남은 달력일 수는 공휴일 달력으로만 계산하고, 실제 거래 데이터의 미래 날짜는 쓰지 않는다** |
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
- **기간**: h = 3, 7, 21 모두 같은 구간, 같은 재학습 주기, 같은 학습 창 비교를 쓴다.
- **Chronos-2** (사전 등록 2026-11-10, 결과를 보기 전에 고정)
  - 모델: `amazon/chronos-2` revision `29ec3766d36d6f73f0696f85560a422f50e8498c`, `chronos-forecasting==2.3.2`, CPU, zero-shot
  - 입력 시계열: 거래일(`평균` 행이 있는 날)만 이어 붙인 등간격 수열이다. 달력 날짜 공백을 만들지 않는다.
  - 이력: 예측 시점 t마다 2002-11 ~ t 전체를 넣는다. 8192 이하라 자르지 않는다. t 이후 값은 넣지 않는다.
  - 호출: 예측 시점마다 prediction_length = 21로 1회 호출하고 3·7·21번째 스텝을 쓴다. 점예측 = 0.5 분위수, 원 단위로 반올림한다.
  - 시계열끼리 정보를 섞지 않는다(`cross_learning=False`). batch 32, 예측 시점 순서로 묶는다.
  - 예측 시점: h별로 LightGBM 테스트와 같은 집합(934/930/916회). 코드에서 assert로 확인한다.
  - 입력 후보: (가) 상품 평균가만, (나) 상품 평균가 + 과거값 공변량(중품 평균가, 참여 시장 수). 중품 평균가가 없는 날은 결측으로 넣는다.
  - 입력 선택: 검증 구간(2020~2022, LightGBM 튜닝과 같은 h별 검증 예측 시점 739/735/721회) MAE로 h별로 하나를 고르고, 커밋한 뒤 테스트를 실행한다. 동률이면 (가). 테스트 결과로 입력을 고르지 않는다.
  - 테스트 구간은 고른 입력으로 1회만 실행한다.

## 6. LLM 설명

설명은 h = 3 예측만 대상으로 한다. API 호출로 간단히 구현한다.

- **입력**(JSON)
  - 예측값, 현재가, 차이와 등락률, 방향
  - 3거래일 후 예상 날짜
  - 최근 20거래일 추이 요약, 계절 비교(같은 달 과거 중앙값)
  - 참여 시장 수 변화
  - 모델의 기준선 대비 성능(상대 MAE)
- **출력**: 예상가격, 현재가와 차이, 주요 변동 요인, 주의사항을 쉬운 문장 4~6개로. 예측이 틀릴 수 있다는 문구를 포함한다.
- **근거 검사** (`explain/grounding.py`, 2026-11-10 강화): 실패하면 템플릿 문장으로 대체한다.
  - (a) 출력의 모든 숫자가 입력에 있다. 금액은 그대로이거나 10·100·1,000원 단위 반올림까지, %는 소수 첫째 자리 그대로이거나 정수 반올림까지 허용한다. 날짜는 입력 날짜와 맞아야 한다. 고정 상수는 5(kg), 20(거래일 창), 2023(성능 평가 시작 연도)만 허용한다.
    - 식별자 예외 (2026-11-12 개정): 입력 JSON에 문자열로 그대로 있는 영문+숫자 식별자(예: model `chronos2`)는 숫자 검사에서 뺀다. 그 밖의 허용 범위는 넓히지 않는다.
    - 계절 중앙값 표기 (2026-11-12 신설): `seasonal.median` 금액(그대로 또는 반올림, '만'·'천' 표기 포함)이 나오는 문장에 "중앙값"이 없으면 실패한다. 그 금액이 다른 입력 금액과 정확히 같으면 검사하지 않는다.
    - (a) = 숫자 근거(`a_numbers`) and 중앙값 표기(`a_median`). 규칙별 보고에는 둘을 따로 집계한다.
    - 개정 기록: 2026-11-12, 학습용 입력 프롬프트 시험(Gemini, 25개)에서 발견, 평가 결과 보기 전. 오탐("chronos2"의 2)과, 숫자는 맞지만 중앙값을 "평균"이라고 쓴 사실 오류(25개 중 14개)가 근거다. "다만"은 주의 단어로 추가하지 않는다.
  - (b) 입력에 없는 원인(날씨·태풍·폭염·수입·뉴스·작황·수급 등)을 말하지 않는다. 금지어 목록과 한계는 `docs/research/distill-precheck.md` §5에 있다.
  - (c) 문장 4~6개다. 예상가격, 현재가와 차이, 주요 요인(추이·계절·시장 수의 숫자), 주의 문구, 틀릴 수 있다는 문구가 들어간다.
  - 형식: 평문 한 문단(목록·제목·강조·사고 태그 없음), 80~800자, 한국어
  - 통과 = (a) and (b) and (c). explain은 통과와 형식을 모두 만족할 때만 LLM 문장을 쓴다.
- **모델**: 호출은 `explain/llm.py` 한 곳에만 둔다. 제공자는 설정(`LLM_PROVIDER`)으로만 고른다.
- **제공자·모델명** (사용자 결정 2026-11-10)
  - local: 증류한 학생 HyperCLOVA X SEED 14B Think를 ~~RTX 3080 10GB 데모 PC~~ **RTX 2080 Ti 22GB(개조) 데모 서버**에서 돌린다(2026-11-12 정정, decisions). §6.3 채택 기준을 통과할 때만 쓴다.
  - api: GPU가 없는 환경의 대체다. 사용자 키(BYOK, `.env`의 `GEMINI_API_KEY`)를 쓰고, 기본은 Gemini `gemini-3.1-flash-lite`다(2026-11-12 변경, 이전 `gemini-2.5-flash`·`LLM_API_KEY`).
  - auto: local → api → 템플릿 순서로 쓴다.
- **비용 상한**: 월 [미정: 사용자가 정할 값]. BYOK이므로 사용자 키의 한도를 따른다.
- **MVP 범위**: 뉴스는 넣지 않는다. 뉴스 출처는 [미정].
- **범위 제외: 해설 꼬리질문(대화형)** (사용자 결정 2026-11-12). 향후 과제다. 자유 질문을 받으면 LLM이 가격을 예측하게 될 위험이 있어서다. 수행계획서에는 있었으나 intent에서 빠진 항목이다.

### 6.1 LLM 해설 증류: 데이터 (사전 등록 2026-11-10, GPU 실행 전)
- **구조**
  - 선생: Qwen3.8-27B. A100 40GB면 FP8, 80GB면 bf16으로 돌리고 revision을 고정한다.
  - 학생: HyperCLOVA X SEED 14B Think (revision `9b74e35d…`)
  - QLoRA로 학습하고, bf16 원본에 merge한 뒤 4bit로 양자화한다.
  - 예비 선생 Gemini API는 프롬프트 시험에만 쓰고, 그 출력은 학습에 쓰지 않는다.
- **입력**
  - 과거 예측 시점마다 위 입력 JSON(h = 3)을 만든다(`explain/dataset.py`, `scripts/build_explain_inputs.py`).
  - 예측값은 Chronos-2 zero-shot이고 운영과 같은 설정을 쓴다. 데이터는 백테스트와 같이 2026-11-04까지다.
  - 각 시점은 그 시점까지의 행만 쓴다. 누수 테스트는 `tests/test_llm_dataset.py`에 있다.
  - 예외: performance(모델 성능 한 줄)는 모든 시점에 운영 화면과 같은 상수(2023 ~ 백테스트 값)를 넣는다. 배포 입력과 같게 하려는 것이고, 시점별 가격 정보는 담고 있지 않다.
- **분할** (시간 기준)
  - 학습: 2003 ~ 2021 거래일. 이 중 3,000개를 seed 20261111로 뽑는다.
  - 학습 설정용 검증: 2022 거래일. 이 중 200개를 같은 seed로 뽑는다.
  - 평가: 2023-01-02 ~ 2026-10-30, h = 3 테스트와 같은 934개다. 학습과 설정 선택에는 쓰지 않는다.
- **선생 생성**
  - 사고 출력은 끈다(`enable_thinking=False`). temperature 0.7, top_p 0.8, top_k 20, 최대 512토큰, 요청마다 seed를 고정한다.
  - 근거 검사(pass)와 형식을 통과한 출력만 학습에 쓴다. 실패하면 seed를 바꿔 최대 2번 다시 생성한다. 끝까지 실패한 시점은 뺀다.
  - 첫 시도 통과율을 보고한다.
- **선생 시범 생성** (2026-11-12 추가): 전체 생성 전에 학습용 입력 50개(2003 ~ 2021, seed 20261113)를 위 샘플링으로 첫 시도만 생성해 첫 시도 통과율(전체·규칙별)을 본다. 01 노트북의 시범 단계다. 시범 출력은 학습에 쓰지 않는다.
- **프롬프트** (`explain/prompt.py`)
  - 학습용 입력(2003 ~ 2021)으로만 다듬는다. v2(2026-11-12): 주의 문장을 "틀릴 수 있다" 문장과 따로 쓰고 '유의'·'참고'를 넣는다, 계절 비교 값은 "중앙값"으로 쓴다, 모델 이름을 쓰지 않는다.
  - 고정 시점은 선생 시범 뒤, 전체 생성을 시작할 때다. 그때의 `PROMPT_VERSION`으로 고정하고, 세 모델 평가에 같은 프롬프트를 쓴다.
  - 시범 뒤 프롬프트를 고치면 버전을 올리고 decisions에 기록한 뒤 시범을 다시 한다.
  - 평가 입력을 본 뒤에는 바꾸지 않는다.

### 6.2 LLM 해설 증류: 학습 설정 (사전 등록)
- **QLoRA**: NF4 이중 양자화, LoRA r 16, alpha 32, dropout 0.05
  - 대상: q, k, v, o, gate, up, down
  - 실효 batch 16, cosine, warmup 3%, 최대 2,048토큰
  - 손실은 정답(해설) 토큰에만 건다. 프롬프트는 `skip_reasoning=True` 형식이다.
- **설정 선택**: 학습률 {1e-4, 2e-4} × epoch {1, 2} 네 가지 중 하나를 고른다.
  - 기준은 검증 200개를 greedy로 생성했을 때의 근거 검사 통과율이다.
  - 동률이면 검증 손실이 낮은 쪽, 그다음 작은 학습률, 적은 epoch를 고른다.
  - 평가 입력은 쓰지 않는다.
- **4bit 형식**: bitsandbytes NF4(이중 양자화). 배포 때 embedding만 CPU에 두어 ~~RTX 3080 10GB~~ VRAM 10GB(§6.3 채택 기준) 안에 들어가게 한다. GGUF는 merge한 모델의 변환 경로가 없어 뺀다(`distill-precheck.md` §3).
  - 확정(사용자 결정 2026-11-12). 평가의 (i) 원본과 (ii) LoRA는 이 같은 형식으로 비교한다.
- **계산 dtype** (`bnb_4bit_compute_dtype`와 양자화하지 않는 가중치의 dtype): **fp16** (사용자 결정 2026-11-12. 2026-11-12 앞 개정의 [미정]을 닫는다)
  - 이유: 데모 서버 RTX 2080 Ti(Turing, 7.5)는 bf16을 하드웨어로 지원하지 않는다.
  - 조건: 데모 서버에서 학생 원본(NF4, embedding CPU, fp16)이 학습용 입력 3개를 NaN/inf 없이 생성해야 한다(`scripts/demo_gpu_check.py`, Docker). 실패하면 로컬 배포 불가로 보고 API(BYOK)로 간다.
  - 평가(§6.3)의 (i)·(ii)는 둘 다 fp16 계산으로 한다(04 노트북 `COMPUTE_DTYPE = "fp16"`). 03의 배포본도 양자화하지 않는 가중치를 fp16으로 저장한다.
  - QLoRA 학습과 설정 선택(검증 200개 생성)은 A100에서 bf16 그대로 한다.
  - 데모 서버의 모든 실행은 Docker(`--gpus all`, `deploy/demo-gpu/Dockerfile`) 안에서 한다. 호스트에는 패키지를 설치하지 않는다.

### 6.3 LLM 해설 증류: 평가와 채택 (사전 등록, 결과 보기 전)
- **비교 대상**: 평가 입력 934개에 같은 프롬프트로 세 모델을 비교한다.
  - (i) 학생 원본(LoRA 없음, 4bit)
  - (ii) LoRA 학생(merge 후 4bit, 실제 배포본)
  - (iii) 선생
- **생성 조건**
  - 모두 greedy, 최대 512토큰, 사고 출력은 끈다.
  - 학생은 배포 형식(NF4, embedding CPU)과 §6.2의 계산 dtype(fp16)으로 batch 16 생성한다.
  - 재생성은 하지 않는다.
- **지표** (`explain/scoring.py`, `scripts/score_distill.py`)
  - 근거 검사 통과율: 전체, (a)·(b)·(c) 규칙별, (a)의 숫자 근거·중앙값 표기 따로. 출력이 없으면 실패로 센다. 분모는 934다.
  - 출력 형식 준수율
  - 평균 생성 시간: 평가 입력 중 고정 seed로 뽑은 50개를 batch 1로 생성해 잰다(A100).
  - 최대 VRAM: 위 batch 1 측정 중 `torch.cuda.max_memory_reserved()`. A100에서 잰 대리 지표이고, ~~3080 데모~~ 데모 서버(RTX 2080 Ti 22GB)에서 다시 잰다(아래 채택 기준). 선생(vLLM)은 미리 잡는 메모리라 비교하지 않는다.
  - 사람 점검: (ii) 출력 중 무작위 30개(seed 20261111)를 사용자가 읽고 오류(사실 오류, 근거 없는 원인, 어색한 문장)를 기록한다. 채택 판정에는 쓰지 않는다.
- **채택 기준** (2026-11-12 개정, 결과 보기 전)
  - 다음 두 가지를 모두 만족하면 explain에 학생을 쓴다. 출력마다 근거 검사·형식에 실패하면 템플릿으로 대체한다.
    1. (ii)의 근거 검사 통과율이 90% 이상
    2. 데모 서버(RTX 2080 Ti 22GB)에서 (ii)를 배포 형식으로 batch 1 생성할 때 최대 VRAM이 10GB 이하
       - 입력: 위 시간 측정과 같은 평가 입력 50개, greedy, 최대 512토큰
       - 값: `torch.cuda.max_memory_reserved()`, 10GB = 10 × 10⁹ 바이트. `nvidia-smi` 사용량은 참고로 함께 적는다.
       - 측정: Docker 안에서 `scripts/demo_gpu_check.py --timing` → `distill/eval/student_lora_demo.json` (사용자 승인 2026-11-12)
  - 미달이면 학생을 쓰지 않는다. API(BYOK, `LLM_PROVIDER=api` 또는 auto)를 쓰고, 키가 없거나 실패하면 템플릿을 쓴다.
  - (2026-11-10 원안: 통과율 90% 이상이면 채택, 미달이면 템플릿 유지)
- **증류 효과**: (ii) − (i) 통과율 차이와 짝지은 개수(둘 다 통과, (i)만, (ii)만, 둘 다 실패)를 보고한다.
- **테스트 구간 사용**
  - 평가 입력은 2023 ~ 테스트 구간의 가격과 Chronos-2 예측으로 만든다.
  - 가격 모델의 선택이나 수치에는 영향이 없다. LLM 설정 선택에도 쓰지 않고, 이 평가에서 1회만 쓴다.

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
  horizon_tdays integer NOT NULL DEFAULT 3,
  model_name  text NOT NULL,
  segment     text NOT NULL,            -- 'test_all' | 'spike'
  metric      text NOT NULL,            -- 'mae' | 'mape' | 'rel_mae' | 'dir_acc_ud' | 'dir_acc3' | 'rmse' | 'sim_cost_a' | 'sim_cost_b' | 'sim_diff_won'(B − A) | 'sim_diff_pct'(B − A) | 'dm_stat' | 'dm_p'  (B3·오라클은 model_name 'B3', 'oracle_opt', 'oracle_rule')
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
  calendar.py          # 공휴일 달력(holidays KR), 거래일 계산, t+h 예상 날짜
  features.py          # §4 feature (t 시점까지만)
  models/baselines.py, models/lgbm.py, models/chronos.py
  evaluation/walkforward.py, evaluation/metrics.py, evaluation/simulation.py
  explain/llm.py, explain/grounding.py, explain/template.py
  api/main.py          # FastAPI: /forecast/latest, /prices, /health
  web/                 # 대시보드 한 화면: FastAPI 템플릿 + JS 차트
  cli.py
tests/                 # metrics, calendar, feature 누수 검사부터
docker-compose.yml, Dockerfile
```
- 의존성 관리: uv (`pyproject.toml` + `uv.lock`). docs/decisions.md 2026-11-01
- Chronos-2: 로컬 CPU에서 충분히 빨라 Colab과 `backtest import` 대신 `tomato backtest --models …,chronos2`로 직접 돌린다(`uv run --group chronos`, 2026-11-10). Colab 경로는 쓰지 않는다.

## 9. CLI 명령

컨테이너 안에서 `docker compose run --rm app tomato <명령>` 형태로 실행한다.

| 명령 | 역할 |
|---|---|
| `tomato db init` | `schema.sql` 적용 |
| `tomato collect backfill --market wholesale --from 2002-11-01 [--to …]` | 1년 단위로 나눠 받아 upsert |
| `tomato collect daily [--days 7]` | 최근 7일을 다시 받아 upsert. 실패 시 재시도(3회, 간격 증가), `ingest_run`에 기록 |
| `tomato backtest --models B1,B2,lgbm [--window full\|5y] [--horizons 3,7,21]` | walk-forward 실행, `backtest_metric` 저장, 표 출력 |
| `tomato train --model lgbm` | 최신 데이터로 학습해 `model_version` 등록 |
| `tomato predict [--origin YYYY-MM-DD]` | 3·7거래일 후 예측을 `forecast`에 저장 |
| `tomato explain [--forecast-id N]` | LLM 설명 생성과 근거 검사. 실패하면 템플릿 문장 |
| `tomato show latest` | 현재가, 예측, 설명 조회 |

- **스케줄**: 호스트 cron이 매일 20시에 `collect daily` → `predict` → `explain`을 컨테이너 안에서 실행한다.

## 10. 구현 순서

1. **B1으로 end-to-end**: 수집 → DB → B1 예측 → 템플릿 설명 → 대시보드 → Docker
2. **LightGBM + backtest**: B1·B2·LightGBM, h = 3·7, 학습 창 2종, 선택 규칙 적용, 매입 시뮬레이션
3. **LLM 설명**: `llm.py`, 근거 검사, 템플릿 대체
4. **Chronos-2** (로컬 CPU): 같은 예측 시점으로 예측 → 선택 규칙 다시 적용
5. **LLM 증류 학습**: Chronos-2 다음에 진행한다. 범위에 다시 넣었다(docs/decisions.md 2026-11-10). 선생 Qwen3.8-27B, 학생 HyperCLOVA X SEED 14B Think (§6.1~6.3)

## 11. 완료 기준 (MVP 1순위)

1. `docker compose up`으로 DB·API·대시보드가 뜬다.
2. `collect backfill` 결과 DB의 **가격이 있는 행과 `평균` 행**이 원본 CSV(`data-manifest.md`)와 키·값 모두 일치한다. `-` 가격은 NULL로 들어간다. `-` 행의 개수는 요청 기간 경계에 따라 달라지므로 기준에서 제외한다(`docs/research/stage1-check.md`).
3. `collect daily`가 실패하면 재시도하고, 실패 사유를 `ingest_run`에 남긴다. 실패 상황은 네트워크 차단으로 재현해 확인한다.
4. `backtest`가 B1·B2와 후보 모델을 **같은 fold, 같은 지표**로 비교한 표를 낸다.
   - 전체 테스트와 급등 구간을 따로 낸다.
   - 학습 창 비교(전체 vs 최근 5년)를 포함한다.
   - 기준선을 못 이기면 그대로 보고한다.
   - h = 3, 7을 각각 낸다.
   - 매입 시뮬레이션 표(§2)를 전체·급등 구간으로 낸다.
   - B3를 모든 표에 싣는다. 오라클 절감액(h = 3, 7)을 낸다. h = 21을 시뮬레이션 없이 내고, DM 결과를 사전 등록 기준(α = 0.025)으로 판정한다.
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
   - 매입 시뮬레이션: 작은 입력으로 A·B 비용과 차이를 손계산과 대조

---

## 남은 [미정]

| 항목 | 비고 |
|---|---|
| LLM 월 비용 상한 | 사용자가 정할 값 |
| 뉴스 출처 | MVP 이후 |
| KAMIS 실제 공표 시각 | 운영하면서 관찰해 기록 (비차단) |
