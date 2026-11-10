"""Colab 증류 노트북 공용 코드 (spec §6.1~6.3). torch·transformers·peft·vllm은 Colab에서만 import한다.

Drive 구조 (TOMATO_DISTILL_DIR, 기본 /content/drive/MyDrive/tomato-distill)
  bundle/       scripts/pack_distill_bundle.sh로 만든 묶음을 푼 곳 (src/, distill/inputs/, notebooks/)
  teacher/      선생 출력 jsonl (단계마다 이어 쓰기)
  lora/         설정별 LoRA 체크포인트와 검증 생성 결과
  merged_nf4/   merge 후 4bit 모델 (repo 밖. 경로와 sha256만 기록)
  eval/         평가 생성 결과와 시간·VRAM
"""
import hashlib
import json
import os
import random
import sys
import time
from pathlib import Path

DRIVE = Path(os.environ.get("TOMATO_DISTILL_DIR", "/content/drive/MyDrive/tomato-distill"))
BUNDLE = DRIVE / "bundle"
SEED = 20261111

STUDENT_ID = "naver-hyperclovax/HyperCLOVAX-SEED-Think-14B"
STUDENT_REV = "9b74e35d4c7e4ffec489f4171273caca8948a2b9"
TEACHERS = {  # GPU 메모리(GB) 기준. docs/research/distill-precheck.md §2
    40: ("Qwen/Qwen3.8-27B-FP8", "c3a462cc3d38cf351f3b26cbd763469eeb74ef81"),
    80: ("Qwen/Qwen3.8-27B", "37561816e66b5b9153b1b64c10968c18c1e6f4a0"),
}
TEACHER_SAMPLING = {"temperature": 0.7, "top_p": 0.8, "top_k": 20, "max_tokens": 512}  # 학습 데이터 생성
MAX_RETRIES = 2  # 근거 검사에 실패한 선생 출력은 seed를 바꿔 최대 2번 다시 생성
N_TRAIN, N_VAL, N_TIMING = 3000, 200, 50
MAX_NEW_TOKENS = 512
STOP_STRINGS = ["<|im_end|>", "<|endofturn|>", "<|stop|>"]
LORA_GRID = {"r": 16, "alpha": 32, "dropout": 0.05, "lr": (1e-4, 2e-4), "epochs": 2,
             "targets": ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]}


def setup():
    """Drive의 묶음을 import 경로에 넣고 프롬프트 버전을 출력한다."""
    sys.path.insert(0, str(BUNDLE / "src"))
    from tomato.explain import prompt

    print(f"bundle {BUNDLE}, prompt {prompt.PROMPT_VERSION}")
    return prompt


def load_inputs(name):
    with open(BUNDLE / "distill" / "inputs" / f"{name}.jsonl", encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def subsets():
    """학습 N_TRAIN개(2003~2021), 설정 선택용 검증 N_VAL개(2022). seed 고정, 시간 순서로 정렬."""
    recs = load_inputs("train")
    rng = random.Random(SEED)
    train = [r for r in recs if r["split"] == "train"]
    val = [r for r in recs if r["split"] == "val"]
    pick = lambda rs, n: sorted(rng.sample(rs, min(n, len(rs))), key=lambda r: r["id"])  # noqa: E731
    return pick(train, N_TRAIN), pick(val, N_VAL)


def eval_inputs():
    return load_inputs("eval")


def timing_subset(recs):
    return sorted(random.Random(SEED + 1).sample(recs, N_TIMING), key=lambda r: r["id"])


def read_jsonl(path):
    path = Path(path)
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def done_ids(path):
    return {r["id"] for r in read_jsonl(path)}


def append_jsonl(path, rows):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


def sha256(path, chunk=1 << 24):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while b := f.read(chunk):
            h.update(b)
    return h.hexdigest()


def dir_hashes(d):
    return {p.name: sha256(p) for p in sorted(Path(d).iterdir()) if p.is_file()}


def gpu_gb():
    import torch

    return round(torch.cuda.get_device_properties(0).total_memory / 1e9)


# ---------------- 학생 (transformers + bitsandbytes NF4) ----------------
def bnb_config():
    import torch
    from transformers import BitsAndBytesConfig

    return BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True,
                              bnb_4bit_compute_dtype=torch.bfloat16, llm_int8_enable_fp32_cpu_offload=True)


def deploy_device_map(cfg):
    """배포 형식: embedding만 CPU, 나머지는 GPU 0 (precheck §3 제안, 사용자 확인 필요). 모듈 이름은 빈 모델에서 읽는다."""
    from accelerate import init_empty_weights
    from transformers import AutoModelForCausalLM

    with init_empty_weights():
        m = AutoModelForCausalLM.from_config(cfg)
    dm = {}
    for name, child in m.model.named_children():
        if name == "layers":
            dm.update({f"model.layers.{i}": 0 for i in range(len(child))})
        else:
            dm[f"model.{name}"] = "cpu" if name == "embed_tokens" else 0
    dm.update({name: 0 for name, _ in m.named_children() if name != "model"})
    return dm


