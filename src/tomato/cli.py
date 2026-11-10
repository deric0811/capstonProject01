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
from tomato.evaluation import metrics, selection, simulation, walkforward
from tomato.explain import template
from tomato.models import baselines, chronos2, lgbm

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


MODEL_LABELS = {"B1": "직전가(B1)", "B2": "최근 5거래일 평균(B2)", "lgbm": "LightGBM", "chronos2": "Chronos-2"}


def metric_experiment(model, horizon):
    """대시보드·설명에 쓸 backtest 지표의 실험 이름. LightGBM은 검증에서 고른 학습 창, Chronos-2는 검증에서 고른 입력."""
    if model == "lgbm":
        return f"window={lgbm.selected(horizon)[0]}"
    if model == "chronos2":
        return f"input={chronos2.load_choice()[str(horizon)]['selected_input']}"
    return "window=full"


def model_label(model, horizon):
    label = MODEL_LABELS.get(model, model)
    if model == "lgbm":
        return f"{label} (학습 창 {lgbm.selected(horizon)[0]})"
    if model == "chronos2":
        return f"{label} (zero-shot)"
    return label


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


OPS_MODELS = {3: "chronos2", 7: "chronos2"}  # 운영 모델 (docs/decisions.md 2026-11-10). 실패하면 LightGBM full


def _lgbm_forecast(conn, daily, h):
    t = daily[-1].date
    mv = repo.latest_trained_model(conn, "lgbm", h)
    if not mv:
        raise RuntimeError(f"h={h} 학습 모델이 없습니다. 먼저 tomato train --model lgbm을 실행하세요.")
    if t < mv["train_end"]:
        raise RuntimeError(f"예측 시점 {t}이 학습 데이터 끝 {mv['train_end']}보다 앞섭니다(미래 라벨 사용).")
    if not Path(mv["artifact_path"]).exists():
        raise RuntimeError(f"모델 파일이 없습니다: {mv['artifact_path']}. tomato train을 다시 실행하세요.")
    return mv["id"], "lgbm", lgbm.predict_last(lgb.Booster(model_file=mv["artifact_path"]), daily, h)


def _chronos_forecast(conn, daily, h, cache):
    """Chronos-2 zero-shot, 검증에서 고른 입력, 0.5 분위수. 파이프라인은 한 번만 로드한다."""
    if "error" in cache:
        raise cache["error"]
    if "pipe" not in cache:
        try:
            cache["pipe"] = chronos2.load_pipeline()
        except Exception as e:
            cache["error"] = e
            raise
    variant = chronos2.load_choice()[str(h)]["selected_input"]
    i = len(daily) - 1
    y_hat = round(float(chronos2.predict(cache["pipe"], daily, [i], variant)[i][h - 1]))
    mv = repo.model_version_id(conn, "chronos2", {"horizon": h, "input": variant, "revision": chronos2.REVISION})
    return mv, "chronos2", y_hat


def forecast_one(conn, daily, h, model, cache):
    """(model_version_id, 실제로 쓴 모델, ŷ). Chronos-2가 실패하면 LightGBM full로 대체하고 사유를 stderr에 남긴다."""
    if model == "chronos2":
        try:
            return _chronos_forecast(conn, daily, h, cache)
        except Exception as e:  # noqa: BLE001 - 어떤 실패든 LightGBM으로 대체한다
            print(f"[경고] h={h} Chronos-2 실패, LightGBM full로 대체: {type(e).__name__}: {e}", file=sys.stderr)
            model = "lgbm"
    if model == "lgbm":
        return _lgbm_forecast(conn, daily, h)
    y_hat = round(baselines.MODELS[model]([r.price for r in daily]))
    return repo.model_version_id(conn, model, {}), model, y_hat


def cmd_predict(conn, args):
    daily = _daily(conn, args.origin)
    if args.origin and daily[-1].date != args.origin:
        sys.exit(f"{args.origin}은 거래일(평균가 있는 날)이 아닙니다.")
    t, y0 = daily[-1].date, daily[-1].price
    holidays = cal.kr_holidays([t.year, t.year + 1])
    rows, used, cache = [], [], {}
    for h in _horizons(args.horizons):
        model = OPS_MODELS.get(h, "lgbm") if args.model == "ops" else args.model
        try:
            mv_id, name, y_hat = forecast_one(conn, daily, h, model, cache)
        except RuntimeError as e:
            sys.exit(str(e))
        used.append(name)
        r = metrics.change(y0, y_hat)
        rows.append({
            "model_version_id": mv_id, "experiment": "live", "origin_date": t, "horizon_tdays": h,
            "target_date_est": cal.add_trading_days(t, h, holidays), "y_origin": y0, "y_hat": y_hat,
            "change_pct": round(100 * r, 3), "direction": metrics.direction(r), "is_backtest": False,
        })
    for fid, row, name in zip(repo.upsert_forecasts(conn, rows), rows, used, strict=True):
        print(f"forecast {fid}: {name}, t={t} y={y0:,} → {row['horizon_tdays']}거래일 후"
              f"({row['target_date_est']} 예상) {row['y_hat']:,} ({row['change_pct']:+.1f}%, {row['direction']})")


