"""운영 예측의 대체 경로: Chronos-2가 실패하면 LightGBM full로 예측하고 model_version도 lgbm으로 기록된다."""
import datetime as dt

import numpy as np
import pytest

from test_features import make_daily
from tomato import cli
from tomato.models import chronos2

DAILY = make_daily(300)


@pytest.fixture
def fake_repo(monkeypatch):
    calls = {}

    def model_version_id(conn, name, params):
        calls["mv"] = (name, params)
        return 900

    monkeypatch.setattr(cli.repo, "model_version_id", model_version_id)
    monkeypatch.setattr(cli, "_lgbm_forecast", lambda conn, daily, h: (700, "lgbm", 12345))
    return calls


def test_chronos_load_failure_falls_back_to_lgbm(fake_repo, monkeypatch, capsys):
    def boom():
        raise OSError("가중치 없음")

    monkeypatch.setattr(chronos2, "load_pipeline", boom)
    cache = {}
    for h in (3, 7):
        assert cli.forecast_one(None, DAILY, h, "chronos2", cache) == (700, "lgbm", 12345)
    err = capsys.readouterr().err
    assert err.count("Chronos-2 실패, LightGBM full로 대체: OSError: 가중치 없음") == 2
    assert isinstance(cache["error"], OSError)  # 두 번째 h에서는 다시 로드하지 않는다


def test_chronos_predict_failure_falls_back_to_lgbm(fake_repo, monkeypatch, capsys):
    class Broken:
        def predict_quantiles(self, *a, **k):
            raise RuntimeError("예측 실패")

    monkeypatch.setattr(chronos2, "load_pipeline", lambda: Broken())
    assert cli.forecast_one(None, DAILY, 3, "chronos2", {})[:2] == (700, "lgbm")
    assert "RuntimeError: 예측 실패" in capsys.readouterr().err


def test_chronos_success_records_chronos_model_version(fake_repo, monkeypatch):
    class Pipe:
        def predict_quantiles(self, inputs, prediction_length, **k):
            return [np.arange(1, prediction_length + 1, dtype=float).reshape(1, -1, 1) * 1000 for _ in inputs], None

    monkeypatch.setattr(chronos2, "load_pipeline", lambda: Pipe())
    mv, name, y_hat = cli.forecast_one(None, DAILY, 7, "chronos2", {})
    assert (mv, name, y_hat) == (900, "chronos2", 7000)  # 7번째 스텝
    assert fake_repo["mv"] == ("chronos2", {"horizon": 7, "input": "target", "revision": chronos2.REVISION})


def test_ops_models_are_chronos_for_3_and_7_only():
    assert cli.OPS_MODELS == {3: "chronos2", 7: "chronos2"}
    assert cli.model_label("chronos2", 3) == "Chronos-2 (zero-shot)"
    assert cli.metric_experiment("chronos2", 3) == "input=target"
