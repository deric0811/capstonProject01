"""tomato CLI (spec §9). db init, collect, train, predict, backtest, explain, show latest."""
import argparse
import datetime as dt
import sys
from pathlib import Path

import lightgbm as lgb

from tomato import calendar as cal
from tomato import features
from tomato.collectors import kamis
from tomato.config import load_settings
from tomato.db import repo
from tomato.evaluation import metrics, selection, walkforward
from tomato.explain import template
from tomato.models import baselines, lgbm

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


MODEL_LABELS = {"B1": "직전가(B1)", "B2": "최근 5거래일 평균(B2)", "lgbm": "LightGBM"}


def metric_experiment(model, horizon):
    """대시보드·설명에 쓸 backtest 지표의 실험 이름. LightGBM은 검증에서 고른 학습 창."""
    return f"window={lgbm.selected(horizon)[0]}" if model == "lgbm" else "window=full"


def _series(conn):
    rows = repo.wholesale_series(conn, since=YEAR_ROUND_FROM)
    if not rows:
        sys.exit("wholesale_daily가 비어 있습니다. 먼저 collect backfill을 실행하세요.")
    return rows


def _daily(conn, to=None):
    daily = [features.Daily(*r) for r in repo.wholesale_feature_rows(conn, since=YEAR_ROUND_FROM)]
    if not daily:
        sys.exit("wholesale_daily가 비어 있습니다. 먼저 collect backfill을 실행하세요.")
    return [r for r in daily if r.date <= to] if to else daily


def _horizons(text):
    return [int(x) for x in text.split(",")]


def cmd_train(conn, args):
    daily = _daily(conn)
    lgbm.ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    for h in _horizons(args.horizons):
        window, params = lgbm.selected(h)
        booster, start = lgbm.train_final(daily, h, params, window)
        path = lgbm.ARTIFACT_DIR / f"lgbm_h{h}_{window}_{daily[-1].date}.txt"
        booster.save_model(str(path))
        mv = repo.insert_trained_model(conn, "lgbm", {"horizon": h, "window": window, **params}, start,
                                       daily[-1].date, str(path))
        print(f"model_version {mv}: lgbm h={h} window={window}, 학습 {start} ~ {daily[-1].date}, {path}")


def cmd_predict(conn, args):
    daily = _daily(conn, args.origin)
    if args.origin and daily[-1].date != args.origin:
        sys.exit(f"{args.origin}은 거래일(평균가 있는 날)이 아닙니다.")
    t, y0 = daily[-1].date, daily[-1].price
    holidays = cal.kr_holidays([t.year, t.year + 1])
    rows = []
    for h in _horizons(args.horizons):
        if args.model == "lgbm":
            mv = repo.latest_trained_model(conn, "lgbm", h)
            if not mv:
                sys.exit(f"h={h} 학습 모델이 없습니다. 먼저 tomato train --model lgbm을 실행하세요.")
            if t < mv["train_end"]:
                sys.exit(f"예측 시점 {t}이 학습 데이터 끝 {mv['train_end']}보다 앞섭니다(미래 라벨 사용).")
            if not Path(mv["artifact_path"]).exists():
                sys.exit(f"모델 파일이 없습니다: {mv['artifact_path']}. tomato train을 다시 실행하세요.")
            y_hat = lgbm.predict_last(lgb.Booster(model_file=mv["artifact_path"]), daily, h)
            mv_id = mv["id"]
        else:
            y_hat = round(baselines.MODELS[args.model]([r.price for r in daily]))
            mv_id = repo.model_version_id(conn, args.model, {})
        r = metrics.change(y0, y_hat)
        rows.append({
            "model_version_id": mv_id, "experiment": "live", "origin_date": t, "horizon_tdays": h,
            "target_date_est": cal.add_trading_days(t, h, holidays), "y_origin": y0, "y_hat": y_hat,
            "change_pct": round(100 * r, 3), "direction": metrics.direction(r), "is_backtest": False,
        })
    for fid, row in zip(repo.upsert_forecasts(conn, rows), rows, strict=True):
        print(f"forecast {fid}: {args.model}, t={t} y={y0:,} → {row['horizon_tdays']}거래일 후"
              f"({row['target_date_est']} 예상) {row['y_hat']:,} ({row['change_pct']:+.1f}%, {row['direction']})")


def _save_backtest(conn, name, params, experiment, horizon, rows, b1_rows):
    mv = repo.model_version_id(conn, name, params)
    repo.upsert_forecasts(conn, [{
        "model_version_id": mv, "experiment": experiment, "origin_date": r["origin_date"],
        "horizon_tdays": horizon, "target_date_est": r["target_date"], "y_origin": r["y0"],
        "y_hat": r["y_hat"], "change_pct": round(100 * metrics.change(r["y0"], r["y_hat"]), 3),
        "direction": metrics.direction(metrics.change(r["y0"], r["y_hat"])), "is_backtest": True,
    } for r in rows])
    out = {}
    b1_seg = walkforward.segments(b1_rows)
    for seg, seg_rows in walkforward.segments(rows).items():
        out[seg] = {m["metric"]: m for m in walkforward.score(seg_rows, b1_seg[seg])}
    repo.replace_metrics(conn, experiment, name, [{**m, "segment": s} for s, ms in out.items() for m in ms.values()],
                         horizon)
    return out


