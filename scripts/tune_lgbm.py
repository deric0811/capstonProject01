"""LightGBM 튜닝 (spec §4): 2020~2022 검증 구간에서 h·학습 창별 파라미터와 h별 학습 창을 고른다.

2022-12-31까지 자른 데이터만 쓴다. 결과는 src/tomato/models/lgbm_params.json에 저장한다.
사용법: DATABASE_URL=postgresql://... uv run python scripts/tune_lgbm.py [--jobs 8]
"""
import argparse
import json
import os
from concurrent.futures import ProcessPoolExecutor

from tomato.db import repo
from tomato.evaluation import metrics, walkforward as wf
from tomato.features import Daily
from tomato.models import baselines, lgbm


def _job(args):
    daily, h, w, k = args
    return h, w, k, *lgbm.validation_mae(daily, h, lgbm.GRID[k], w)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=int, default=os.cpu_count())
    args = ap.parse_args()
    with repo.connect(os.environ["DATABASE_URL"]) as conn:
        daily = lgbm.cut_to_validation([Daily(*r) for r in repo.wholesale_feature_rows(conn)])
    print(f"데이터 {daily[0].date} ~ {daily[-1].date}, {len(daily)}거래일, 조합 {len(lgbm.GRID)}개")

    results = {h: {w: {} for w in wf.WINDOWS} for h in wf.HORIZONS}
    counts = {}
    jobs = [(daily, h, w, k) for h in wf.HORIZONS for w in wf.WINDOWS for k in range(len(lgbm.GRID))]
    with ProcessPoolExecutor(args.jobs) as ex:
        for h, w, k, mae, n in ex.map(_job, jobs):
            results[h][w][k] = mae
            counts[h] = n
    chosen = lgbm.choose(results)

    series = [(r.date, r.price) for r in daily]
    for h in wf.HORIZONS:
        b1 = wf.backtest(series, baselines.b1, start=wf.VALID_START, horizon=h)
        chosen[str(h)]["val_b1_mae"] = metrics.mae([r["y"] for r in b1], [r["y_hat"] for r in b1])
        chosen[str(h)]["val_n"] = counts[h]
        print(f"h={h}: {json.dumps(chosen[str(h)], ensure_ascii=False)}")
    chosen["meta"] = {"data_end": str(daily[-1].date), "grid_size": len(lgbm.GRID), "fixed": lgbm.FIXED}
    lgbm.PARAMS_FILE.write_text(json.dumps(chosen, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"저장: {lgbm.PARAMS_FILE}")


if __name__ == "__main__":
    main()
