"""데모 서버(RTX 2080 Ti 22GB) GPU 확인. spec §6.2 계산 dtype, §6.3 채택 기준 2(VRAM).

uv 환경과 따로, 데모 서버에 CUDA용 가상환경을 만든다 (repo 루트에서):
  python3 -m venv ~/hcx-venv && . ~/hcx-venv/bin/activate
  pip install torch "transformers>=5.9.0" bitsandbytes accelerate

1) 계산 dtype 확인 (평가 전, 사용자가 실행)
   python scripts/demo_gpu_check.py --out ~/demo_dtype.json
   - 학생 원본(revision 고정)을 배포 형식(NF4 이중 양자화 + embedding만 CPU)으로 올린다.
     첫 실행 때 원본 약 59GB(fp32)를 내려받는다. dtype마다 다시 올린다.
   - 학습용 입력(2003 ~ 2021) 3개를 seed 고정으로 뽑아 fp16, bf16으로 각각 batch 1 greedy 생성한다.
   - dtype별로 NaN/inf 여부, 평균 생성 시간, 최대 VRAM(max_memory_reserved), 출력 앞부분을 출력한다.
   - 이 결과로 사용자가 dtype 하나를 정한다. 평가 입력은 쓰지 않는다.

2) 채택 기준 2: (ii) LoRA 학생 VRAM (Colab 04 뒤에)
   python scripts/demo_gpu_check.py --timing --model <merged_nf4 경로> --dtype <정한 dtype>
   - A100 시간 측정과 같은 평가 입력 50개를 batch 1로 생성해 distill/eval/student_lora_demo.json에 쓴다.
"""
import argparse
import json
import random
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "notebooks")]

import distill_common as dc  # noqa: E402
from tomato.explain import grounding, prompt  # noqa: E402

SEED = 20261112
N_CHECK = 3


def read(name):
    with open(ROOT / "distill" / "inputs" / f"{name}.jsonl", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def check_inputs(n=N_CHECK):
    recs = [r for r in read("train") if r["split"] == "train"]
    return sorted(random.Random(SEED).sample(recs, n), key=lambda r: r["id"])


def smi_used_gb():
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits", "-i", "0"],
                             capture_output=True, text=True, timeout=10).stdout
        return round(float(out.strip().splitlines()[0]) * 2**20 / 1e9, 2)
    except Exception:
        return None


