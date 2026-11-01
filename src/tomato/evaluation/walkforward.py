"""시간순 평가 (spec §5). 1단계는 학습이 없는 B1만 다룬다. 학습 모델의 월별 재학습은 2단계."""
import datetime as dt

from tomato.calendar import observed_target
from tomato.evaluation import metrics

TEST_START = dt.date(2023, 1, 1)
SPIKE = (dt.date(2023, 9, 1), dt.date(2024, 12, 31))  # 예측 시점 기준
HORIZON = 3


def backtest(series, predict, start=TEST_START, horizon=HORIZON):
    """series = [(date, price)] 날짜순. t >= start이고 t+horizon 실제값이 있는 모든 t에서 예측."""
    days = [d for d, _ in series]
    price = dict(series)
    out = []
    for i, (t, y0) in enumerate(series):
        if t < start:
            continue
        target = observed_target(days, t, horizon)
        if target is None:
            break
        y_hat = round(predict([p for _, p in series[: i + 1]]))
        out.append({"origin_date": t, "target_date": target, "y0": y0, "y": price[target], "y_hat": y_hat})
    return out


def score(rows, b1_rows):
    """rows와 b1_rows는 같은 예측 시점 집합이어야 한다. [{'metric', 'value', 'n'}]"""
    assert [r["origin_date"] for r in rows] == [r["origin_date"] for r in b1_rows]
    y0, y, yh = ([r[k] for r in rows] for k in ("y0", "y", "y_hat"))
    ud, n_ud = metrics.updown_accuracy(y0, y, yh)
    n = len(rows)
    return [
        {"metric": "mae", "value": metrics.mae(y, yh), "n": n},
        {"metric": "mape", "value": metrics.mape(y, yh), "n": n},
        {"metric": "rmse", "value": metrics.rmse(y, yh), "n": n},
        {"metric": "rel_mae", "value": metrics.relative_mae(y, yh, [r["y_hat"] for r in b1_rows]), "n": n},
        {"metric": "dir_acc_ud", "value": ud, "n": n_ud},
        {"metric": "dir_acc3", "value": metrics.three_class_accuracy(y0, y, yh), "n": n},
    ]


def segments(rows):
    spike = [r for r in rows if SPIKE[0] <= r["origin_date"] <= SPIKE[1]]
    return {"test_all": rows, "spike": spike}
