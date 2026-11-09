"""매입 시뮬레이션 손계산 대조 (spec §2)."""
import pytest

from tomato.evaluation import selection, simulation
from tomato.models import baselines


def row(y0, y1, y, y_hat):
    return {"y0": y0, "y1": y1, "y": y, "y_hat": y_hat}


def values(rows):
    return {m["metric"]: m["value"] for m in simulation.simulate(rows)}


def test_hand_calculation():
    rows = [
        row(10000, 10100, 11000, 10500),  # +5% 상승: B는 t+1 → 10100
        row(10000, 10200, 9000, 10000),  # 0% 보합: B는 t+h → 9000
        row(10000, 9900, 9500, 9000),  # −10% 하락: B는 t+h → 9500
    ]
    v = values(rows)
    assert v["sim_cost_a"] == 10100 + 10200 + 9900 == 30200
    assert v["sim_cost_b"] == 10100 + 9000 + 9500 == 28600
    assert v["sim_diff_won"] == -1600
    assert v["sim_diff_pct"] == pytest.approx(100 * -1600 / 30200)


def test_exactly_three_percent_is_not_up():
    assert simulation.strategy_b_cost(row(10000, 111, 222, 10300)) == 222
    assert simulation.strategy_b_cost(row(10000, 111, 222, 10301)) == 111


def test_y_t_is_never_a_purchase_price():
    assert values([row(1, 500, 700, 2)])["sim_cost_b"] == 500
    assert values([row(1, 500, 700, 1)])["sim_cost_b"] == 700
    assert values([row(1, 500, 700, 1)])["sim_cost_a"] == 500


def test_b1_always_buys_on_last_day():
    rows = [row(y0, y0 + 1, y0 + 2, baselines.b1([y0])) for y0 in (10000, 20000, 15000)]
    assert values(rows)["sim_cost_b"] == sum(r["y"] for r in rows)


def m(mae, rel, acc):
    return {"mae": mae, "rel_mae": rel, "dir_acc_ud": acc}


def test_select_lowest_mae_among_passing():
    assert selection.select({"B2": m(100, 0.9, 0.6), "lgbm": m(90, 0.8, 0.7)})[0] == "lgbm"


def test_select_excludes_model_below_b2_direction():
    assert selection.select({"B2": m(100, 0.9, 0.6), "lgbm": m(90, 0.8, 0.5)})[0] == "B2"


def test_select_falls_back_to_b1():
    name, reasons = selection.select({"B2": m(100, 1.0, 0.6), "lgbm": m(110, 1.1, 0.7)})
    assert name == "B1" and "B1 채택" in reasons[-1]


def test_select_b2_itself_is_not_excluded_by_its_own_direction():
    assert selection.select({"B2": m(100, 0.9, 0.6), "lgbm": m(110, 1.1, 0.9)})[0] == "B2"


def test_b3_signal_is_strictly_above_mean_without_delta():
    assert simulation.strategy_b_cost({"y0": 101, "mean5": 100, "y1": 1, "y": 2}, simulation.b3_buys_now) == 1
    assert simulation.strategy_b_cost({"y0": 100, "mean5": 100, "y1": 1, "y": 2}, simulation.b3_buys_now) == 2


def test_oracles_hand_calculation():
    rows = [
        row(10000, 10100, 11000, 0),  # 실제 +10%: 규칙·최적 모두 t+1 → 10100
        row(10000, 10300, 10200, 0),  # 실제 +2%: 규칙은 t+h 10200, 최적도 10200
        row(10000, 9800, 10250, 0),  # 실제 +2.5%: 규칙은 t+h 10250, 최적은 t+1 9800
    ]
    opt = {m["metric"]: m["value"] for m in simulation.simulate(rows, simulation.oracle_opt_buys_now)}
    rule = {m["metric"]: m["value"] for m in simulation.simulate(rows, simulation.oracle_rule_buys_now)}
    assert opt["sim_cost_b"] == 10100 + 10200 + 9800
    assert rule["sim_cost_b"] == 10100 + 10200 + 10250


def test_oracle_opt_is_lower_bound_of_any_strategy():
    import itertools
    rows = [row(100, 105, 99, 0), row(100, 98, 101, 0), row(100, 100, 100, 0)]
    best = sum(simulation.strategy_b_cost(r, simulation.oracle_opt_buys_now) for r in rows)
    for picks in itertools.product([True, False], repeat=3):
        assert best <= sum(r["y1"] if p else r["y"] for r, p in zip(rows, picks))
