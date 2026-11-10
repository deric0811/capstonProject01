"""프롬프트 시험 (spec §6.2): API 제공자(Gemini 무료 티어)로 학습용 입력 일부만 생성해 근거 검사 통과율을 본다.

uv run python scripts/prompt_trial.py --n 25 --out <scratch 경로>
- 키는 .env의 LLM_API_KEY. 출력하지 않는다.
- 학습용(split = train) 입력만 쓴다. 검증(2022)·평가(2023 ~) 입력은 쓰지 않는다.
- 생성 결과는 repo 밖(--out)에만 둔다. Gemini 출력은 학습 데이터로 쓰지 않는다(약관).
"""
import argparse
import json
import random
import sys
import time
from pathlib import Path

from tomato import config
from tomato.explain import grounding, llm, prompt

SEED = 20261110


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=25)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--sleep", type=float, default=6.0, help="무료 티어 분당 호출 한도용 간격(초)")
    ap.add_argument("--model", default=None)
    args = ap.parse_args()
    if config.ROOT in args.out.resolve().parents:
        sys.exit("--out은 repo 밖이어야 합니다.")

    s = llm.settings_for("api")
    if not s.api_key:
        sys.exit(".env에 LLM_API_KEY가 없습니다.")
    if args.model:
        s = llm.LLMSettings(s.provider, s.base_url, args.model, s.api_key, s.timeout, s.extra)
    recs = [json.loads(line) for line in open(config.ROOT / "distill/inputs/train.jsonl", encoding="utf-8")]
    recs = random.Random(SEED).sample([r for r in recs if r["split"] == "train"], args.n)

    results = []
    for k, r in enumerate(recs):
        try:
            text, sec = llm.chat(s, prompt.messages(r["input"]))
            res = grounding.check(text, r["input"])
        except RuntimeError as e:
            text, sec, res = "", 0.0, {"pass": False, "a": False, "b": False, "c": False, "format": False,
                                       "errors": [str(e)]}
        results.append({"id": r["id"], "text": text, "sec": round(sec, 2), **res})
        print(f"[{k + 1}/{len(recs)}] {r['id']} pass={res['pass']} {'; '.join(res['errors'])[:160]}", flush=True)
        time.sleep(args.sleep)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        for x in results:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")
    n = len(results)
    summary = {k: sum(x[k] for x in results) for k in ("pass", "a", "b", "c", "format")}
    print(f"\n모델 {s.model}, 프롬프트 {prompt.PROMPT_VERSION}, n = {n}")
    for k, v in summary.items():
        print(f"  {k}: {v}/{n} ({100 * v / n:.0f}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
