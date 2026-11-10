"""LLM 해설 증류용 입력 JSON 만들기 (spec §6.1). 호스트: uv run --group chronos python scripts/build_explain_inputs.py

- 학습용: 2003 ~ 2022의 모든 거래일 예측 시점(2022는 검증). 평가용: 2023 ~ h = 3 테스트 예측 시점(934회).
- 예측값은 Chronos-2 zero-shot, 운영과 같은 설정. 데이터는 백테스트와 같이 --to 2026-11-04까지.
- 성능 문장 입력(performance)은 모든 시점에 운영 화면과 같은 값(2023 ~ 백테스트)을 넣는다. 시점별로 같은 상수다.
- 결과: distill/inputs/{train,eval}.jsonl. Chronos-2 예측은 scratch 캐시(--cache)에 저장해 중단돼도 이어서 한다.
"""
import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path

import numpy as np
import psycopg

from tomato import calendar as cal
from tomato import cli, config
from tomato.explain import dataset
from tomato.models import chronos2

OUT = config.ROOT / "distill" / "inputs"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--to", type=dt.date.fromisoformat, default=dt.date(2026, 11, 4))
    ap.add_argument("--cache", type=Path, required=True)
    args = ap.parse_args()

    with psycopg.connect(config.load_settings().database_url) as conn:
        daily = cli._daily(conn, args.to)
        perf = cli.performance(conn, "chronos2", dataset.HORIZON)
    variant = chronos2.load_choice()[str(dataset.HORIZON)]["selected_input"]
    train = dataset.train_origins(daily)
    evals = [i for i in chronos2.origin_indices(daily, dataset.EVAL_START) if i + dataset.HORIZON < len(daily)]
    assert len(evals) == 934, len(evals)  # h = 3 테스트와 같은 예측 시점 집합
    print(f"데이터 {daily[0].date} ~ {daily[-1].date}, 학습·검증 {len(train)}회, 평가 {len(evals)}회, 입력 {variant}")

    cache = dict(np.load(args.cache, allow_pickle=True)["preds"].item()) if args.cache.exists() else {}
    todo = [i for i in train + evals if i not in cache]
    pipe = chronos2.load_pipeline() if todo else None
    t0 = time.time()
    for k in range(0, len(todo), 320):
        cache.update(chronos2.predict(pipe, daily, todo[k : k + 320], variant))
        np.savez(args.cache, preds=np.array(cache, dtype=object))
        print(f"  {min(k + 320, len(todo))}/{len(todo)} ({time.time() - t0:.0f}초)", flush=True)

    holidays = cal.kr_holidays(range(daily[0].date.year, daily[-1].date.year + 2))
    OUT.mkdir(parents=True, exist_ok=True)
    for name, origins in (("train", train), ("eval", evals)):
        recs = [dataset.record(daily, i, round(float(cache[i][dataset.HORIZON - 1])), perf, holidays) for i in origins]
        with open(OUT / f"{name}.jsonl", "w", encoding="utf-8") as f:
            for r in recs:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        by = {}
        for r in recs:
            by[r["split"]] = by.get(r["split"], 0) + 1
        print(f"{name}.jsonl: {by}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
