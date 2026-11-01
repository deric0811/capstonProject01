import pytest

from tomato.evaluation import metrics as m

# y0 = y(t), y = y(t+3) 실제, B1 예측 = y0
Y0 = [10000, 10000, 10000, 10000, 20000]
Y = [10500, 9600, 10300, 10000, 20600]
B1 = Y0


def test_errors_b1():
    # |오차| = 500, 400, 300, 0, 600
    assert m.mae(Y, B1) == pytest.approx(360)
    assert m.rmse(Y, B1) == pytest.approx((sum(e * e for e in [500, 400, 300, 0, 600]) / 5) ** 0.5)
    assert m.mape(Y, B1) == pytest.approx(100 * (500 / 10500 + 400 / 9600 + 300 / 10300 + 0 + 600 / 20600) / 5)


def test_relative_mae_of_b1_is_one():
    assert m.relative_mae(Y, B1, B1) == pytest.approx(1.0)
    better = [10400, 9700, 10300, 10000, 20500]
    assert m.relative_mae(Y, better, B1) < 1


def test_direction_boundary_is_flat():
    assert m.direction(0.03) == "flat"
    assert m.direction(-0.03) == "flat"
    assert m.direction(0.0301) == "up"
    assert m.direction(-0.0301) == "down"
    assert m.direction(m.change(20000, 20600)) == "flat"  # 정확히 3%


def test_updown_accuracy_b1_is_zero():
    # |r| > 3%인 날: 1(+5%), 2(−4%). 3(+3%), 4(0), 5(+3%)는 제외
    acc, n = m.updown_accuracy(Y0, Y, B1)
    assert (acc, n) == (0.0, 2)


def test_updown_accuracy_uses_sign_only():
    pred = [10010, 9999, 0, 0, 0]  # +0.1%, −0.01%: δ 이하여도 부호만 본다
    acc, n = m.updown_accuracy(Y0, Y, pred)
    assert (acc, n) == (1.0, 2)


def test_three_class_accuracy_b1():
    # B1 예측은 모두 flat. 실제 flat은 3,4,5 → 3/5
    assert m.three_class_accuracy(Y0, Y, B1) == pytest.approx(0.6)
