"""Chronos-2 누수 검사와 예측 시점 집합 (spec §5). 실제 모델은 CHRONOS_REAL=1일 때만."""
import datetime as dt
import math
import os

import numpy as np
import pytest

from test_features import make_daily
from tomato.evaluation import walkforward as wf
from tomato.models import baselines, chronos2, lgbm

START = dt.date(2020, 9, 1)


class FakePipe:
    """입력만으로 정해지는 가짜 모델: 스텝 k의 중앙값 = 마지막 값 + k + 공변량 마지막 값 합."""

    def __init__(self):
        self.calls = []

    def predict_quantiles(self, inputs, prediction_length, quantile_levels, batch_size, cross_learning):
        self.calls.append({"inputs": inputs, "cross_learning": cross_learning, "levels": quantile_levels})
        out = []
        for x in inputs:
            extra = sum(np.nan_to_num(v[-1]) for v in x.get("past_covariates", {}).values())
            base = x["target"][-1] + extra
            out.append(np.array([[[base + k] for k in range(1, prediction_length + 1)]]))
        return out, None


@pytest.mark.parametrize("variant", chronos2.VARIANTS)
def test_input_at_t_has_no_rows_after_t(variant):
    daily = make_daily(600)
    pipe = FakePipe()
    origins = chronos2.origin_indices(daily, START)
    chronos2.predict(pipe, daily, origins, variant)
    seen = [x for c in pipe.calls for x in c["inputs"]]
    assert len(seen) == len(origins)
    for i, x in zip(origins, seen):
        assert len(x["target"]) == i + 1
        np.testing.assert_array_equal(x["target"], [r.price for r in daily[: i + 1]])
        for v in x.get("past_covariates", {}).values():
            assert len(v) == i + 1
    assert all(c["cross_learning"] is False and c["levels"] == [0.5] for c in pipe.calls)


@pytest.mark.parametrize("variant", chronos2.VARIANTS)
def test_prediction_does_not_change_with_data_after_t(variant):
    daily = make_daily(600)
    i = 500
    changed = daily[: i + 1] + [r._replace(price=r.price * 3, n_markets=1, mid_price=1) for r in daily[i + 1 :]]
    a = chronos2.predict(FakePipe(), daily, [i], variant)[i]
    b = chronos2.predict(FakePipe(), changed, [i], variant)[i]
    np.testing.assert_array_equal(a, b)


def test_missing_mid_price_is_nan_covariate():
    daily = make_daily(30)
    daily[-1] = daily[-1]._replace(mid_price=None)
    x = chronos2.make_input(daily, 29, "cov")
    assert math.isnan(x["past_covariates"]["mid_price"][-1])
    with pytest.raises(ValueError):
        chronos2.make_input(daily, 29, "x")


@pytest.mark.parametrize("h", [3, 7, 21])
def test_origin_set_matches_baseline_and_lgbm(h):
    daily = make_daily(1000, dt.date(2019, 1, 1))
    start = daily[900].date
    preds = chronos2.predict(FakePipe(), daily, chronos2.origin_indices(daily, start), "target")
    series = [(r.date, r.price) for r in daily]
    small = {"objective": "l2", "num_leaves": 7, "min_data_in_leaf": 20, "learning_rate": 0.1, "num_boost_round": 5}
    rows = chronos2.rows(daily, preds, h, start)
    wf.assert_same_origins({"B1": wf.backtest(series, baselines.b1, start=start, horizon=h),
                            "lgbm": lgbm.backtest(daily, h, small, "full", start=start), "chronos2": rows})


def test_rows_use_step_h_median():
    daily = make_daily(100)
    preds = {i: np.arange(1, 22) * 1000.0 for i in range(100)}
    for h in (3, 7, 21):
        assert chronos2.rows(daily, preds, h, daily[50].date)[0]["y_hat"] == h * 1000


def test_choose_ties_go_to_target():
    assert chronos2.choose({3: {"target": 10.0, "cov": 9.0}, 7: {"target": 5.0, "cov": 5.0}}) == {"3": "cov", "7": "target"}


def test_missing_choice_file_fails(tmp_path):
    with pytest.raises(FileNotFoundError):
        chronos2.load_choice(tmp_path / "none.json")


@pytest.mark.skipif(os.environ.get("CHRONOS_REAL") != "1", reason="CHRONOS_REAL=1일 때만 실제 모델")
@pytest.mark.parametrize("variant", chronos2.VARIANTS)
def test_real_model_ignores_future_and_batch_mates(variant):
    daily = make_daily(400)
    pipe = chronos2.load_pipeline()
    i = 300
    changed = daily[: i + 1] + [r._replace(price=r.price * 3) for r in daily[i + 1 :]]
    alone = chronos2.predict(pipe, daily, [i], variant)[i]
    np.testing.assert_array_equal(alone, chronos2.predict(pipe, changed, [i], variant)[i])
    batched = chronos2.predict(pipe, daily, list(range(i - 10, i + 22)), variant)[i]  # 뒤 시점과 같은 batch
    np.testing.assert_allclose(alone, batched, rtol=1e-4)
