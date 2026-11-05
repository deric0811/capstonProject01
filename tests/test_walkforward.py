import datetime as dt

import pytest

from test_features import make_daily
from tomato.evaluation import metrics, walkforward as wf
from tomato.features import Daily
from tomato.models import baselines, lgbm

SMALL = {"objective": "l2", "num_leaves": 7, "min_data_in_leaf": 20, "learning_rate": 0.1, "num_boost_round": 10}


def test_b2_is_last_five_mean():
    assert baselines.b2([1, 100, 200, 300, 400, 500]) == 300
    assert baselines.b2([100, 200]) == 150


@pytest.mark.parametrize("h", [3, 7])
def test_baseline_rows_have_t_plus_1_and_t_plus_h(h):
    d0 = dt.date(2023, 1, 2)
    series = [(d0 + dt.timedelta(days=i), 100 + i) for i in range(20)]
    rows = wf.backtest(series, baselines.b1, start=d0, horizon=h)
    assert len(rows) == 20 - h
    assert (rows[0]["y0"], rows[0]["y1"], rows[0]["y"]) == (100, 101, 100 + h)


def test_h7_origins_are_prefix_of_h3():
    d0 = dt.date(2023, 1, 2)
    series = [(d0 + dt.timedelta(days=i), 100) for i in range(20)]
    o3 = [r["origin_date"] for r in wf.backtest(series, baselines.b1, start=d0, horizon=3)]
    o7 = [r["origin_date"] for r in wf.backtest(series, baselines.b1, start=d0, horizon=7)]
    assert o7 == o3[:-4]


def test_folds_retrain_on_first_trading_day_of_each_month():
    days = [dt.date(2023, 1, 30), dt.date(2023, 1, 31), dt.date(2023, 2, 1), dt.date(2023, 2, 2), dt.date(2023, 3, 2)]
    assert wf.folds(days, dt.date(2023, 1, 31)) == [(1, [1]), (2, [2, 3]), (4, [4])]


@pytest.mark.parametrize("h", [3, 7])
@pytest.mark.parametrize("window", ["full", "5y"])
def test_training_labels_are_published_before_retrain_day(h, window):
    days = [r.date for r in make_daily(2000, dt.date(2015, 1, 1))]
    for i0 in (1500, 1800, 1999):
        idx = wf.train_indices(days, i0, h, window)
        assert max(idx) + h == i0 - 1  # 라벨 날짜 <= 재학습 전날, 그 안에서는 빠짐없이
        assert days[max(idx) + h] < days[i0]


def test_5y_window_starts_five_years_before_retrain_day():
    days = [r.date for r in make_daily(2000, dt.date(2015, 1, 1))]
    i0 = 1800
    idx = wf.train_indices(days, i0, 3, "5y")
    since = days[i0].replace(year=days[i0].year - 5)
    assert days[idx[0]] >= since and days[idx[0] - 1] < since
    assert wf.train_indices(days, i0, 3, "full")[0] == 0
    with pytest.raises(ValueError):
        wf.train_indices(days, i0, 3, "2y")


@pytest.mark.parametrize("h", [3, 7])
def test_lgbm_prediction_does_not_change_with_data_after_origin(h):
    daily = make_daily(1000, dt.date(2019, 1, 1))
    start = daily[900].date
    base = lgbm.backtest(daily, h, SMALL, "full", start=start)
    i = 950
    origin = daily[i].date
    changed = daily[: i + 1] + [r._replace(price=r.price * 2, n_markets=1) for r in daily[i + 1 :]]
    other = lgbm.backtest(changed, h, SMALL, "full", start=start)
    get = lambda rows: next(r["y_hat"] for r in rows if r["origin_date"] == origin)  # noqa: E731
    assert get(base) == get(other)


def test_lgbm_rows_match_baseline_origin_set():
    daily = make_daily(1000, dt.date(2019, 1, 1))
    start = daily[950].date
    series = [(r.date, r.price) for r in daily]
    for h in (3, 7):
        wf.assert_same_origins({
            "B1": wf.backtest(series, baselines.b1, start=start, horizon=h),
            "lgbm": lgbm.backtest(daily, h, SMALL, "5y", start=start),
        })


def test_different_origin_sets_fail():
    a = [{"origin_date": dt.date(2023, 1, 2), "y0": 1, "y": 1, "y1": 1, "y_hat": 1}]
    b = [{"origin_date": dt.date(2023, 1, 3), "y0": 1, "y": 1, "y1": 1, "y_hat": 1}]
    with pytest.raises(ValueError):
        wf.assert_same_origins({"x": a, "y": b})
    with pytest.raises(ValueError):
        wf.score(a, b)


def test_tuning_input_is_cut_before_test_period():
    daily = [Daily(dt.date(2022, 12, 30), 1, 1, 1, 1), Daily(dt.date(2022, 12, 31), 1, 1, 1, 1),
             Daily(dt.date(2023, 1, 1), 1, 1, 1, 1)]
    assert [r.date.year for r in lgbm.cut_to_validation(daily)] == [2022, 2022]


def test_validation_mae_ignores_test_period(monkeypatch):
    daily = make_daily(1100, dt.date(2019, 1, 1))  # 2023년까지 이어지는 데이터
    assert daily[-1].date >= dt.date(2023, 1, 1)
    seen = {}

    def spy(d, h, p, w, start):
        seen["last"], seen["start"] = d[-1].date, start
        return [{"y": 1, "y_hat": 1}]

    monkeypatch.setattr(lgbm, "backtest", spy)
    lgbm.validation_mae(lgbm.cut_to_validation(daily), 3, SMALL, "full")
    assert seen["last"] <= wf.VALID_END and seen["start"] == wf.VALID_START


def test_validation_origins_have_targets_inside_validation():
    daily = lgbm.cut_to_validation(make_daily(1100, dt.date(2019, 1, 1)))
    rows = lgbm.backtest(daily, 7, SMALL, "full", start=dt.date(2022, 11, 1))
    assert rows and max(r["target_date"] for r in rows) <= wf.VALID_END


def test_choose_picks_lowest_mae_per_window_and_lower_window_per_horizon():
    res = {3: {"full": {0: 10.0, 1: 9.0}, "5y": {0: 8.0, 1: 12.0}}, 7: {"full": {0: 5.0, 1: 5.0}, "5y": {0: 5.0, 1: 6.0}}}
    out = lgbm.choose(res)
    assert out["3"]["selected_window"] == "5y"
    assert out["3"]["full"] == {"params": lgbm.GRID[1], "val_mae": 9.0}
    assert out["3"]["5y"] == {"params": lgbm.GRID[0], "val_mae": 8.0}
    assert out["7"]["selected_window"] == "full"  # 동률이면 full
    assert out["7"]["full"]["params"] == lgbm.GRID[0]  # 동률이면 grid 앞쪽


def test_missing_params_file_fails(tmp_path):
    with pytest.raises(FileNotFoundError):
        lgbm.load_params(tmp_path / "none.json")


def test_lgbm_price_is_inverse_of_log_return_target():
    daily = make_daily(1000, dt.date(2019, 1, 1))
    rows = lgbm.backtest(daily, 3, SMALL, "full", start=daily[990].date)
    assert all(abs(metrics.change(r["y0"], r["y_hat"])) < 1 for r in rows)
