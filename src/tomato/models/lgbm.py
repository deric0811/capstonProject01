"""LightGBM (spec §4). 목표는 h거래일 로그수익률이고, 예측 뒤 가격으로 되돌린다.

튜닝은 2022-12-31까지 자른 데이터만 본다. 테스트 실행은 lgbm_params.json을 읽기만 한다.
"""
import itertools
import json
import math
from pathlib import Path

import lightgbm as lgb
import numpy as np

from tomato import features
from tomato.evaluation import metrics, walkforward as wf

PARAMS_FILE = Path(__file__).with_name("lgbm_params.json")
FIXED = {"feature_fraction": 0.8, "seed": 42, "deterministic": True, "force_row_wise": True, "num_threads": 1,
         "verbosity": -1}
GRID = [
    {"objective": o, "num_leaves": n, "min_data_in_leaf": m, "learning_rate": lr, "num_boost_round": b}
    for o, n, m, (lr, b) in itertools.product(("l2", "l1"), (7, 15, 31), (20, 50), ((0.05, 100), (0.02, 300)))
]


def fit(X, y, params):
    p = {**FIXED, **params}
    rounds = p.pop("num_boost_round")
    return lgb.train(p, lgb.Dataset(X, label=y, feature_name=features.NAMES), num_boost_round=rounds)


def backtest(daily, horizon, params, window, start=wf.TEST_START):
    """매달 첫 거래일에 재학습해 그달 예측 시점을 예측한다. 행 형식은 walkforward.backtest와 같다."""
    days = [r.date for r in daily]
    y = np.array([r.price for r in daily], dtype=float)
    X = features.build(daily, horizon)
    n = len(daily)
    labels = np.full(n, np.nan)
    labels[: n - horizon] = np.log(y[horizon:] / y[: n - horizon])
    out = []
    for i0, origins in wf.folds(days, start):
        origins = [i for i in origins if i + horizon < n]
        if not origins:
            continue
        train = wf.train_indices(days, i0, horizon, window)
        booster = fit(X[train], labels[train], params)
        for i, pred in zip(origins, booster.predict(X[origins]), strict=True):
            out.append({"origin_date": days[i], "target_date": days[i + horizon], "y0": daily[i].price,
                        "y1": daily[i + 1].price, "y": daily[i + horizon].price,
                        "y_hat": round(daily[i].price * math.exp(pred))})
    return out


def validation_mae(daily, horizon, params, window):
    rows = backtest(daily, horizon, params, window, start=wf.VALID_START)
    return metrics.mae([r["y"] for r in rows], [r["y_hat"] for r in rows]), len(rows)


def cut_to_validation(daily):
    """2023년 이후 데이터는 튜닝 함수에 넘기지 않는다. t+h도 검증 구간 안에 있게 된다."""
    return [r for r in daily if r.date <= wf.VALID_END]


def choose(results):
    """results = {h: {window: {grid 위치: val MAE}}}. h·창별 최저 조합과, h별 검증 MAE가 낮은 창을 고른다."""
    out = {}
    for h, by_window in results.items():
        best = {}
        for w, maes in by_window.items():
            k = min(maes, key=lambda g: (maes[g], g))  # 동률이면 grid 앞쪽
            best[w] = {"params": GRID[k], "val_mae": maes[k]}
        selected = min(wf.WINDOWS, key=lambda w: best[w]["val_mae"])  # 동률이면 full
        out[str(h)] = {"selected_window": selected, **best}
    return out


def load_params(path=PARAMS_FILE):
    if not path.exists():
        raise FileNotFoundError(f"{path.name}가 없습니다. 먼저 scripts/tune_lgbm.py를 실행하세요.")
    return json.loads(path.read_text(encoding="utf-8"))
