"""템플릿 설명 (LLM 없이). spec §6의 입력을 만들고, 그 입력의 숫자만으로 문장을 만든다.

3단계에서 LLM 설명이 근거 검사에 실패하면 이 문장으로 대체한다.
"""
import statistics

PROVIDER = MODEL = "template"
DIRECTION_KO = {"up": "오를 것으로", "down": "내릴 것으로", "flat": "큰 변화가 없을 것으로"}


def build_input(series, forecast, perf=None):
    """series = [(date, avg_price, n_markets)] 예측 시점 t까지. forecast = repo.latest_forecast 형식."""
    t = forecast["origin_date"]
    hist = [r for r in series if r[0] <= t]
    y0 = hist[-1][1]
    window = hist[-21:]  # t 포함 21개 = 20거래일 변화
    same_month = [p for d, p, _ in hist if d.month == t.month and (d.year, d.month) < (t.year, t.month)]
    return {
        "origin_date": t.isoformat(),
        "target_date_est": forecast["target_date_est"].isoformat(),
        "horizon_tdays": forecast["horizon_tdays"],
        "model": forecast["model"],
        "y_origin": y0,
        "y_hat": forecast["y_hat"],
        "diff": forecast["y_hat"] - y0,
        "change_pct": round(float(forecast["change_pct"]), 1),
        "direction": forecast["direction"],
        "trend20": {
            "start_date": window[0][0].isoformat(), "start_price": window[0][1],
            "change_pct": round(100 * (y0 - window[0][1]) / window[0][1], 1),
            "min": min(p for _, p, _ in window), "max": max(p for _, p, _ in window),
        },
        "seasonal": {
            "month": t.month,
            "median": round(statistics.median(same_month)) if same_month else None,
            "vs_median_pct": round(100 * (y0 / statistics.median(same_month) - 1), 1) if same_month else None,
        },
        "markets": {"today": hist[-1][2], "prev": hist[-2][2] if len(hist) > 1 else None},
        "performance": perf,
    }


def render(x):
    s = [f"{x['origin_date']} 기준 토마토 도매 평균가(상품, 5kg)는 {x['y_origin']:,}원입니다."]

    when = f"{x['horizon_tdays']}거래일 후({x['target_date_est']} 예상)"
    if x["model"] == "B1":
        s.append(f"{when} 예상가는 현재가와 같은 {x['y_hat']:,}원입니다. 지금은 최근 가격이 그대로 유지된다고 보는 "
                 "기준 방식(직전가)으로 예측합니다.")
    else:
        s.append(f"{when} 예상가는 {x['y_hat']:,}원으로, 현재가보다 {x['diff']:+,}원({x['change_pct']:+.1f}%) "
                 f"{DIRECTION_KO[x['direction']]} 예상됩니다.")

    tr = x["trend20"]
    s.append(f"최근 20거래일 동안 {tr['start_price']:,}원에서 {x['y_origin']:,}원으로 {tr['change_pct']:+.1f}% 움직였고, "
             f"이 기간 최저 {tr['min']:,}원, 최고 {tr['max']:,}원이었습니다.")

    se = x["seasonal"]
    if se["median"] is not None:
        side = "높습니다" if se["vs_median_pct"] > 0 else "낮습니다" if se["vs_median_pct"] < 0 else "같습니다"
        gap = f"{abs(se['vs_median_pct']):.1f}% " if se["vs_median_pct"] else ""
        s.append(f"과거 {se['month']}월 중앙값 {se['median']:,}원보다 현재가가 {gap}{side}.")

    mk = x["markets"]
    if mk["prev"] is not None and mk["today"] != mk["prev"]:
        s.append(f"오늘 가격을 낸 도매시장은 {mk['today']}곳으로 직전 거래일({mk['prev']}곳)과 달라, "
                 "평균에 들어간 시장 구성이 바뀌었습니다.")

    perf = x["performance"]
    tail = "예측은 틀릴 수 있고 예상 날짜도 평일·공휴일 기준 추정이므로 참고용으로만 보세요."
    if perf and perf.get("mae_reduction_pct") is not None:
        s.append(f"이 모델의 2023년 이후 {x['horizon_tdays']}거래일 후 평균 오차는 {perf['mae']:,}원"
                 f"(MAPE {perf['mape']:.1f}%)으로, 직전가 방식보다 {perf['mae_reduction_pct']:.1f}% 작습니다. {tail}")
    elif perf:
        s.append(f"이 방식의 2023년 이후 {x['horizon_tdays']}거래일 후 평균 오차는 {perf['mae']:,}원"
                 f"(MAPE {perf['mape']:.1f}%)입니다. {tail}")
    else:
        s.append(tail)
    return " ".join(s)