def _save_backtest(conn, name, params, experiment, horizon, rows, b1_rows, simulate, dm=False, chronos_dm=None):
    mv = repo.model_version_id(conn, name, params)
    repo.upsert_forecasts(conn, [{
        "model_version_id": mv, "experiment": experiment, "origin_date": r["origin_date"],
        "horizon_tdays": horizon, "target_date_est": r["target_date"], "y_origin": r["y0"],
        "y_hat": r["y_hat"], "change_pct": round(100 * metrics.change(r["y0"], r["y_hat"]), 3),
        "direction": metrics.direction(metrics.change(r["y0"], r["y_hat"])), "is_backtest": True,
    } for r in rows])
    out, notes = {}, []
    b1_seg = walkforward.segments(b1_rows)
    for seg, seg_rows in walkforward.segments(rows).items():
        ms = walkforward.score(seg_rows, b1_seg[seg], simulate)
        if dm:
            dm_metrics, info = walkforward.score_dm(seg_rows, b1_seg[seg], horizon)
            ms += dm_metrics
            notes.append(f"DM {seg}: 통계량 {info['stat']:.3f}, p {info['p']:.4f}, 커널 {info['kernel']},"
                         f" α {walkforward.DM_ALPHA} 기준 {'유의' if info['p'] < walkforward.DM_ALPHA else '유의하지 않음'}")
        if chronos_dm:
            lgbm_rows, base_rows = chronos_dm
            for ref, ref_rows, suffix in (("LightGBM full", lgbm_rows, "_vs_lgbm"), ("B1", base_rows, "")):
                dm_metrics, info = walkforward.score_dm(seg_rows, walkforward.segments(ref_rows)[seg], horizon)
                ms += [{**m, "metric": m["metric"] + suffix} for m in dm_metrics]
                judged = ref == "LightGBM full" and seg == "test_all"
                verdict = (f"α {walkforward.CHRONOS_DM_ALPHA:.4f} 기준 "
                           f"{'유의' if info['p'] < walkforward.CHRONOS_DM_ALPHA else '유의하지 않음'}"
                           if judged else "참고(판정 대상 아님)")
                notes.append(f"DM Chronos-2 vs {ref} {seg}: 통계량 {info['stat']:.3f}, p {info['p']:.4f},"
                             f" 커널 {info['kernel']}, {verdict}")
        out[seg] = {m["metric"]: m for m in ms}
    _replace(conn, experiment, name, horizon, out)
    return out, notes


def _replace(conn, experiment, name, horizon, out):
    repo.replace_metrics(conn, experiment, name, [{**m, "segment": s} for s, ms in out.items() for m in ms.values()],
                         horizon)


def _save_reference(conn, name, horizon, b1_rows, score):
    """B3·오라클: 가격 예측이 없어 forecast는 저장하지 않고 지표만 저장한다."""
    out = {seg: {m["metric"]: m for m in score(rows)} for seg, rows in walkforward.segments(b1_rows).items()}
    _replace(conn, "window=full", name, horizon, out)
    return out


def _fmt(m, key, spec, scale=1.0, sign=1):
    if key in m:
        return format(sign * scale * m[key]["value"], spec)
    return format("—", spec[0] + "".join(c for c in spec[1:].split(".")[0] if c.isdigit()))


def _print_table(results):
    print(f"{'segment':<9} {'model':<12} {'MAE':>8} {'상대MAE':>7} {'MAPE':>6} {'상하적중':>7} {'3분류':>6} {'절감액(A-B)':>13} {'절감%':>6} {'n':>5}")
    for seg in ("test_all", "spike"):
        for name, res in results.items():
            m = res[seg]
            n = next(iter(m.values()))["n"] if "mae" not in m else m["mae"]["n"]
            if "sim_cost_a" in m:
                n = m["sim_cost_a"]["n"]
            print(f"{seg:<9} {name:<12} {_fmt(m, 'mae', '>8.1f')} {_fmt(m, 'rel_mae', '>7.4f')}"
                  f" {_fmt(m, 'mape', '>6.2f')} {_fmt(m, 'dir_acc_ud', '>7.1f', 100)}"
                  f" {_fmt(m, 'dir_acc3', '>6.1f', 100)} {_fmt(m, 'sim_diff_won', '>13,.0f', sign=-1)}"
                  f" {_fmt(m, 'sim_diff_pct', '>6.2f', sign=-1)} {n:>5}")


