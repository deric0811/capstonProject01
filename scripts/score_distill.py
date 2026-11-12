"""증류 평가 채점 (spec §6.3). Colab에서 가져온 distill/eval/*.jsonl로 지표·채택 판정·사람 점검 표를 만든다.

uv run python scripts/score_distill.py → distill/eval/metrics.json, distill/eval/human_check.csv
"""
import csv
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

    print(f"{'모델':14} {'n':>4} {'통과':>6} {'(a)':>6} {'(b)':>6} {'(c)':>6} {'형식':>6} {'시간(초)':>8} {'VRAM(GB)':>8}")
    for m, s in summary.items():
        print(f"{m:14} {s['n']:>4} " + " ".join(f"{100 * s[k]:>5.1f}%" for k in scoring.RULES)
              + f" {s.get('mean_sec') or '—':>8} {s.get('max_reserved_gb') or '—':>8}")
    print(json.dumps(result["paired_pass"], ensure_ascii=False), json.dumps(result["decision"], ensure_ascii=False))

    lora = {r["id"]: r["text"] for r in read(D / "eval" / "student_lora.jsonl")}
    by_id = {r["id"]: r["input"] for r in inputs}
    with open(D / "eval" / "human_check.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["id", "현재가", "예상가", "해설", "자동검사_통과", "사실_오류", "근거없는_원인", "어색한_문장", "메모"])
        for i in scoring.human_sample(inputs):
            x = by_id[i]
            w.writerow([i, x["y_origin"], x["y_hat"], lora.get(i, ""), per["student_lora"][i]["pass"], "", "", "", ""])
    return 0


if __name__ == "__main__":
    sys.exit(main())
