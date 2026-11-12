"""증류 평가 채점 (spec §6.3). Colab에서 가져온 distill/eval/*.jsonl로 지표와 채택 판정을 만든다.

uv run python scripts/score_distill.py → distill/eval/metrics.json
사람 점검((i)·(ii) 가림 파일)은 scripts/human_review.py.
"""
import json
import sys

from tomato import config
from tomato.explain import scoring

D = config.ROOT / "distill"


def read(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in open(path, encoding="utf-8") if line.strip()]


def main():
    inputs = read(D / "inputs" / "eval.jsonl")
    assert len(inputs) == 934, len(inputs)
    summary, per = {}, {}
    for m in scoring.MODELS:
        outs = {r["id"]: r["text"] for r in read(D / "eval" / f"{m}.jsonl")}
        summary[m], per[m] = scoring.score(inputs, outs)
        t = D / "eval" / f"{m}_timing.json"
        if t.exists():
            tj = json.loads(t.read_text())
            summary[m].update({k: tj.get(k) for k in ("mean_sec", "max_reserved_gb", "max_allocated_gb",
                                                       "nvidia_smi_used_gb", "gpu")})
    demo = D / "eval" / "student_lora_demo.json"  # 데모 서버 VRAM (scripts/demo_gpu_check.py --timing)
    demo_vram = json.loads(demo.read_text())["max_reserved_gb"] if demo.exists() else None
    result = {"summary": summary, "paired_pass": scoring.paired(per["student_base"], per["student_lora"]),
              "decision": scoring.decide(summary, demo_vram)}
    (D / "eval" / "metrics.json").write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n")

    print(f"{'모델':14} {'n':>4} " + " ".join(f"{k:>9}" for k in scoring.RULES) + f" {'시간(초)':>8} {'VRAM(GB)':>8}")
    for m, s in summary.items():
        print(f"{m:14} {s['n']:>4} " + " ".join(f"{100 * s[k]:>8.1f}%" for k in scoring.RULES)
              + f" {s.get('mean_sec') or '—':>8} {s.get('max_reserved_gb') or '—':>8}")
    print(json.dumps(result["paired_pass"], ensure_ascii=False), json.dumps(result["decision"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
