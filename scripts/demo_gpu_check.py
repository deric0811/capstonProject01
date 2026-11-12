"""데모 서버(RTX 2080 Ti 22GB, Turing sm_75) GPU 확인. spec §6.2 계산 dtype(fp16), §6.3 채택 기준 2(VRAM).

호스트에는 venv·pip·apt 설치를 하지 않는다. 모든 실행은 Docker(--gpus all) 안에서 한다.
HF 캐시(~/.cache/huggingface)와 결과 파일(~/tomato-demo-out, repo의 distill/eval/)은 볼륨으로 호스트에 남는다.

repo 루트에서:
  docker build -t tomato-demo-gpu deploy/demo-gpu

1) fp16 확인 (평가 전): 학생 원본이 fp16으로 NaN/inf 없이 생성되는지
  mkdir -p ~/.cache/huggingface ~/tomato-demo-out
  docker run --rm --gpus all --user "$(id -u):$(id -g)" \
    -v "$PWD":/repo -v ~/.cache/huggingface:/hf -v ~/tomato-demo-out:/out \
    tomato-demo-gpu --out /out/demo_fp16.json
  - 학생 원본(revision 고정)을 배포 형식(NF4 이중 양자화 + embedding만 CPU, fp16)으로 올린다.
    첫 실행 때 원본 약 59GB(fp32)를 내려받는다.
  - 학습용 입력(2003 ~ 2021) 3개를 seed 고정으로 뽑아 batch 1 greedy 생성한다.
  - NaN/inf 여부, 평균 생성 시간, 최대 VRAM(max_memory_reserved), 출력 앞부분을 출력한다.
  - NaN/inf가 나오면 로컬 배포 불가, API(BYOK)로 간다(spec §6.2).

2) 채택 기준 2: (ii) LoRA 학생 VRAM (Colab 04 뒤에, merged_nf4를 서버로 옮긴 다음)
  docker run --rm --gpus all --user "$(id -u):$(id -g)" \
    -v "$PWD":/repo -v ~/.cache/huggingface:/hf -v <merged_nf4 경로>:/models/merged_nf4:ro \
    tomato-demo-gpu --timing --model /models/merged_nf4
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
COMPUTE = "fp16"  # spec §6.2 (2026-11-12 확정). 2080 Ti는 bf16을 하드웨어로 지원하지 않으므로 bf16 경로는 없다
REQUIRED_ARCH = "sm_75"


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


def environment():
    """torch 빌드와 GPU를 출력하고, sm_75를 지원하지 않는 빌드면 멈춘다."""
    import torch

    info = {"torch": torch.__version__, "cuda_runtime": torch.version.cuda, "cuda_available": torch.cuda.is_available()}
    for mod in ("transformers", "bitsandbytes", "accelerate"):
        try:
            info[mod] = __import__(mod).__version__
        except Exception as e:
            info[mod] = f"import 실패: {e}"
    if not info["cuda_available"]:
        print(json.dumps(info, ensure_ascii=False))
        sys.exit("중단: CUDA GPU가 보이지 않는다. docker run에 --gpus all을 붙였는지, NVIDIA Container Toolkit이 동작하는지 확인한다.")
    info["arch_list"] = torch.cuda.get_arch_list()
    info["gpu"] = torch.cuda.get_device_name(0)
    info["capability"] = ".".join(map(str, torch.cuda.get_device_capability(0)))
    info["total_gb"] = round(torch.cuda.get_device_properties(0).total_memory / 1e9, 2)
    print(json.dumps(info, ensure_ascii=False))
    if REQUIRED_ARCH not in info["arch_list"]:
        sys.exit(f"중단: 이 torch 빌드({info['torch']}, CUDA {info['cuda_runtime']})의 arch 목록에 {REQUIRED_ARCH}가 없다 "
                 f"({info['arch_list']}). RTX 2080 Ti(Turing, 7.5)용 커널이 없으므로 sm_75를 포함한 torch 이미지로 바꾼다.")
    return info


def run_check(model_path, recs):
    import torch

    res = {"compute_dtype": COMPUTE, "model": model_path, "rows": []}
    try:
        model, tok = dc.load_student(model_path, compute=COMPUTE)
    except Exception as e:
        return res | {"error": f"load: {type(e).__name__}: {e}"[:400]}
    res["cpu_modules"] = [k for k, v in model.hf_device_map.items() if v == "cpu"]
    res["param_dtypes"] = sorted({str(p.dtype) for p in model.parameters()})
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
            res["rows"].append({"id": r["id"], "sec": round(sec, 2),
                                "new_tokens": int(g.shape[1] - enc["input_ids"].shape[1]), "text": text,
                                "grounding_pass": grounding.check(text, r["input"])["pass"] if text else False})
        res["max_reserved_gb"] = round(torch.cuda.max_memory_reserved() / 1e9, 2)
        res["max_allocated_gb"] = round(torch.cuda.max_memory_allocated() / 1e9, 2)
        res["nvidia_smi_used_gb"] = smi_used_gb()
        # NaN/inf: VRAM을 잰 뒤, 프롬프트 + 생성 결과 전체를 한 번 더 넣어 logits를 검사한다
        nonfinite = 0
        for r, row in zip(recs, res["rows"]):
            enc = tok([dc.student_prompt(tok, prompt, r["input"]) + row["text"]],
                      return_tensors="pt", add_special_tokens=False).to(0)
            with torch.no_grad():
                logits = model(**enc).logits
            nonfinite += int((~torch.isfinite(logits)).any().item())
            del logits
        res["nan_or_inf_inputs"] = nonfinite
        res["empty_outputs"] = sum(not x["text"] for x in res["rows"])
        res["mean_sec"] = round(sum(x["sec"] for x in res["rows"]) / len(res["rows"]), 2)
    except Exception as e:
        res["error"] = f"generate: {type(e).__name__}: {e}"[:400]
    del model
    torch.cuda.empty_cache()
    res["fp16_ok"] = "error" not in res and res.get("nan_or_inf_inputs") == 0 and res.get("empty_outputs") == 0
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=dc.STUDENT_ID, help="기본: 학생 원본(revision 고정). 또는 merged_nf4 경로")
    ap.add_argument("--out", type=Path, help="fp16 확인 결과 json (repo 밖, 예: /out/demo_fp16.json)")
    ap.add_argument("--timing", action="store_true", help="채택 기준 2: 평가 입력 50개 batch 1 VRAM")
    args = ap.parse_args()

    env = environment()

    if args.timing:
        recs = dc.timing_subset(read("eval"))
        model, tok = dc.load_student(args.model, compute=COMPUTE)
        t = dc.measure_latency(model, tok, prompt, recs)
        t.update({"model": "student_lora", "path": args.model, "compute_dtype": COMPUTE, "where": "demo_server",
                  "nvidia_smi_used_gb": smi_used_gb(), "prompt_version": prompt.PROMPT_VERSION, "env": env})
        out = ROOT / "distill" / "eval" / "student_lora_demo.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(t, ensure_ascii=False, indent=1) + "\n")
        print(f"{out}: max_reserved {t['max_reserved_gb']} GB (기준 <= 10), mean {t['mean_sec']}초, n {t['n']}")
        return 0

    if args.out and ROOT in args.out.resolve().parents:
        sys.exit("--out은 repo 밖이어야 한다.")
    r = run_check(args.model, check_inputs()) | {"env": env}
    print(f"\n== {COMPUTE}")
    if "error" in r:
        print("  오류:", r["error"])
    for k in ("fp16_ok", "nan_or_inf_inputs", "empty_outputs", "mean_sec", "max_reserved_gb", "max_allocated_gb",
              "nvidia_smi_used_gb", "cpu_modules", "param_dtypes"):
        if k in r:
            print(f"  {k}: {r[k]}")
    for x in r["rows"]:
        print(f"  {x['id']} {x['sec']}초 {x['new_tokens']}토큰 근거검사={x['grounding_pass']} | {x['text'][:100]!r}")
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(r, ensure_ascii=False, indent=1) + "\n")
        print("\n저장:", args.out)
    print("\n판정:", "fp16 사용 가능" if r["fp16_ok"] else "fp16 실패 → 로컬 배포 불가, API(BYOK)로 간다 (spec §6.2)")
    return 0 if r["fp16_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
