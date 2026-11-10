"""Chronos-2 입력 선택 (spec §5): 2020~2022 검증 구간 MAE로 h별 (가)/(나)를 고른다.

2022-12-31까지 자른 데이터만 쓴다. 결과는 src/tomato/models/chronos2_choice.json에 저장한다.
사용법: DATABASE_URL=postgresql://... uv run --group chronos python scripts/chronos2_validate.py
"""
import json
import os
import time

from tomato.db import repo
from tomato.evaluation import walkforward as wf
from tomato.features import Daily
from tomato.models import chronos2, lgbm

HORIZONS = (3, 7, 21)
EXPECTED_N = {3: 739, 7: 735, 21: 721}  # LightGBM 튜닝과 같은 검증 예측 시점 수


def main():
    with repo.connect(os.environ["DATABASE_URL"]) as conn:
        daily = lgbm.cut_to_validation([Daily(*r) for r in repo.wholesale_feature_rows(conn)])
    print(f"데이터 {daily[0].date} ~ {daily[-1].date}, {len(daily)}거래일")
    pipe = chronos2.load_pipeline()
    origins = chronos2.origin_indices(daily, wf.VALID_START)
    maes, out = {h: {} for h in HORIZONS}, {}
    for variant in chronos2.VARIANTS:
        t0 = time.time()
        preds = chronos2.predict(pipe, daily, origins, variant)
        for h in HORIZONS:
            mae, n = chronos2.validation_mae(daily, preds, h)
            assert n == EXPECTED_N[h], (h, n)
            maes[h][variant] = mae
        print(f"{variant}: {time.time() - t0:.0f}초, " + ", ".join(f"h={h} MAE {maes[h][variant]:.1f}" for h in HORIZONS))
    chosen = chronos2.choose(maes)
    for h in HORIZONS:
        out[str(h)] = {"selected_input": chosen[str(h)], "val_mae": maes[h], "val_n": EXPECTED_N[h]}
    out["meta"] = {"model": chronos2.MODEL_ID, "revision": chronos2.REVISION, "data_end": str(daily[-1].date),
                   "pred_len": chronos2.PRED_LEN, "batch": chronos2.BATCH, "quantile": 0.5}
    chronos2.CHOICE_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
