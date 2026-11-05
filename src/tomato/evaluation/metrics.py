"""평가 지표 (spec §2). y0 = y(t), y = 실제 y(t+h), yhat = 예측."""
import math

DELTA = 0.03


def mae(y, yhat):
    return sum(abs(a - b) for a, b in zip(y, yhat, strict=True)) / len(y)


def rmse(y, yhat):
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(y, yhat, strict=True)) / len(y))


def mape(y, yhat):
    return 100 * sum(abs(a - b) / a for a, b in zip(y, yhat, strict=True)) / len(y)


def relative_mae(y, yhat, yhat_b1):
    return mae(y, yhat) / mae(y, yhat_b1)


def change(y0, y1):
    return (y1 - y0) / y0


def direction(r, delta=DELTA):
    if r > delta:
        return "up"
    if r < -delta:
        return "down"
    return "flat"


def updown_accuracy(y0, y, yhat, delta=DELTA):
    """실제 |r| > δ인 날만, 예측 등락률의 부호로 채점. 예측 등락률 0은 오답. (적중률, 대상 일수)"""
    hit = n = 0
    for a0, a, p in zip(y0, y, yhat, strict=True):
        r = change(a0, a)
        if abs(r) <= delta:
            continue
        n += 1
        rp = change(a0, p)
        hit += (rp > 0 and r > 0) or (rp < 0 and r < 0)
    return (hit / n if n else float("nan")), n


def three_class_accuracy(y0, y, yhat, delta=DELTA):
    pairs = list(zip(y0, y, yhat, strict=True))
    return sum(direction(change(a0, a), delta) == direction(change(a0, p), delta) for a0, a, p in pairs) / len(pairs)
