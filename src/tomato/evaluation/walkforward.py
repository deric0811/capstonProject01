"""시간순 평가 (spec §5). 기준선은 시점마다 예측하고, LightGBM은 매달 첫 거래일에 재학습한다."""
import datetime as dt

from tomato.calendar import observed_target
from tomato.evaluation import metrics, posthoc, simulation
from tomato.models import baselines

TEST_START = dt.date(2023, 1, 1)
VALID_START = dt.date(2020, 1, 1)
VALID_END = dt.date(2022, 12, 31)
SPIKE = (dt.date(2023, 9, 1), dt.date(2024, 12, 31))  # 예측 시점 기준
HORIZON = 3
HORIZONS = (3, 7)  # 운영(predict)과 매입 시뮬레이션 대상
SIM_HORIZONS = (3, 7)
DM_HORIZONS = (21,)  # 사전 등록한 DM 검정 (spec §2, 본페로니 α = 0.025)
DM_ALPHA = 0.05 / 2
CHRONOS_DM_ALPHA = 0.05 / 3  # Chronos-2 vs LightGBM full, h = 3·7·21 전체 구간 (spec §2, 2026-11-10)
WINDOWS = ("full", "5y")


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
        history = [p for _, p in series[: i + 1]]
        out.append({"origin_date": t, "target_date": target, "y0": y0, "y1": series[i + 1][1], "y": price[target],
                    "y_hat": round(predict(history)), "mean5": baselines.b2(history)})
    return out


def folds(days, start):
    """[(재학습 위치 i0, 그달 예측 시점 위치들)]. i0 = start 이후 각 달의 첫 거래일."""
    out = {}
    for i, d in enumerate(days):
        if d >= start:
            out.setdefault((d.year, d.month), []).append(i)
    return [(idx[0], idx) for idx in out.values()]


def train_indices(days, i0, horizon, window):
    """i0에서 재학습할 때 쓸 행. 라벨 y(t+h)가 재학습 전날까지 공표된 행만 쓴다."""
    since = days[0]
    if window == "5y":
        d = days[i0]
        since = d.replace(year=d.year - 5, day=28 if (d.month, d.day) == (2, 29) else d.day)
    elif window != "full":
        raise ValueError(f"알 수 없는 학습 창: {window}")
    return [j for j in range(i0 - horizon) if days[j] >= since]


def assert_same_origins(rows_by_model):
    """모든 모델의 예측 시점 집합이 같아야 한다."""
    sets = {name: [r["origin_date"] for r in rows] for name, rows in rows_by_model.items()}
    first = next(iter(sets.values()))
    bad = [name for name, s in sets.items() if s != first]
    if bad:
        raise ValueError(f"예측 시점 집합이 다릅니다: {bad}")


def score(rows, b1_rows, simulate=True):
    """rows와 b1_rows는 같은 예측 시점 집합이어야 한다. [{'metric', 'value', 'n'}]"""
    assert_same_origins({"model": rows, "B1": b1_rows})
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
        *(simulation.simulate(rows) if simulate else []),
    ]


def score_b3(rows, simulate=True):
    """B3 추세 규칙: 상승/하락 적중률과 매입 시뮬레이션만. rows에 mean5 필요."""
    pseudo = [r["y0"] + (r["y0"] - r["mean5"]) for r in rows]  # 부호만 쓰므로 예측 등락률의 부호 = y(t) − 평균의 부호
    ud, n_ud = metrics.updown_accuracy([r["y0"] for r in rows], [r["y"] for r in rows], pseudo)
    out = [{"metric": "dir_acc_ud", "value": ud, "n": n_ud}]
    return out + (simulation.simulate(rows, simulation.b3_buys_now) if simulate else [])


def score_oracle(rows, buys_now):
    return simulation.simulate(rows, buys_now)


def score_dm(rows, b1_rows, horizon):
    """LightGBM vs B1 DM 검정 (spec §2). 분산이 0 이하면 Bartlett 가중."""
    assert_same_origins({"model": rows, "B1": b1_rows})
    dm = posthoc.diebold_mariano([r["y"] - r["y_hat"] for r in rows], [r["y"] - r["y_hat"] for r in b1_rows], horizon,
                                 fallback=True)
    return [{"metric": "dm_stat", "value": dm["stat"], "n": dm["n"]},
            {"metric": "dm_p", "value": dm["p"], "n": dm["n"]}], dm


def segments(rows):
    spike = [r for r in rows if SPIKE[0] <= r["origin_date"] <= SPIKE[1]]
    return {"test_all": rows, "spike": spike}
