"""Chronos-2 zero-shot (spec §5, 사전 등록 2026-11-10).

- 입력: 거래일만 이어 붙인 수열, 예측 시점 t까지의 전체 이력. t 이후 값은 넣지 않는다.
- 호출: 예측 시점마다 prediction_length = 21로 1회, 3·7·21번째 스텝의 0.5 분위수를 쓴다.
- torch·chronos는 `chronos` 의존성 그룹에만 있으므로 load_pipeline 안에서 import한다.
"""
import json
import math
from pathlib import Path

import numpy as np

from tomato.evaluation import metrics, walkforward as wf
from tomato.models import baselines

MODEL_ID = "amazon/chronos-2"
REVISION = "29ec3766d36d6f73f0696f85560a422f50e8498c"
PRED_LEN = 21
BATCH = 32
VARIANTS = ("target", "cov")  # (가) 상품 평균가만, (나) + 과거값 공변량(중품 평균가, 참여 시장 수)
CHOICE_FILE = Path(__file__).with_name("chronos2_choice.json")


def load_pipeline():
    from chronos import Chronos2Pipeline

    return Chronos2Pipeline.from_pretrained(MODEL_ID, revision=REVISION, device_map="cpu")


def make_input(daily, i, variant):
    """예측 시점 daily[i]의 입력. daily[:i+1]만 쓴다."""
    hist = daily[: i + 1]
    target = np.array([r.price for r in hist], dtype=float)
    if variant == "target":
        return {"target": target}
    if variant == "cov":
        return {"target": target, "past_covariates": {
            "mid_price": np.array([math.nan if r.mid_price is None else r.mid_price for r in hist], dtype=float),
            "n_markets": np.array([r.n_markets for r in hist], dtype=float),
        }}
    raise ValueError(f"알 수 없는 입력: {variant}")


def origin_indices(daily, start):
    """start 이후, 가장 짧은 기간(3거래일)의 실제값이 있는 예측 시점. h = 7, 21의 시점은 이 집합의 앞부분이다."""
    return [i for i, r in enumerate(daily) if r.date >= start and i + min(wf.HORIZONS) < len(daily)]


def predict(pipe, daily, origins, variant, batch_size=BATCH):
    """{i: 21스텝 중앙값 배열}. 예측 시점 순서대로 batch로 묶고, 시계열끼리 정보를 섞지 않는다."""
    out = {}
    for k in range(0, len(origins), batch_size):
        chunk = origins[k : k + batch_size]
        quantiles, _ = pipe.predict_quantiles(
            [make_input(daily, i, variant) for i in chunk], prediction_length=PRED_LEN, quantile_levels=[0.5],
            batch_size=batch_size, cross_learning=False,
        )
        for i, q in zip(chunk, quantiles, strict=True):
            out[i] = np.asarray(q)[0, :, 0]
    return out


def rows(daily, preds, horizon, start):
    """walkforward.backtest와 같은 형식과 같은 예측 시점 집합."""
    out = []
    for i, r in enumerate(daily):
        if r.date < start:
            continue
        if i + horizon >= len(daily):
            break
        history = [x.price for x in daily[: i + 1]]
        out.append({"origin_date": r.date, "target_date": daily[i + horizon].date, "y0": r.price,
                    "y1": daily[i + 1].price, "y": daily[i + horizon].price,
                    "y_hat": round(float(preds[i][horizon - 1])), "mean5": baselines.b2(history)})
    return out


def validation_mae(daily, preds, horizon):
    rs = rows(daily, preds, horizon, wf.VALID_START)
    return metrics.mae([r["y"] for r in rs], [r["y_hat"] for r in rs]), len(rs)


def choose(maes):
    """maes = {h: {variant: val MAE}}. h별로 MAE가 낮은 입력, 동률이면 (가) target."""
    return {str(h): min(VARIANTS, key=lambda v: (by[v], VARIANTS.index(v))) for h, by in maes.items()}


def load_choice(path=CHOICE_FILE):
    if not path.exists():
        raise FileNotFoundError(f"{path.name}가 없습니다. 먼저 scripts/chronos2_validate.py를 실행하세요.")
    return json.loads(path.read_text(encoding="utf-8"))
