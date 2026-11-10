"""LLM 해설 증류용 입력 (spec §6.1). 과거 예측 시점마다 spec §6 입력 JSON(h = 3)을 만든다.

- 예측값은 Chronos-2 zero-shot(운영과 같은 입력·revision·0.5 분위수)이다.
- 각 시점의 입력은 daily[:i+1]만 쓴다. 예상 날짜는 운영과 같이 공휴일 달력으로 추정한다.
- 분할은 시간 기준: 2003 ~ 2021 학습, 2022 학습 설정용 검증, 2023 ~ 평가(학습에 쓰지 않음).
"""
import datetime as dt

from tomato import calendar as cal
from tomato.evaluation import metrics
from tomato.evaluation import walkforward as wf
from tomato.explain import template

HORIZON = 3
TRAIN_START = dt.date(2003, 1, 1)
VAL_START = dt.date(2022, 1, 1)  # 학습용 데이터에서 떼어 낸 검증 (LoRA 설정 선택에만)
TRAIN_END = dt.date(2022, 12, 31)
EVAL_START = wf.TEST_START


def split_of(d):
    if d >= EVAL_START:
        return "eval"
    if d >= VAL_START:
        return "val"
    if d >= TRAIN_START:
        return "train"
    return None


def train_origins(daily):
    return [i for i, r in enumerate(daily) if TRAIN_START <= r.date <= TRAIN_END and i >= 1]


def forecast_at(daily, i, y_hat, holidays, model="chronos2"):
    """cli.cmd_predict가 저장하는 forecast와 같은 형식. daily[:i+1]만 쓴다."""
    t, y0 = daily[i].date, daily[i].price
    r = metrics.change(y0, y_hat)
    return {
        "origin_date": t, "target_date_est": cal.add_trading_days(t, HORIZON, holidays),
        "horizon_tdays": HORIZON, "model": model, "y_origin": y0, "y_hat": y_hat,
        "change_pct": round(100 * r, 3), "direction": metrics.direction(r),
    }


def record(daily, i, y_hat, perf, holidays):
    f = forecast_at(daily, i, y_hat, holidays)
    return {
        "id": f"h{HORIZON}-{daily[i].date.isoformat()}",
        "split": split_of(daily[i].date),
        "input": template.build_input([(r.date, r.price, r.n_markets) for r in daily[: i + 1]], f, perf),
    }
