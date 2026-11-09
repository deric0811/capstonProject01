"""2단계 사후 분석. 결과를 본 뒤의 분석이며 모델 선택에는 쓰지 않는다 (docs/research/stage2-backtest.md)."""
import math

from tomato.evaluation import metrics
from tomato.models import baselines


def trend_updown_accuracy(rows, history_by_origin, delta=metrics.DELTA):
    """추세 규칙: 예측 방향 = 최근 5거래일 평균(t 포함) 대비 y(t)의 방향. B2 방향의 반대.

    채점은 상승/하락 적중률과 같다(실제 |r| > δ인 날만, 부호 비교, 예측 변화 0은 오답).
    """
    y0 = [r["y0"] for r in rows]
    y = [r["y"] for r in rows]
    pseudo = [r["y0"] + (r["y0"] - baselines.b2(history_by_origin[r["origin_date"]])) for r in rows]
    return metrics.updown_accuracy(y0, y, pseudo, delta)


def diebold_mariano(e_model, e_base, horizon):
    """절대오차 손실 차 d = |e_model| − |e_base|의 DM 통계량과 양측 p값(정규근사).

    분산은 lag h−1까지의 자기공분산 합(직사각형 커널, Diebold-Mariano 1995). 음수면 B가 아니라 모델 오차가 작다.
    """
    d = [abs(a) - abs(b) for a, b in zip(e_model, e_base, strict=True)]
    n = len(d)
    mean = sum(d) / n

    def gamma(k):
        return sum((d[t] - mean) * (d[t - k] - mean) for t in range(k, n)) / n

    var = gamma(0) + 2 * sum(gamma(k) for k in range(1, horizon))
    if var <= 0:
        raise ValueError(f"HAC 분산이 0 이하입니다: {var}")
    stat = mean / math.sqrt(var / n)
    return {"stat": stat, "p": math.erfc(abs(stat) / math.sqrt(2)), "mean_d": mean, "n": n}
