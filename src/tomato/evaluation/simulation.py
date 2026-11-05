"""매입 시뮬레이션 (spec §2). 기간 안에 1단위를 반드시 산다. 매입 가격은 t+1 이후의 공표가만 쓴다.

A: 항상 t+1. B: 방향이 상승(예측 등락률 > +δ)이면 t+1, 아니면 t+h.
"""
from tomato.evaluation import metrics


def strategy_b_cost(row):
    up = metrics.direction(metrics.change(row["y0"], row["y_hat"])) == "up"
    return row["y1"] if up else row["y"]


def simulate(rows):
    """rows의 키: y0 = y(t), y1 = y(t+1), y = y(t+h), y_hat. 차이는 B − A이고 음수면 B가 싸다."""
    a = sum(r["y1"] for r in rows)
    b = sum(strategy_b_cost(r) for r in rows)
    return [
        {"metric": "sim_cost_a", "value": a, "n": len(rows)},
        {"metric": "sim_cost_b", "value": b, "n": len(rows)},
        {"metric": "sim_diff_won", "value": b - a, "n": len(rows)},
        {"metric": "sim_diff_pct", "value": 100 * (b - a) / a, "n": len(rows)},
    ]
