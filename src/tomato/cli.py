"""tomato CLI (spec §9). 1단계 명령: db init, collect, predict, backtest(B1), explain, show latest."""
import argparse
import datetime as dt
import sys

from tomato import calendar as cal
from tomato.collectors import kamis
from tomato.config import load_settings
from tomato.db import repo
from tomato.evaluation import metrics, walkforward
from tomato.explain import template
from tomato.models import baselines

YEAR_ROUND_FROM = dt.date(2002, 11, 1)


def cmd_db_init(conn, args):
    repo.init_db(conn)
    print("schema 적용 완료")


def _collect(conn, settings, job, start, end):
    run_id = repo.start_run(conn, job)
    try:
        rows, attempts = kamis.collect(settings, start, end)
        n = repo.upsert_prices(conn, rows, run_id)
    except kamis.FetchError as e:
        repo.finish_run(conn, run_id, "failed", e.attempts, error=str(e))
        print(f"수집 실패 (ingest_run {run_id}, {e.attempts}회 시도): {e}", file=sys.stderr)
        return 1
    except Exception as e:  # noqa: BLE001 - DB 오류 등도 실패로 기록한다
        repo.finish_run(conn, run_id, "failed", 1, error=f"{type(e).__name__}: {e}")
        raise
    repo.finish_run(conn, run_id, "ok", attempts, rows_upserted=n)
    print(f"{job}: {start} ~ {end}, {n}행 upsert (ingest_run {run_id}, 최대 {attempts}회 시도)")
    return 0


def cmd_collect_backfill(conn, args):
    return _collect(conn, args.settings, "backfill", args.start, args.to)


def cmd_collect_daily(conn, args):
    end = dt.date.today()
    return _collect(conn, args.settings, "daily", end - dt.timedelta(days=args.days - 1), end)


def _series(conn):
    rows = repo.wholesale_series(conn, since=YEAR_ROUND_FROM)
    if not rows:
        sys.exit("wholesale_daily가 비어 있습니다. 먼저 collect backfill을 실행하세요.")
    return rows


def cmd_predict(conn, args):
    rows = _series(conn)
    if args.origin:
        rows = [r for r in rows if r[0] <= args.origin]
        if not rows or rows[-1][0] != args.origin:
            sys.exit(f"{args.origin}은 거래일(평균가 있는 날)이 아닙니다.")
    t, y0 = rows[-1][0], rows[-1][1]
    y_hat = round(baselines.b1([p for _, p, _ in rows]))
    r = metrics.change(y0, y_hat)
    target = cal.add_trading_days(t, walkforward.HORIZON, cal.kr_holidays([t.year, t.year + 1]))
    mv = repo.model_version_id(conn, "B1", {})
    [fid] = repo.upsert_forecasts(conn, [{
        "model_version_id": mv, "experiment": "live", "origin_date": t, "horizon_tdays": walkforward.HORIZON,
        "target_date_est": target, "y_origin": y0, "y_hat": y_hat, "change_pct": round(100 * r, 3),
        "direction": metrics.direction(r), "is_backtest": False,
    }])
    print(f"forecast {fid}: B1, t={t} y={y0:,} → {walkforward.HORIZON}거래일 후({target} 예상) {y_hat:,}")


