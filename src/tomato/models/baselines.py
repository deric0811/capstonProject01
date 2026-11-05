"""기준선 (spec §3). 기간 h와 무관하게 같은 값을 낸다. history = t까지의 가격 목록."""
B2_K = 5


def b1(history):
    """B1 직전가: ŷ(t+h) = y(t)."""
    return history[-1]


def b2(history):
    """B2 최근 평균: ŷ(t+h) = 최근 5거래일 평균. 5일이 안 되면 있는 만큼."""
    recent = history[-B2_K:]
    return sum(recent) / len(recent)


MODELS = {"B1": b1, "B2": b2}
