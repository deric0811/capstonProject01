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
