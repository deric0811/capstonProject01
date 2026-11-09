"""매입 시뮬레이션 (spec §2). 기간 안에 1단위를 반드시 산다. 매입 가격은 t+1 이후의 공표가만 쓴다.

A: 항상 t+1. B: 매입 신호가 있으면 t+1, 없으면 t+h. 신호는 전략마다 다르다.
"""
from tomato.evaluation import metrics


def model_buys_now(row):
    """모델: 방향이 상승(예측 등락률 > +δ)."""
    return metrics.direction(metrics.change(row["y0"], row["y_hat"])) == "up"


def b3_buys_now(row):
    """B3 추세 규칙: y(t) > 최근 5거래일 평균(t 포함). δ 없음, 같으면 신호 없음."""
    return row["y0"] > row["mean5"]


def oracle_opt_buys_now(row):
    """오라클-최적: min(y(t+1), y(t+h))에 산다. 엄밀한 상한."""
    return row["y1"] <= row["y"]


def oracle_rule_buys_now(row):
    """오라클-규칙: 같은 규칙에 실제 등락률을 넣는다. 엄밀한 상한은 아니다."""
    return metrics.direction(metrics.change(row["y0"], row["y"])) == "up"


def strategy_b_cost(row, buys_now=model_buys_now):
    return row["y1"] if buys_now(row) else row["y"]


def simulate(rows, buys_now=model_buys_now):
    """rows의 키: y0 = y(t), y1 = y(t+1), y = y(t+h), 그리고 buys_now가 쓰는 키. 차이는 B − A이고 음수면 B가 싸다."""
    a = sum(r["y1"] for r in rows)
    b = sum(strategy_b_cost(r, buys_now) for r in rows)
    return [
        {"metric": "sim_cost_a", "value": a, "n": len(rows)},
        {"metric": "sim_cost_b", "value": b, "n": len(rows)},
        {"metric": "sim_diff_won", "value": b - a, "n": len(rows)},
        {"metric": "sim_diff_pct", "value": 100 * (b - a) / a, "n": len(rows)},
    ]
