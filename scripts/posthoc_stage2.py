"""2단계 사후 분석 (선택에 사용하지 않음). DB에 저장된 backtest 예측을 그대로 읽는다.

사용법: DATABASE_URL=postgresql://... uv run python scripts/posthoc_stage2.py
"""
import datetime as dt
import os

from tomato.db import repo
from tomato.evaluation import metrics, posthoc, walkforward as wf

TO = dt.date(2026, 11, 4)  # stage2-backtest.md의 --to
REPORTED = {3: (934, 1415.6), 7: (930, 2670.2)}  # (예측 시점 수, LightGBM full MAE)


def main():
    with repo.connect(os.environ["DATABASE_URL"]) as conn:
        series = [(d, p) for d, p, _ in repo.wholesale_series(conn) if d <= TO]
        price = dict(series)
        days = [d for d, _ in series]
        print("| h | 구간 | n | 추세 규칙 적중률 (대상 일수) | DM 통계량 | p값 | 평균 손실 차(원) |")
        print("|---|---|---|---|---|---|---|")
        for h in wf.HORIZONS:
            stored = conn.execute(
                "SELECT f.origin_date, f.target_date_est, f.y_origin, f.y_hat FROM forecast f"
                " JOIN model_version mv ON mv.id = f.model_version_id"
                " WHERE mv.name = 'lgbm' AND f.experiment = 'window=full' AND f.is_backtest"
                " AND f.horizon_tdays = %s AND f.target_date_est <= %s ORDER BY f.origin_date",
                (h, TO),
            ).fetchall()
            rows = [{"origin_date": o, "y0": y0, "y": price[tgt], "y_hat": yh} for o, tgt, y0, yh in stored]
            n, mae = REPORTED[h]
            got = metrics.mae([r["y"] for r in rows], [r["y_hat"] for r in rows])
            assert len(rows) == n and abs(got - mae) < 0.05, (h, len(rows), got)  # 보고서와 같은 예측인지
            hist = {d: [p for _, p in series[: i + 1]] for i, (d, _) in enumerate(series) if d >= wf.TEST_START}
            assert all(days[days.index(r["origin_date"]) + h] == tgt for r, (_, tgt, _, _) in zip(rows, stored))
            for seg, seg_rows in wf.segments(rows).items():
                acc, n_ud = posthoc.trend_updown_accuracy(seg_rows, hist)
                dm = posthoc.diebold_mariano([r["y"] - r["y_hat"] for r in seg_rows],
                                             [r["y"] - r["y0"] for r in seg_rows], h)
                name = "전체" if seg == "test_all" else "급등"
                print(f"| {h} | {name} | {len(seg_rows)} | {100 * acc:.1f}% ({n_ud}) | {dm['stat']:.3f} | {dm['p']:.4f}"
                      f" | {dm['mean_d']:.1f} |")


if __name__ == "__main__":
    main()