def run_dtype(model_path, compute, recs):
    import torch

    res = {"compute_dtype": compute, "model": model_path, "rows": []}
    try:
        model, tok = dc.load_student(model_path, compute=compute)
    except Exception as e:  # bf16을 지원하지 않으면 여기서 실패할 수 있다
        return res | {"error": f"load: {type(e).__name__}: {e}"[:400]}
    res["cpu_modules"] = [k for k, v in model.hf_device_map.items() if v == "cpu"]
    torch.cuda.synchronize()
    torch.cuda.reset_peak_memory_stats()
    try:
        for r in recs:
            enc = tok([dc.student_prompt(tok, prompt, r["input"])], return_tensors="pt",
                      add_special_tokens=False).to(0)
            torch.cuda.synchronize()
            t0 = time.time()
            with torch.no_grad():
                g = model.generate(**enc, do_sample=False, max_new_tokens=dc.MAX_NEW_TOKENS, use_cache=True,
                                   stop_strings=dc.STOP_STRINGS, tokenizer=tok, pad_token_id=tok.pad_token_id)
            torch.cuda.synchronize()
            sec = time.time() - t0
            text = dc._clean(tok.decode(g[0, enc["input_ids"].shape[1]:], skip_special_tokens=False))
            res["rows"].append({"id": r["id"], "sec": round(sec, 2), "new_tokens": int(g.shape[1] - enc["input_ids"].shape[1]),
                                "text": text, "grounding_pass": grounding.check(text, r["input"])["pass"] if text else False})
        res["max_reserved_gb"] = round(torch.cuda.max_memory_reserved() / 1e9, 2)
        res["max_allocated_gb"] = round(torch.cuda.max_memory_allocated() / 1e9, 2)
        res["nvidia_smi_used_gb"] = smi_used_gb()
        # NaN/inf: VRAM을 잰 뒤, 마지막 생성 전체(프롬프트 + 출력)를 한 번 더 넣어 logits를 검사한다
        nonfinite = 0
        for r, row in zip(recs, res["rows"]):
            enc = tok([dc.student_prompt(tok, prompt, r["input"]) + row["text"]],
                      return_tensors="pt", add_special_tokens=False).to(0)
            with torch.no_grad():
                logits = model(**enc).logits
            nonfinite += int((~torch.isfinite(logits)).any().item())
            del logits
        res["nan_or_inf_inputs"] = nonfinite
        res["mean_sec"] = round(sum(x["sec"] for x in res["rows"]) / len(res["rows"]), 2)
    except Exception as e:
        res["error"] = f"generate: {type(e).__name__}: {e}"[:400]
    del model
    torch.cuda.empty_cache()
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=dc.STUDENT_ID, help="기본: 학생 원본(revision 고정). 또는 merged_nf4 경로")
    ap.add_argument("--dtypes", default="fp16,bf16")
    ap.add_argument("--out", type=Path, help="dtype 확인 결과 json (repo 밖)")
    ap.add_argument("--timing", action="store_true", help="채택 기준 2: 평가 입력 50개 batch 1 VRAM")
    ap.add_argument("--dtype", help="--timing에서 쓸 계산 dtype (spec §6.2에서 정한 값)")
    args = ap.parse_args()

    import torch

    if not torch.cuda.is_available():
        sys.exit("CUDA GPU가 없다.")
    gpu = torch.cuda.get_device_name(0)
    print(f"GPU {gpu}, compute capability {torch.cuda.get_device_capability(0)}, "
          f"torch.cuda.is_bf16_supported() = {torch.cuda.is_bf16_supported()}")

    if args.timing:
        if args.dtype not in dc.COMPUTE_DTYPES:
            sys.exit("--timing에는 --dtype fp16|bf16 (spec §6.2에서 정한 값)이 필요하다.")
        recs = dc.timing_subset(read("eval"))
        model, tok = dc.load_student(args.model, compute=args.dtype)
        t = dc.measure_latency(model, tok, prompt, recs)
        t.update({"model": "student_lora", "path": args.model, "compute_dtype": args.dtype, "where": "demo_server",
                  "nvidia_smi_used_gb": smi_used_gb(), "prompt_version": prompt.PROMPT_VERSION})
        out = ROOT / "distill" / "eval" / "student_lora_demo.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(t, ensure_ascii=False, indent=1) + "\n")
        print(f"{out}: max_reserved {t['max_reserved_gb']} GB (기준 <= 10), mean {t['mean_sec']}초, n {t['n']}")
        return 0

    if args.out and ROOT in args.out.resolve().parents:
        sys.exit("--out은 repo 밖이어야 한다.")
    recs = check_inputs()
    results = []
    for compute in args.dtypes.split(","):
        r = run_dtype(args.model, compute.strip(), recs)
        r["gpu"] = gpu
        results.append(r)
        print(f"\n== {compute}")
        if "error" in r:
            print("  오류:", r["error"])
        for k in ("nan_or_inf_inputs", "mean_sec", "max_reserved_gb", "max_allocated_gb", "nvidia_smi_used_gb", "cpu_modules"):
            if k in r:
                print(f"  {k}: {r[k]}")
        for x in r["rows"]:
            print(f"  {x['id']} {x['sec']}초 {x['new_tokens']}토큰 근거검사={x['grounding_pass']} | {x['text'][:100]!r}")
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(results, ensure_ascii=False, indent=1) + "\n")
        print("\n저장:", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