def _print_table(results):
    print(f"{'segment':<9} {'model':<10} {'MAE':>8} {'상대MAE':>7} {'MAPE':>6} {'상하적중':>7} {'3분류':>6} {'절감액(A-B)':>13} {'절감%':>6} {'n':>5}")
    for seg in ("test_all", "spike"):
        for name, res in results.items():
            m = res[seg]
            print(f"{seg:<9} {name:<10} {m['mae']['value']:>8.1f} {m['rel_mae']['value']:>7.4f}"
                  f" {m['mape']['value']:>6.2f} {100 * m['dir_acc_ud']['value']:>7.1f}"
                  f" {100 * m['dir_acc3']['value']:>6.1f} {-m['sim_diff_won']['value']:>13,.0f}"
                  f" {-m['sim_diff_pct']['value']:>6.2f} {m['mae']['n']:>5}")


def cmd_backtest(conn, args):
    names = args.models.split(",")
    known = (*baselines.MODELS, "lgbm")
    unknown = [n for n in names if n not in known]
    if unknown:
        sys.exit(f"지원 모델은 {', '.join(known)}입니다: {unknown}")
    daily = _daily(conn, args.to)
    series = [(r.date, r.price) for r in daily]
    tuned = lgbm.load_params() if "lgbm" in names else None
    print(f"데이터 {daily[0].date} ~ {daily[-1].date}, {len(daily)}거래일")

    for h in _horizons(args.horizons):
        b1_rows = walkforward.backtest(series, baselines.b1, horizon=h)
        all_rows, results = {}, {}
        for name in names:
            if name == "lgbm":
                for w in args.window.split(","):
                    params = tuned[str(h)][w]["params"]
                    all_rows[f"lgbm-{w}"] = (lgbm.backtest(daily, h, params, w), f"window={w}", {"horizon": h, "window": w, **params})
            else:
                all_rows[name] = (walkforward.backtest(series, baselines.MODELS[name], horizon=h), "window=full", {})
        walkforward.assert_same_origins({"B1": b1_rows, **{k: v[0] for k, v in all_rows.items()}})
        for label, (rows, experiment, params) in all_rows.items():
            results[label] = _save_backtest(conn, label.split("-")[0], params, experiment, h, rows, b1_rows)
        print(f"\n=== h={h}, 예측 시점 {b1_rows[0]['origin_date']} ~ {b1_rows[-1]['origin_date']}, {len(b1_rows)}회 ===")
        _print_table(results)
        if tuned and "B2" in results:
            window = tuned[str(h)]["selected_window"]
            cand = {"B2": results["B2"], f"lgbm-{window}": results[f"lgbm-{window}"]}
            chosen, reasons = selection.select(
                {k: {x: v["test_all"][x]["value"] for x in ("mae", "rel_mae", "dir_acc_ud")} for k, v in cand.items()}
            )
            print(f"선택 (h={h}, 검증에서 고른 창 {window}): {chosen}")
            for reason in reasons:
                print(f"  - {reason}")


def performance(conn, model, horizon=3):
    """설명·대시보드의 성능 한 줄 입력. B1 대비 MAE 감소율은 B1이 아닐 때만."""
    m = repo.metrics_for(conn, model, metric_experiment(model, horizon), horizon=horizon)
    if "mae" not in m:
        return None
    out = {"mae": round(m["mae"][0]), "mape": round(m["mape"][0], 1), "n": m["mae"][1]}
    if model != "B1" and "rel_mae" in m:
        out["mae_reduction_pct"] = round(100 * (1 - m["rel_mae"][0]), 1)
    return out


def cmd_explain(conn, args):
    f = repo.forecast_by_id(conn, args.forecast_id) if args.forecast_id else repo.latest_forecast(conn)
    if not f:
        sys.exit("forecast가 없습니다. 먼저 predict를 실행하세요.")
    x = template.build_input(_series(conn), f, performance(conn, f["model"], f["horizon_tdays"]))
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

    tr = sub.add_parser("train")
    tr.add_argument("--model", choices=["lgbm"], default="lgbm")
    tr.add_argument("--horizons", default="3,7")
    tr.set_defaults(fn=cmd_train)

    pr = sub.add_parser("predict")
    pr.add_argument("--origin", type=date)
    pr.add_argument("--model", choices=["lgbm", "B1", "B2"], default="lgbm")
    pr.add_argument("--horizons", default="3,7")
    pr.set_defaults(fn=cmd_predict)

    bt = sub.add_parser("backtest")
    bt.add_argument("--models", default="B1")
    bt.add_argument("--window", default="full,5y", help="full, 5y 또는 full,5y")
    bt.add_argument("--horizons", default="3,7")
    bt.add_argument("--to", type=date, help="이 날짜까지의 데이터만 쓴다 (결과 재현용)")
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
