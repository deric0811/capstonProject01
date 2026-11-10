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


def wholesale_feature_rows(conn, since="2002-11-01"):
    """[(trade_date, 상품 평균가, 참여 시장 수, 중품 평균가, 상품 시장별 최댓값−최솟값)] 상품 평균가가 있는 거래일만, 날짜순."""
    return conn.execute(
        """
        SELECT a.trade_date, a.avg_price, a.n_markets, m.avg_price, s.spread
        FROM wholesale_daily a
        LEFT JOIN wholesale_daily m ON m.trade_date = a.trade_date AND m.rank_code = '05'
        LEFT JOIN (
          SELECT trade_date, max(price) - min(price) AS spread FROM price_raw
          WHERE market_type = 'wholesale' AND item_code = '225' AND kind_code = '00'
            AND rank_code = '04' AND county <> '평균' AND price IS NOT NULL
          GROUP BY trade_date
        ) s ON s.trade_date = a.trade_date
        WHERE a.rank_code = '04' AND a.trade_date >= %s AND a.avg_price IS NOT NULL
        ORDER BY a.trade_date
        """,
        (since,),
    ).fetchall()


# --- model / forecast / metric / explanation ----------------------------

def model_version_id(conn, name, params):
    """backtest·기준선용 model_version. 학습 파일이 있는 행(train)은 쓰지 않는다."""
    row = conn.execute(
        "SELECT id FROM model_version WHERE name = %s AND params = %s AND artifact_path IS NULL ORDER BY id LIMIT 1",
        (name, Jsonb(params)),
    ).fetchone()
    if row:
        return row[0]
    return conn.execute(
        "INSERT INTO model_version (name, params) VALUES (%s, %s) RETURNING id", (name, Jsonb(params))
    ).fetchone()[0]


def insert_trained_model(conn, name, params, train_start, train_end, artifact_path):
    return conn.execute(
        "INSERT INTO model_version (name, params, train_start, train_end, artifact_path)"
        " VALUES (%s, %s, %s, %s, %s) RETURNING id",
        (name, Jsonb(params), train_start, train_end, artifact_path),
    ).fetchone()[0]


def latest_trained_model(conn, name, horizon):
    """{'id', 'params', 'train_end', 'artifact_path'} 또는 None."""
    row = conn.execute(
        "SELECT id, params, train_end, artifact_path FROM model_version"
        " WHERE name = %s AND artifact_path IS NOT NULL AND (params->>'horizon')::int = %s ORDER BY id DESC LIMIT 1",
        (name, horizon),
    ).fetchone()
    return dict(zip(("id", "params", "train_end", "artifact_path"), row)) if row else None


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


def replace_metrics(conn, experiment, model_name, rows, horizon=3):
    with conn.transaction():
        conn.execute(
            "DELETE FROM backtest_metric WHERE experiment = %s AND model_name = %s AND horizon_tdays = %s",
            (experiment, model_name, horizon),
        )
        for r in rows:
            conn.execute(
                "INSERT INTO backtest_metric (experiment, horizon_tdays, model_name, segment, metric, value, n)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (experiment, horizon, model_name, r["segment"], r["metric"], r["value"], r["n"]),
            )


def metrics_for(conn, model_name, experiment="window=full", segment="test_all", horizon=3):
    rows = conn.execute(
        "SELECT metric, value, n FROM backtest_metric"
        " WHERE model_name = %s AND experiment = %s AND segment = %s AND horizon_tdays = %s",
        (model_name, experiment, segment, horizon),
    ).fetchall()
    return {m: (float(v), n) for m, v, n in rows}


_FORECAST_SELECT = (
    "SELECT f.id, mv.name, f.origin_date, f.horizon_tdays, f.target_date_est, f.y_origin, f.y_hat,"
    " f.change_pct, f.direction FROM forecast f JOIN model_version mv ON mv.id = f.model_version_id"
)
_FORECAST_KEYS = ("id", "model", "origin_date", "horizon_tdays", "target_date_est", "y_origin", "y_hat",
                  "change_pct", "direction")


def latest_forecast(conn, horizon=3):
    """대시보드·설명용 최신 예측. 기본은 h = 3."""
    row = conn.execute(
        _FORECAST_SELECT + " WHERE NOT f.is_backtest AND f.experiment = 'live' AND f.horizon_tdays = %s"
        " ORDER BY f.origin_date DESC, f.created_at DESC, f.id DESC LIMIT 1",  # upsert는 id를 유지하고 created_at을 갱신한다
        (horizon,),
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
