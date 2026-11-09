import datetime as dt
import math

import pytest

from tomato.evaluation import posthoc

D = dt.date(2023, 1, 2)


def test_trend_rule_is_opposite_of_b2_direction():
    # 최근 5일 평균 100, 현재 110 → 추세 규칙은 상승 예측
    rows = [{"origin_date": D, "y0": 110, "y": 120}, {"origin_date": D + dt.timedelta(1), "y0": 110, "y": 100}]
    hist = {D: [95, 95, 100, 100, 110], D + dt.timedelta(1): [95, 95, 100, 100, 110]}
    acc, n = posthoc.trend_updown_accuracy(rows, hist)
    assert (acc, n) == (0.5, 2)  # +9.1% 상승은 적중, −9.1% 하락은 오답


def test_trend_rule_flat_prediction_counts_as_wrong():
    rows = [{"origin_date": D, "y0": 100, "y": 120}]
    assert posthoc.trend_updown_accuracy(rows, {D: [100] * 5}) == (0.0, 1)


def test_dm_lag0_matches_simple_t_statistic():
    e_model = [1, 2, 3, 4, 1, 2]
    e_base = [2, 2, 5, 4, 3, 2]
    d = [abs(a) - abs(b) for a, b in zip(e_model, e_base)]
    mean = sum(d) / 6
    var = sum((x - mean) ** 2 for x in d) / 6
    out = posthoc.diebold_mariano(e_model, e_base, 1)
    assert out["stat"] == pytest.approx(mean / math.sqrt(var / 6))
    assert out["p"] == pytest.approx(math.erfc(abs(out["stat"]) / math.sqrt(2)))
    assert out["stat"] < 0  # 모델 오차가 작으면 음수


def test_dm_uses_autocovariances_up_to_h_minus_1():
    e_model = [1, 3, 2, 5, 1, 4, 2, 6]
    e_base = [2, 2, 2, 2, 2, 2, 2, 2]
    d = [a - 2 for a in e_model]
    n, mean = len(d), sum(d) / len(d)
    g = [sum((d[t] - mean) * (d[t - k] - mean) for t in range(k, n)) / n for k in range(3)]
    out = posthoc.diebold_mariano(e_model, e_base, 3)
    assert out["stat"] == pytest.approx(mean / math.sqrt((g[0] + 2 * (g[1] + g[2])) / n))


def test_dm_rejects_non_positive_variance():
    with pytest.raises(ValueError):
        posthoc.diebold_mariano([1, 1, 1], [0, 0, 0], 1)
