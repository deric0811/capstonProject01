"""LightGBM feature (spec §4). 각 행은 그 거래일 t까지의 정보만 쓴다.

남은 달력일 수는 공휴일 달력으로만 계산한다. 실제 거래 데이터의 미래 날짜는 쓰지 않는다.
"""
import bisect
import datetime as dt
import math
import statistics
from typing import NamedTuple

import numpy as np

from tomato import calendar as cal

LAGS = range(10)
RETURNS = (1, 3, 5, 10)
ROLLING = (5, 20)
NAMES = (
    [f"lag_{k}" for k in LAGS]
    + [f"ret_{k}" for k in RETURNS]
    + [f"{s}_{k}" for k in ROLLING for s in ("ma", "std")]
    + ["mid_price", "top_mid_ratio", "market_spread", "n_markets", "n_markets_changed"]
    + ["month", "doy_sin", "doy_cos", "weekday", "days_to_target"]
    + ["prev_year_price", "month_median_ratio"]
)


class Daily(NamedTuple):
    date: dt.date
    price: int
    n_markets: int
    mid_price: int | None
    spread: int | None


def _year_ago(d):
    try:
        return d.replace(year=d.year - 1)
    except ValueError:  # 2월 29일
        return d.replace(year=d.year - 1, day=28)


def build(daily, horizon):
    """daily = 날짜순 Daily 목록. 행 i는 daily[:i+1]과 공휴일 달력만 쓴다."""
    days = [r.date for r in daily]
    y = [r.price for r in daily]
    holidays = cal.kr_holidays(range(days[0].year, days[-1].year + 2))
    by_month = {}
    X = np.full((len(daily), len(NAMES)), np.nan)
    for i, r in enumerate(daily):
        t = r.date
        by_month.setdefault(t.month, []).append(r.price)
        row = [y[i - k] if i >= k else math.nan for k in LAGS]
        row += [y[i] / y[i - k] - 1 if i >= k else math.nan for k in RETURNS]
        for k in ROLLING:
            if i + 1 >= k:
                w = y[i + 1 - k : i + 1]
                row += [sum(w) / k, statistics.pstdev(w)]
            else:
                row += [math.nan, math.nan]
        row += [
            r.mid_price if r.mid_price is not None else math.nan,
            r.price / r.mid_price if r.mid_price else math.nan,
            r.spread if r.spread is not None else math.nan,
            r.n_markets,
            float(r.n_markets != daily[i - 1].n_markets) if i else math.nan,
        ]
        doy = t.timetuple().tm_yday
        row += [
            t.month,
            math.sin(2 * math.pi * doy / 365.25),
            math.cos(2 * math.pi * doy / 365.25),
            t.weekday(),
            cal.calendar_days_until(t, horizon, holidays),
        ]
        j = bisect.bisect_right(days, _year_ago(t), 0, i + 1) - 1
        row += [y[j] if j >= 0 else math.nan, r.price / statistics.median(by_month[t.month])]
        X[i] = row
    return X