def cmd_backtest(conn, args):
    names = args.models.split(",")
    unknown = [n for n in names if n not in baselines.MODELS]
    if unknown:
        sys.exit(f"1단계에서는 {', '.join(baselines.MODELS)}만 지원합니다: {unknown}")
    series = [(d, p) for d, p, _ in _series(conn)]
    b1_rows = walkforward.backtest(series, baselines.b1)
    experiment = "window=full"
    for name in names:
        rows = walkforward.backtest(series, baselines.MODELS[name])
        mv = repo.model_version_id(conn, name, {})
        repo.upsert_forecasts(conn, [{
            "model_version_id": mv, "experiment": experiment, "origin_date": r["origin_date"],
            "horizon_tdays": walkforward.HORIZON, "target_date_est": r["target_date"], "y_origin": r["y0"],
            "y_hat": r["y_hat"], "change_pct": round(100 * metrics.change(r["y0"], r["y_hat"]), 3),
            "direction": metrics.direction(metrics.change(r["y0"], r["y_hat"])), "is_backtest": True,
        } for r in rows])
        out = []
        b1_seg = walkforward.segments(b1_rows)
        for seg, seg_rows in walkforward.segments(rows).items():
            out += [{**m, "segment": seg} for m in walkforward.score(seg_rows, b1_seg[seg])]
        repo.replace_metrics(conn, experiment, name, out)
        print(f"\n{name} ({experiment}, 예측 시점 {rows[0]['origin_date']} ~ {rows[-1]['origin_date']})")
        print(f"{'segment':<9} {'metric':<11} {'value':>12} {'n':>6}")
        for m in out:
            print(f"{m['segment']:<9} {m['metric']:<11} {m['value']:>12.4f} {m['n']:>6}")


def _perf(conn, model):
    m = repo.metrics_for(conn, model)
    return {"mae": round(m["mae"][0]), "mape": round(m["mape"][0], 1)} if "mae" in m else None


def cmd_explain(conn, args):
    f = repo.forecast_by_id(conn, args.forecast_id) if args.forecast_id else repo.latest_forecast(conn)
    if not f:
        sys.exit("forecast가 없습니다. 먼저 predict를 실행하세요.")
    x = template.build_input(_series(conn), f, _perf(conn, f["model"]))
    text = template.render(x)
    eid = repo.insert_explanation(conn, f["id"], template.PROVIDER, template.MODEL, x, text, True)
    print(f"explanation {eid} (forecast {f['id']}, template):\n{text}")


def cmd_show_latest(conn, args):
    f = repo.latest_forecast(conn)
    if not f:
        sys.exit("forecast가 없습니다.")
    print(f"현재가 {f['origin_date']}: {f['y_origin']:,}원 / 5kg")
    print(f"{f['horizon_tdays']}거래일 후({f['target_date_est']} 예상): {f['y_hat']:,}원 [{f['model']}]")
    e = repo.latest_explanation(conn, f["id"])
    print(e["text"] if e else "(설명 없음: explain 실행 필요)")


def build_parser():
    date = dt.date.fromisoformat
    ap = argparse.ArgumentParser(prog="tomato")
    sub = ap.add_subparsers(required=True)

    db = sub.add_parser("db").add_subparsers(required=True)
    db.add_parser("init").set_defaults(fn=cmd_db_init)

    co = sub.add_parser("collect").add_subparsers(required=True)
    bf = co.add_parser("backfill")
    bf.add_argument("--market", choices=["wholesale"], default="wholesale")
    bf.add_argument("--from", dest="start", type=date, default=YEAR_ROUND_FROM)
    bf.add_argument("--to", type=date, default=dt.date.today() - dt.timedelta(days=1))
    bf.set_defaults(fn=cmd_collect_backfill)
    dy = co.add_parser("daily")
    dy.add_argument("--days", type=int, default=7)
    dy.set_defaults(fn=cmd_collect_daily)

    pr = sub.add_parser("predict")
    pr.add_argument("--origin", type=date)
    pr.set_defaults(fn=cmd_predict)

    bt = sub.add_parser("backtest")
    bt.add_argument("--models", default="B1")
    bt.set_defaults(fn=cmd_backtest)

    ex = sub.add_parser("explain")
    ex.add_argument("--forecast-id", type=int)
    ex.set_defaults(fn=cmd_explain)

    sh = sub.add_parser("show").add_subparsers(required=True)
    sh.add_parser("latest").set_defaults(fn=cmd_show_latest)
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    args.settings = load_settings()
    with repo.connect(args.settings.database_url) as conn:
        return args.fn(conn, args) or 0


if __name__ == "__main__":
    sys.exit(main())
