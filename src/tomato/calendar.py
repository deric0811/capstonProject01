"""거래일 계산.

- 미래 거래일(예상 날짜)은 평일 중 공휴일(holidays KR)을 뺀 날로 추정한다.
- 과거 거래일은 실제로 `평균` 행이 있는 날이다(토요일 거래 포함).
- 남은 달력일 수(feature)는 공휴일 달력만으로 계산한다. 거래 데이터의 미래 날짜를 쓰면 누수다.
"""
import bisect
import datetime as dt

import holidays as _holidays


def kr_holidays(years):
    return set(_holidays.KR(years=list(years)))


def is_business_day(d, holidays):
    return d.weekday() < 5 and d not in holidays


def add_trading_days(origin, n, holidays):
    d = origin
    while n > 0:
        d += dt.timedelta(days=1)
        if is_business_day(d, holidays):
            n -= 1
    return d


def calendar_days_until(origin, n, holidays):
    return (add_trading_days(origin, n, holidays) - origin).days


def observed_target(trading_days, origin, n):
    """정렬된 실제 거래일 목록에서 origin의 n거래일 뒤 날짜. 없으면 None."""
    i = bisect.bisect_left(trading_days, origin)
    if i == len(trading_days) or trading_days[i] != origin or i + n >= len(trading_days):
        return None
    return trading_days[i + n]
