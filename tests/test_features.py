"""feature 누수 검사 (spec §11-8). h = 3, 7."""
import datetime as dt
import math

import numpy as np
import pytest

from tomato import calendar as cal
from tomato import features
from tomato.features import Daily


def make_daily(n=700, start=dt.date(2019, 1, 1)):
    out, d = [], start
    while len(out) < n:
        if d.weekday() < 5:
            i = len(out)
            p = 20000 + round(3000 * math.sin(i / 17)) + (i * 37) % 900
            out.append(Daily(d, p, 5 + i // 200, round(p * 0.8), 1000 + (i * 13) % 500))
        d += dt.timedelta(days=1)
    return out


@pytest.mark.parametrize("h", [3, 7])
def test_row_is_same_when_data_after_t_is_removed(h):
    daily = make_daily()
    full = features.build(daily, h)
    for i in (0, 1, 9, 20, 262, 400, 699):
        np.testing.assert_array_equal(features.build(daily[: i + 1], h)[i], full[i])


@pytest.mark.parametrize("h", [3, 7])
def test_row_is_same_when_values_after_t_change(h):
    daily = make_daily()
    i = 400
    changed = daily[: i + 1] + [r._replace(price=r.price * 3, n_markets=1, mid_price=1, spread=1) for r in daily[i + 1 :]]
    np.testing.assert_array_equal(features.build(changed, h)[i], features.build(daily, h)[i])


@pytest.mark.parametrize("h", [3, 7])
def test_days_to_target_ignores_actual_future_trading_days(h):
    daily = make_daily()
    i = 400
    k = features.NAMES.index("days_to_target")
    # 미래 거래일을 지워도(휴장) 값이 같고, 공휴일 달력으로 계산한 값과 같아야 한다.
    without = daily[: i + 1] + daily[i + 4 :]
    assert features.build(without, h)[i, k] == features.build(daily, h)[i, k]
    holidays = cal.kr_holidays(range(2019, 2023))
    assert features.build(daily, h)[i, k] == cal.calendar_days_until(daily[i].date, h, holidays)


def test_days_to_target_is_longer_for_h7():
    daily = make_daily(50)
    k = features.NAMES.index("days_to_target")
    assert (features.build(daily, 7)[:, k] > features.build(daily, 3)[:, k]).all()


def test_shape_matches_names_and_known_values():
    daily = make_daily(30)
    X = features.build(daily, 3)
    assert X.shape == (30, len(features.NAMES))
    get = lambda name, i: X[i, features.NAMES.index(name)]  # noqa: E731
    assert get("lag_0", 29) == daily[29].price
    assert get("lag_9", 29) == daily[20].price
    assert math.isnan(get("lag_9", 8))
    assert get("ret_3", 29) == pytest.approx(daily[29].price / daily[26].price - 1)
    assert get("ma_5", 29) == pytest.approx(sum(r.price for r in daily[25:30]) / 5)
    assert get("top_mid_ratio", 29) == pytest.approx(daily[29].price / daily[29].mid_price)


def test_prev_year_price_uses_latest_trading_day_on_or_before_year_ago():
    daily = make_daily(400)
    X = features.build(daily, 3)
    k = features.NAMES.index("prev_year_price")
    i = 300
    ago = daily[i].date.replace(year=daily[i].date.year - 1)
    assert X[i, k] == [r.price for r in daily if r.date <= ago][-1]
    assert math.isnan(X[100, k])


def test_missing_mid_and_spread_become_nan():
    daily = make_daily(5)
    daily[4] = daily[4]._replace(mid_price=None, spread=None)
    X = features.build(daily, 3)
    assert math.isnan(X[4, features.NAMES.index("mid_price")])
    assert math.isnan(X[4, features.NAMES.index("top_mid_ratio")])
    assert math.isnan(X[4, features.NAMES.index("market_spread")])
