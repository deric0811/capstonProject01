"""기준선 (spec §3). 1단계는 B1만 구현한다."""


def b1(history):
    """B1 직전가: ŷ(t+3) = y(t). history = t까지의 가격 목록."""
    return history[-1]


MODELS = {"B1": b1}