def cmd_backtest(conn, args):
    names = args.models.split(",")
    known = (*baselines.MODELS, "lgbm", "chronos2")
    unknown = [n for n in names if n not in known]
    if unknown:
        sys.exit(f"지원 모델은 {', '.join(known)}입니다: {unknown}")
    daily = _daily(conn, args.to)
    series = [(r.date, r.price) for r in daily]
    tuned = lgbm.load_params() if "lgbm" in names else None
    print(f"데이터 {daily[0].date} ~ {daily[-1].date}, {len(daily)}거래일")
    chronos_preds, chronos_choice = {}, None
    if "chronos2" in names:
        chronos_choice = chronos2.load_choice()
        pipe = chronos2.load_pipeline()
        origins = chronos2.origin_indices(daily, walkforward.TEST_START)
        for variant in sorted({chronos_choice[h]["selected_input"] for h in args.horizons.split(",")}):
            print(f"Chronos-2 ({variant}) 예측 시점 {len(origins)}회 실행 중")
            chronos_preds[variant] = chronos2.predict(pipe, daily, origins, variant)

    for h in _horizons(args.horizons):
        simulate = h in walkforward.SIM_HORIZONS
        selected = tuned[str(h)]["selected_window"] if tuned else None
        b1_rows = walkforward.backtest(series, baselines.b1, horizon=h)
        all_rows, results, notes = {}, {}, []
        for name in names:
            if name == "lgbm":
                for w in args.window.split(","):
                    params = tuned[str(h)][w]["params"]
                    all_rows[f"lgbm-{w}"] = (lgbm.backtest(daily, h, params, w), f"window={w}",
                                             {"horizon": h, "window": w, **params})
            elif name == "chronos2":
                variant = chronos_choice[str(h)]["selected_input"]
                all_rows["chronos2"] = (chronos2.rows(daily, chronos_preds[variant], h, walkforward.TEST_START),
                                        f"input={variant}", {"horizon": h, "input": variant, "revision": chronos2.REVISION})
            else:
                all_rows[name] = (walkforward.backtest(series, baselines.MODELS[name], horizon=h), "window=full", {})
        walkforward.assert_same_origins({"B1": b1_rows, **{k: v[0] for k, v in all_rows.items()}})
        for label, (rows, experiment, params) in all_rows.items():
            dm = h in walkforward.DM_HORIZONS and label == f"lgbm-{selected}"
            extra = None
            if label == "chronos2" and f"lgbm-{selected}" in all_rows:
                extra = (all_rows[f"lgbm-{selected}"][0], b1_rows)
            results[label], n = _save_backtest(conn, label.split("-")[0], params, experiment, h, rows, b1_rows,
                                               simulate, dm, extra)
            notes += n
        results["B3"] = _save_reference(conn, "B3", h, b1_rows, lambda r: walkforward.score_b3(r, simulate))
        if simulate:
            for name, fn in (("oracle_opt", simulation.oracle_opt_buys_now), ("oracle_rule", simulation.oracle_rule_buys_now)):
                results[name] = _save_reference(conn, name, h, b1_rows, lambda r, fn=fn: walkforward.score_oracle(r, fn))
        print(f"\n=== h={h}, 예측 시점 {b1_rows[0]['origin_date']} ~ {b1_rows[-1]['origin_date']}, {len(b1_rows)}회"
              f"{'' if simulate else ', 매입 시뮬레이션 없음'} ===")
        _print_table(results)
        for note in notes:
            print(note)
        if tuned and "B2" in results:
            cand = {"B2": results["B2"], f"lgbm-{selected}": results[f"lgbm-{selected}"]}
            if "chronos2" in results:
                cand["chronos2"] = results["chronos2"]
            chosen, reasons = selection.select(
                {k: {x: v["test_all"][x]["value"] for x in ("mae", "rel_mae", "dir_acc_ud")} for k, v in cand.items()}
            )
            print(f"선택 (h={h}, 검증에서 고른 창 {selected}): {chosen}")
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
    pr.add_argument("--model", choices=["ops", "chronos2", "lgbm", "B1", "B2"], default="ops",
                    help="ops = 운영 모델(h = 3·7 Chronos-2, 실패 시 LightGBM)")
    pr.add_argument("--horizons", default="3,7")
    pr.set_defaults(fn=cmd_predict)

    bt = sub.add_parser("backtest")
    bt.add_argument("--models", default="B1")
    bt.add_argument("--window", default="full,5y", help="full, 5y 또는 full,5y")
    bt.add_argument("--horizons", default="3,7,21")
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