def load_student(path_or_id=STUDENT_ID, revision=STUDENT_REV, deploy=True):
    import torch
    from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer

    kw = {"revision": revision} if path_or_id == STUDENT_ID else {}
    cfg = AutoConfig.from_pretrained(path_or_id, **kw)
    tok = AutoTokenizer.from_pretrained(path_or_id, **kw)
    tok.padding_side = "left"
    quant = None if getattr(cfg, "quantization_config", None) else bnb_config()
    model = AutoModelForCausalLM.from_pretrained(
        path_or_id, quantization_config=quant, dtype=torch.bfloat16,
        device_map=deploy_device_map(cfg) if deploy else {"": 0}, **kw)
    model.eval()
    return model, tok


def student_prompt(tok, prompt_mod, x):
    return tok.apply_chat_template(prompt_mod.messages(x), tokenize=False, add_generation_prompt=True,
                                   skip_reasoning=True)


def _clean(text):
    for s in STOP_STRINGS:
        text = text.split(s)[0]
    return text.strip()


def student_generate(model, tok, prompt_mod, recs, batch_size=16, out_path=None, label=""):
    """greedy 생성. out_path가 있으면 batch마다 이어 쓰고, 이미 있는 id는 건너뛴다."""
    import torch

    done = done_ids(out_path) if out_path else set()
    todo = [r for r in recs if r["id"] not in done]
    out = []
    for k in range(0, len(todo), batch_size):
        chunk = todo[k : k + batch_size]
        enc = tok([student_prompt(tok, prompt_mod, r["input"]) for r in chunk], return_tensors="pt",
                  padding=True, add_special_tokens=False).to(0)
        t0 = time.time()
        with torch.no_grad():
            gen = model.generate(**enc, do_sample=False, max_new_tokens=MAX_NEW_TOKENS, use_cache=True,
                                 stop_strings=STOP_STRINGS, tokenizer=tok, pad_token_id=tok.pad_token_id)
        sec = time.time() - t0
        rows = [{"id": r["id"], "text": _clean(tok.decode(g[enc["input_ids"].shape[1]:], skip_special_tokens=False)),
                 "batch_sec": round(sec, 2), "batch_size": len(chunk)} for r, g in zip(chunk, gen)]
        if out_path:
            append_jsonl(out_path, rows)
        out += rows
        print(f"{label} {len(done) + k + len(chunk)}/{len(recs)} ({sec:.0f}초/batch)", flush=True)
    return out


def measure_latency(model, tok, prompt_mod, recs):
    """batch 1, greedy. 평균 생성 시간(초)과 최대 VRAM(GB, max_memory_reserved)."""
    import torch

    torch.cuda.synchronize()
    torch.cuda.reset_peak_memory_stats()
    secs, rows = [], []
    for r in recs:
        enc = tok([student_prompt(tok, prompt_mod, r["input"])], return_tensors="pt", add_special_tokens=False).to(0)
        torch.cuda.synchronize()
        t0 = time.time()
        with torch.no_grad():
            g = model.generate(**enc, do_sample=False, max_new_tokens=MAX_NEW_TOKENS, use_cache=True,
                               stop_strings=STOP_STRINGS, tokenizer=tok, pad_token_id=tok.pad_token_id)
        torch.cuda.synchronize()
        secs.append(time.time() - t0)
        rows.append({"id": r["id"], "sec": round(secs[-1], 2), "new_tokens": int(g.shape[1] - enc["input_ids"].shape[1])})
    return {"mean_sec": round(sum(secs) / len(secs), 2), "n": len(secs),
            "max_reserved_gb": round(torch.cuda.max_memory_reserved() / 1e9, 2),
            "max_allocated_gb": round(torch.cuda.max_memory_allocated() / 1e9, 2),
            "gpu": torch.cuda.get_device_name(0), "rows": rows}


def sft_features(tok, prompt_mod, x, target, max_len=2048):
    """프롬프트(skip_reasoning) + 정답 + 종료 토큰. 손실은 정답 부분에만."""
    p = tok(student_prompt(tok, prompt_mod, x), add_special_tokens=False)["input_ids"]
    t = tok(target.strip() + "<|im_end|><|endofturn|>", add_special_tokens=False)["input_ids"]
    ids = (p + t)[:max_len]
    labels = ([-100] * len(p) + t)[:max_len]
    return {"input_ids": ids, "attention_mask": [1] * len(ids), "labels": labels}
