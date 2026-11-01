import datetime as dt
import re

from tomato.explain import template

D = dt.date
SERIES = [(D(2025, 11, 3) + dt.timedelta(days=i), 20000 + 100 * i, 5) for i in range(25)]
SERIES[-1] = (SERIES[-1][0], SERIES[-1][1], 4)  # 마지막 날 시장 1곳 빠짐
F = {"id": 1, "model": "B1", "origin_date": SERIES[-1][0], "horizon_tdays": 3, "target_date_est": D(2025, 12, 2),
     "y_origin": SERIES[-1][1], "y_hat": SERIES[-1][1], "change_pct": 0, "direction": "flat"}


def _numbers(text):
    return {n.replace(",", "") for n in re.findall(r"\d[\d,]*\.?\d*", text)}


def _flatten(x):
    if isinstance(x, dict):
        for v in x.values():
            yield from _flatten(v)
    elif x is not None:
        yield str(x)


def test_render_uses_only_input_numbers():
    x = template.build_input(SERIES, F, {"mae": 1234, "mape": 6.5})
    text = template.render(x)
    allowed = set()
    for v in _flatten(x):
        allowed |= _numbers(v) | {v.lstrip("+-")}
    allowed |= {"20", "2023", "5"}  # 고정 문구: 최근 20거래일, 2023년 이후, 5kg
    assert _numbers(text) <= allowed, _numbers(text) - allowed
    assert "틀릴 수 있" in text and "4곳" in text and "1,234원" in text


def test_seasonal_uses_only_past_months():
    x = template.build_input(SERIES, F)
    assert x["seasonal"]["median"] is None  # 같은 달의 과거 해 데이터 없음
    assert x["trend20"]["start_date"] == SERIES[-21][0].isoformat()
