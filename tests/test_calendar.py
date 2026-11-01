import datetime as dt
import inspect

from tomato import calendar as cal

D = dt.date


def test_friday_plus_3_is_wednesday():
    assert cal.add_trading_days(D(2026, 10, 30), 3, set()) == D(2026, 11, 4)


def test_skips_weekday_holiday():
    # 2026-10-09 한글날(금)
    hol = {D(2026, 10, 9)}
    assert cal.add_trading_days(D(2026, 10, 7), 3, hol) == D(2026, 10, 13)


def test_seollal_block_from_kr_calendar():
    # 2026 설 연휴 2/16(월)~2/18(수). 2/13(금) + 3거래일 = 2/23(월)
    hol = cal.kr_holidays([2026])
    assert {D(2026, 2, 16), D(2026, 2, 17), D(2026, 2, 18)} <= hol
    assert cal.add_trading_days(D(2026, 2, 13), 3, hol) == D(2026, 2, 23)


def test_year_boundary():
    hol = cal.kr_holidays([2026, 2027])  # 2027-01-01(금) 신정
    assert cal.add_trading_days(D(2026, 12, 30), 3, hol) == D(2027, 1, 5)


def test_calendar_days_until():
    assert cal.calendar_days_until(D(2026, 10, 30), 3, set()) == 5
    assert cal.calendar_days_until(D(2026, 2, 13), 3, cal.kr_holidays([2026])) == 10


def test_calendar_days_uses_holiday_calendar_only():
    # 누수 방지: 남은 달력일 수는 공휴일 달력만 입력으로 받는다 (가격·거래 데이터 인자 없음)
    params = list(inspect.signature(cal.calendar_days_until).parameters)
    assert params == ["origin", "n", "holidays"]


def test_observed_target_counts_actual_trading_days():
    # 과거 거래일 = 평균 행이 있는 날. 토요일 거래(10/31)도 거래일로 센다.
    days = [D(2026, 10, 29), D(2026, 10, 30), D(2026, 10, 31), D(2026, 11, 2), D(2026, 11, 3)]
    assert cal.observed_target(days, D(2026, 10, 29), 3) == D(2026, 11, 2)
    assert cal.observed_target(days, D(2026, 11, 2), 3) is None
