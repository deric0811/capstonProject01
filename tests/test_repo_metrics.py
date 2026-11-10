"""h별 지표 저장. TEST_DATABASE_URL이 없으면 건너뛴다."""
import os

import pytest

from tomato.db import repo

URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="TEST_DATABASE_URL 없음")
EXP = "test-replace-metrics"


@pytest.fixture
def conn():
    with repo.connect(URL) as c:
        repo.init_db(c)
        c.execute("DELETE FROM backtest_metric WHERE experiment = %s", (EXP,))
        yield c
        c.execute("DELETE FROM backtest_metric WHERE experiment = %s", (EXP,))


def row(v):
    return {"segment": "test_all", "metric": "mae", "value": v, "n": 1}


def test_h7_does_not_overwrite_h3(conn):
    repo.replace_metrics(conn, EXP, "B1", [row(3)], horizon=3)
    repo.replace_metrics(conn, EXP, "B1", [row(7)], horizon=7)
    assert repo.metrics_for(conn, "B1", EXP)["mae"][0] == 3  # 기본은 h = 3
    assert repo.metrics_for(conn, "B1", EXP, horizon=7)["mae"][0] == 7


def test_replace_same_horizon_replaces(conn):
    repo.replace_metrics(conn, EXP, "B1", [row(3)], horizon=3)
    repo.replace_metrics(conn, EXP, "B1", [row(4)], horizon=3)
    assert repo.metrics_for(conn, "B1", EXP)["mae"] == (4, 1)


def test_init_db_adds_column_to_existing_table_and_is_repeatable(conn):
    repo.init_db(conn)
    n = conn.execute(
        "SELECT count(*) FROM information_schema.columns WHERE table_name = 'backtest_metric' AND column_name = 'horizon_tdays'"
    ).fetchone()[0]
    assert n == 1


def test_latest_forecast_filters_horizon_and_trained_model_lookup(conn):
    import datetime as dt
    mv = repo.insert_trained_model(conn, "lgbm-test", {"horizon": 7}, dt.date(2002, 11, 1), dt.date(2099, 1, 1), "/x")
    assert repo.latest_trained_model(conn, "lgbm-test", 7)["id"] == mv
    assert repo.latest_trained_model(conn, "lgbm-test", 3) is None
    assert repo.model_version_id(conn, "lgbm-test", {"horizon": 7}) != mv  # backtest용은 학습 행을 쓰지 않는다
    base = {"model_version_id": mv, "experiment": "live", "origin_date": dt.date(2099, 1, 1), "y_origin": 1,
            "y_hat": 1, "change_pct": 0, "direction": "flat", "is_backtest": False,
            "target_date_est": dt.date(2099, 1, 5)}
    try:
        repo.upsert_forecasts(conn, [{**base, "horizon_tdays": 3}, {**base, "horizon_tdays": 7}])
        assert repo.latest_forecast(conn)["horizon_tdays"] == 3
        assert repo.latest_forecast(conn, horizon=7)["horizon_tdays"] == 7
    finally:
        conn.execute("DELETE FROM forecast WHERE model_version_id IN"
                     " (SELECT id FROM model_version WHERE name = 'lgbm-test')")
        conn.execute("DELETE FROM model_version WHERE name = 'lgbm-test'")


def test_latest_forecast_prefers_most_recent_run_on_same_origin(conn):
    """대체(LightGBM) 예측 뒤 같은 날 Chronos-2로 다시 예측하면 Chronos-2가 최신이어야 한다(upsert는 id 유지)."""
    import datetime as dt
    a = repo.insert_trained_model(conn, "lgbm-test", {"horizon": 3}, dt.date(2002, 11, 1), dt.date(2099, 1, 1), "/x")
    b = repo.model_version_id(conn, "chronos2-test", {"horizon": 3})
    row = {"experiment": "live", "origin_date": dt.date(2099, 2, 1), "horizon_tdays": 3, "y_origin": 1,
           "change_pct": 0, "direction": "flat", "is_backtest": False, "target_date_est": dt.date(2099, 2, 4)}
    try:
        [first] = repo.upsert_forecasts(conn, [{**row, "model_version_id": b, "y_hat": 1}])
        repo.upsert_forecasts(conn, [{**row, "model_version_id": a, "y_hat": 2}])  # 대체
        [again] = repo.upsert_forecasts(conn, [{**row, "model_version_id": b, "y_hat": 3}])  # 복구
        assert again == first
        latest = repo.latest_forecast(conn)
        assert (latest["model"], latest["y_hat"]) == ("chronos2-test", 3)
    finally:
        conn.execute("DELETE FROM forecast WHERE model_version_id IN"
                     " (SELECT id FROM model_version WHERE name IN ('lgbm-test', 'chronos2-test'))")
        conn.execute("DELETE FROM model_version WHERE name IN ('lgbm-test', 'chronos2-test')")
