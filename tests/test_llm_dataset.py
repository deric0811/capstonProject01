"""LLM 제공자 설정 분리와 증류 입력의 누수 검사 (spec §6, §6.1)."""
import datetime as dt

import pytest

from test_features import make_daily
from tomato import calendar as cal
from tomato.explain import dataset, llm


def test_template_is_default_and_api_needs_key(monkeypatch):
    monkeypatch.setattr(llm, "_local_alive", lambda s: False)
    assert llm.resolve({}) is None
    assert llm.resolve({"LLM_PROVIDER": "auto"}) is None  # GPU 서버도 키도 없으면 템플릿
    s = llm.resolve({"LLM_PROVIDER": "auto", "LLM_API_KEY": "k-secret"})
    assert s.provider == "api" and "generativelanguage" in s.base_url
    assert "k-secret" not in repr(s)


def test_auto_prefers_local_gpu_server(monkeypatch):
    monkeypatch.setattr(llm, "_local_alive", lambda s: True)
    s = llm.resolve({"LLM_PROVIDER": "auto", "LLM_API_KEY": "k", "LLM_LOCAL_BASE_URL": "http://gpu:9000/v1/"})
    assert s.provider == "local" and s.base_url == "http://gpu:9000/v1"
    assert s.extra == {"chat_template_kwargs": {"skip_reasoning": True}}  # 사고 출력 끔
    assert s.api_key == ""  # 사용자 키를 로컬 서버로 보내지 않는다


def test_unknown_provider_fails():
    with pytest.raises(ValueError):
        llm.resolve({"LLM_PROVIDER": "openai"})


def test_split_is_by_time():
    assert dataset.split_of(dt.date(2002, 12, 31)) is None
    assert dataset.split_of(dt.date(2003, 1, 2)) == "train"
    assert dataset.split_of(dt.date(2021, 12, 31)) == "train"
    assert dataset.split_of(dt.date(2022, 1, 3)) == "val"
    assert dataset.split_of(dt.date(2023, 1, 2)) == "eval"


def test_record_uses_only_rows_up_to_t():
    daily = make_daily(700)
    i = 600
    holidays = cal.kr_holidays(range(2019, 2023))
    perf = {"mae": 1412, "mape": 6.3, "n": 934, "mae_reduction_pct": 9.1}
    changed = daily[: i + 1] + [r._replace(price=r.price * 3, n_markets=1) for r in daily[i + 1 :]]
    a = dataset.record(daily, i, 12345, perf, holidays)
    b = dataset.record(changed, i, 12345, perf, holidays)
    assert a == b
    x = a["input"]
    assert x["origin_date"] == daily[i].date.isoformat() and x["y_origin"] == daily[i].price
    assert x["horizon_tdays"] == 3 and x["model"] == "chronos2" and x["y_hat"] == 12345
    # 입력 어디에도 t 이후 실제 가격이 없다 (예상 날짜는 달력 추정)
    assert x["target_date_est"] == cal.add_trading_days(daily[i].date, 3, holidays).isoformat()
