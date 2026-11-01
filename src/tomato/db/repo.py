"""PostgreSQL 접근. ORM 없이 SQL을 직접 쓴다."""
import json
from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb

SCHEMA = Path(__file__).with_name("schema.sql")


def connect(url):
    return psycopg.connect(url, autocommit=True)


def init_db(conn):
    conn.execute(SCHEMA.read_text())


# --- ingest_run ---------------------------------------------------------

def start_run(conn, job):
    return conn.execute(
        "INSERT INTO ingest_run (job, status, attempts) VALUES (%s, 'running', 0) RETURNING id", (job,)
    ).fetchone()[0]


def finish_run(conn, run_id, status, attempts, rows_upserted=None, error=None):
    conn.execute(
        "UPDATE ingest_run SET finished_at = now(), status = %s, attempts = %s, rows_upserted = %s, error = %s"
        " WHERE id = %s",
        (status, attempts, rows_upserted, error, run_id),
    )


# --- price_raw ----------------------------------------------------------

PRICE_COLS = ("market_type", "item_code", "kind_code", "rank_code", "county", "market", "trade_date", "price", "unit")


def upsert_prices(conn, rows, run_id):
    if not rows:
        return 0
    sql = (
        f"INSERT INTO price_raw ({', '.join(PRICE_COLS)}, ingest_run_id) VALUES ({', '.join(['%s'] * len(PRICE_COLS))}, %s)"
        " ON CONFLICT (market_type, item_code, kind_code, rank_code, county, market, trade_date)"
        " DO UPDATE SET price = EXCLUDED.price, unit = EXCLUDED.unit, fetched_at = now(),"
        " ingest_run_id = EXCLUDED.ingest_run_id"
    )
    with conn.transaction(), conn.cursor() as cur:
        cur.executemany(sql, [tuple(r[c] for c in PRICE_COLS) + (run_id,) for r in rows])
    return len(rows)


def wholesale_series(conn, rank="04", since="2002-11-01"):
    """[(trade_date, avg_price, n_markets)] 평균가가 있는 거래일만, 날짜순."""
    return conn.execute(
        "SELECT trade_date, avg_price, n_markets FROM wholesale_daily"
        " WHERE rank_code = %s AND trade_date >= %s AND avg_price IS NOT NULL ORDER BY trade_date",
        (rank, since),
    ).fetchall()


# --- model / forecast / metric / explanation ----------------------------

def model_version_id(conn, name, params):
    row = conn.execute(
        "SELECT id FROM model_version WHERE name = %s AND params = %s ORDER BY id LIMIT 1", (name, Jsonb(params))
    ).fetchone()
    if row:
        return row[0]
    return conn.execute(
        "INSERT INTO model_version (name, params) VALUES (%s, %s) RETURNING id", (name, Jsonb(params))
    ).fetchone()[0]


FORECAST_COLS = ("model_version_id", "experiment", "origin_date", "horizon_tdays", "target_date_est",
                 "y_origin", "y_hat", "change_pct", "direction", "is_backtest")


def upsert_forecasts(conn, rows):
    sql = (
        f"INSERT INTO forecast ({', '.join(FORECAST_COLS)}) VALUES ({', '.join(['%s'] * len(FORECAST_COLS))})"
        " ON CONFLICT (model_version_id, experiment, origin_date, horizon_tdays, is_backtest)"
        " DO UPDATE SET target_date_est = EXCLUDED.target_date_est, y_origin = EXCLUDED.y_origin,"
        " y_hat = EXCLUDED.y_hat, change_pct = EXCLUDED.change_pct, direction = EXCLUDED.direction,"
        " created_at = now() RETURNING id"
    )
    ids = []
    with conn.transaction(), conn.cursor() as cur:
        for r in rows:
            cur.execute(sql, tuple(r[c] for c in FORECAST_COLS))
            ids.append(cur.fetchone()[0])
    return ids


def replace_metrics(conn, experiment, model_name, rows):
    with conn.transaction():
        conn.execute("DELETE FROM backtest_metric WHERE experiment = %s AND model_name = %s", (experiment, model_name))
        for r in rows:
            conn.execute(
                "INSERT INTO backtest_metric (experiment, model_name, segment, metric, value, n)"
                " VALUES (%s, %s, %s, %s, %s, %s)",
                (experiment, model_name, r["segment"], r["metric"], r["value"], r["n"]),
            )


def metrics_for(conn, model_name, experiment="window=full", segment="test_all"):
    rows = conn.execute(
        "SELECT metric, value, n FROM backtest_metric WHERE model_name = %s AND experiment = %s AND segment = %s",
        (model_name, experiment, segment),
    ).fetchall()
    return {m: (float(v), n) for m, v, n in rows}


_FORECAST_SELECT = (
    "SELECT f.id, mv.name, f.origin_date, f.horizon_tdays, f.target_date_est, f.y_origin, f.y_hat,"
    " f.change_pct, f.direction FROM forecast f JOIN model_version mv ON mv.id = f.model_version_id"
)
_FORECAST_KEYS = ("id", "model", "origin_date", "horizon_tdays", "target_date_est", "y_origin", "y_hat",
                  "change_pct", "direction")


def latest_forecast(conn):
    row = conn.execute(
        _FORECAST_SELECT + " WHERE NOT f.is_backtest AND f.experiment = 'live'"
        " ORDER BY f.origin_date DESC, f.id DESC LIMIT 1"
    ).fetchone()
    return dict(zip(_FORECAST_KEYS, row)) if row else None


def forecast_by_id(conn, forecast_id):
    row = conn.execute(_FORECAST_SELECT + " WHERE f.id = %s", (forecast_id,)).fetchone()
    return dict(zip(_FORECAST_KEYS, row)) if row else None


def insert_explanation(conn, forecast_id, provider, model, input_, text, grounded):
    return conn.execute(
        "INSERT INTO explanation (forecast_id, provider, model, input, output_text, grounded)"
        " VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
        (forecast_id, provider, model, Jsonb(json.loads(json.dumps(input_, default=str))), text, grounded),
    ).fetchone()[0]


def latest_explanation(conn, forecast_id):
    row = conn.execute(
        "SELECT output_text, provider, grounded FROM explanation WHERE forecast_id = %s ORDER BY id DESC LIMIT 1",
        (forecast_id,),
    ).fetchone()
    return dict(zip(("text", "provider", "grounded"), row)) if row else None
