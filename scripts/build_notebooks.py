"""notebooks/0*.ipynb 만들기. 노트북을 고칠 때는 이 파일을 고치고 다시 실행한다: uv run python scripts/build_notebooks.py"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "notebooks"

SETUP = r'''# 공통 준비: Drive 연결, 묶음 풀기, 공용 코드 import
from google.colab import drive
drive.mount("/content/drive")
import os, sys, json, time, gc
DIR = "/content/drive/MyDrive/tomato-distill"
os.environ["TOMATO_DISTILL_DIR"] = DIR
# 묶음은 실행할 때마다 새로 푼다(예전 묶음이 남아 다른 프롬프트로 도는 것을 막는다). sha256을 repo에서 만든 값과 비교한다
import shutil, hashlib
shutil.rmtree(f"{DIR}/bundle", ignore_errors=True)
os.makedirs(f"{DIR}/bundle")
!tar xzf {DIR}/tomato_distill_bundle.tar.gz -C {DIR}/bundle
with open(f"{DIR}/tomato_distill_bundle.tar.gz", "rb") as f:
    print("bundle sha256", hashlib.sha256(f.read()).hexdigest())
sys.path.insert(0, f"{DIR}/bundle/notebooks")
import distill_common as dc
prompt = dc.setup()
from tomato.explain import grounding
!nvidia-smi --query-gpu=name,memory.total --format=csv'''


SHUTDOWN = r'''# 끝: Drive에 다 쓴 뒤 런타임을 끈다(끝난 뒤 GPU가 켜진 채 컴퓨팅 단위를 쓰지 않게).
# 앞 셀에서 오류로 멈추면 이 셀은 실행되지 않는다. 그때는 직접 런타임 > 런타임 연결 해제 및 삭제.
AUTO_SHUTDOWN = True
if AUTO_SHUTDOWN:
    drive.flush_and_unmount()
    from google.colab import runtime
    runtime.unassign()'''


def md(text):
    return {"cell_type": "markdown", "metadata": {}, "source": text.strip("\n").splitlines(keepends=True)}


def code(text):
    return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [],
            "source": text.strip("\n").splitlines(keepends=True)}


def notebook(cells):
    return {"cells": cells, "nbformat": 4, "nbformat_minor": 5,
            "metadata": {"accelerator": "GPU", "colab": {"gpuType": "A100", "machine_shape": "hm"},
                         "kernelspec": {"name": "python3", "display_name": "Python 3"}}}


HEADER = """# {title}

| 항목 | 값 |
|---|---|
| GPU | {gpu} |
| 예상 시간 | {time} |
| 예상 컴퓨트 | {cu} (A100 약 13 CU/시간 가정. Colab 리소스 창에서 실제 소모율을 확인해 기록) |
| 디스크 | {disk} |
| 이어 하기 | {resume} |

사전 등록: `docs/spec.md` §6.1~6.3, `docs/decisions.md` 2026-11-10. 설정을 바꾸면 사전 등록 위반이니 멈추고 기록한다.
준비: repo에서 `scripts/pack_distill_bundle.sh`로 만든 `tomato_distill_bundle.tar.gz`를 Drive `MyDrive/tomato-distill/`에 올린다.
"""

NB = {}

NB["01_teacher_generate.ipynb"] = notebook([
    md(HEADER.format(
        title="01 선생 생성 (Qwen3.8-27B, vLLM)",
        gpu="A100 40GB → `Qwen3.8-27B-FP8`, A100 80GB → `Qwen3.8-27B` bf16 (자동 선택)",
        time="약 1시간 10분 (다운로드 15~20분, 시범 50개 2분 + 확인, 학습·검증 3,200개와 재시도 20~30분, 평가 934개와 시간 측정 15분)",
        cu="약 13~15 CU", disk="가중치 29GB(FP8) 또는 56GB(bf16)",
        resume="출력은 256개마다 Drive `teacher/*.jsonl`에 이어 쓴다. 끊기면 처음부터 다시 실행하면 이미 있는 id는 건너뛴다.")),
    code(SETUP),
    code(r'''!pip install -q -U vllm
import vllm, torch
print("vllm", vllm.__version__, "torch", torch.__version__)'''),
    md("## 선생 로드 (GPU 메모리로 정밀도 결정, revision 고정, 사고 출력 끔)"),
    code(r'''from vllm import LLM, SamplingParams
GB = dc.gpu_gb()
TID, TREV = dc.TEACHERS[80 if GB >= 70 else 40]
llm = LLM(model=TID, revision=TREV, max_model_len=4096, gpu_memory_utilization=0.90,
          limit_mm_per_prompt={"image": 0, "video": 0}, seed=dc.SEED)
CT = {"enable_thinking": False}
meta = {"teacher": TID, "revision": TREV, "gpu": torch.cuda.get_device_name(0), "gpu_gb": GB,
        "vllm": vllm.__version__, "prompt_version": prompt.PROMPT_VERSION, "sampling_train": dc.TEACHER_SAMPLING}
print(meta)'''),
    md("## 생성 함수"),
    code(r'''def id_seed(rid, attempt):
    return int(rid.split("-", 1)[1].replace("-", "")) + attempt * 100_000_000

def generate(recs, path, attempt, sampling, step=256):
    dc.check_prompt_version(path, prompt.PROMPT_VERSION)
    done = dc.done_ids(path)
    todo = [r for r in recs if r["id"] not in done]
    for k in range(0, len(todo), step):
        chunk = todo[k:k + step]
        sps = [SamplingParams(**sampling, seed=id_seed(r["id"], attempt)) for r in chunk]
        t0 = time.time()
        outs = llm.chat([prompt.messages(r["input"]) for r in chunk], sps, chat_template_kwargs=CT, use_tqdm=False)
        sec = time.time() - t0
        rows = []
        for r, o in zip(chunk, outs):
            text = o.outputs[0].text.strip()
            rows.append({"id": r["id"], "split": r["split"], "attempt": attempt, "prompt_version": prompt.PROMPT_VERSION, "text": text,
                         "batch_sec": round(sec, 2), **grounding.check(text, r["input"])})
        dc.append_jsonl(path, rows)
        print(f"{path.name} {len(done) + k + len(chunk)}/{len(recs)} ({sec:.0f}초)", flush=True)

def ok(row):
    return row["pass"] and row["format"]

RULE_KEYS = ("pass", "format", "a", "a_numbers", "a_median", "b", "c", "c_caution", "perf_caution")
T = dc.DRIVE / "teacher"'''),
    md("""## 시범 생성 (spec §6.1): 학습용 입력 50개(seed 20261113) + 새 50개(seed 20261115, 겹치지 않음), 첫 시도만, 학습 설정의 샘플링
- 묶음별·합계 첫 시도 통과율(전체·규칙별), 실패 이유별 개수, 실패 원문 5개를 보고 프롬프트를 고칠지 사용자가 정한다.
- 고치면 repo에서 `PROMPT_VERSION`을 올리고 decisions에 기록한 뒤, 묶음을 다시 만들어 올리고 이 노트북을 처음부터 다시 실행한다.
- 시범 출력은 학습에 쓰지 않는다."""),
    code(r'''import re
from collections import Counter
pilot1, pilot2 = dc.pilot_sets()
ppath = T / f"pilot_{prompt.PROMPT_VERSION}.jsonl"
generate(pilot1 + pilot2, ppath, 0, dc.TEACHER_SAMPLING)
prows = {r["id"]: r for r in dc.read_jsonl(ppath)}
meta["pilot"] = {"prompt_version": prompt.PROMPT_VERSION}
for name, recs in (("seed20261113", pilot1), ("seed20261115", pilot2), ("합계", pilot1 + pilot2)):
    rows = [prows[r["id"]] for r in recs]
    meta["pilot"][name] = {"n": len(rows), **{k: sum(r[k] for r in rows) for k in RULE_KEYS}}
    print(name, json.dumps(meta["pilot"][name], ensure_ascii=False))

def reason(e):  # 실패 이유를 묶는다: 따옴표 안 값과 숫자를 지운다
    return re.sub(r"\d[\d,.]*", "N", re.sub(r"'[^']*'", "'…'", e))

fails = [r for r in prows.values() if not ok(r)]
print("\n실패 이유별 개수:", dict(Counter(reason(e) for r in fails for e in r["errors"]).most_common()))
print("실패 출력 수:", len(fails))
for r in fails[:5]:
    print("----", r["id"], r["errors"]); print(r["text"])'''),
    md("## 프롬프트 고정: 시범 결과를 보고 고정할 버전을 적는다. 이 셀부터가 전체 생성이다"),
    code(r'''FREEZE = None  # 시범 결과를 본 뒤 고정할 PROMPT_VERSION(예: "v2")을 넣는다
assert FREEZE == prompt.PROMPT_VERSION, f"시범을 확인하고 FREEZE = {prompt.PROMPT_VERSION!r}로 고정한다"
assert (T / f"pilot_{FREEZE}.jsonl").exists(), "이 버전의 시범 생성이 없다"
meta["prompt_frozen"] = {"version": FREEZE, "at": time.strftime("%Y-%m-%d %H:%M:%S")}
print(meta["prompt_frozen"])'''),
    md("## 학습(2003~2021) 3,000개 + 검증(2022) 200개 생성, 근거 검사 실패는 seed를 바꿔 최대 2번 재생성"),
    code(r'''train, val = dc.subsets()
for name, recs in (("train", train), ("val", val)):
    remaining = recs
    for attempt in range(dc.MAX_RETRIES + 1):
        path = T / f"{name}_a{attempt}.jsonl"
        generate(remaining, path, attempt, dc.TEACHER_SAMPLING)
        passed = {r["id"] for a in range(attempt + 1) for r in dc.read_jsonl(T / f"{name}_a{a}.jsonl") if ok(r)}
        remaining = [r for r in recs if r["id"] not in passed]
        print(f"{name} attempt {attempt}: 통과 누적 {len(passed)}/{len(recs)}")
        if not remaining:
            break'''),
    code(r'''# 최종 학습 데이터: id마다 처음 통과한 출력. 끝까지 실패한 id는 뺀다.
summary = {}
for name, recs in (("train", train), ("val", val)):
    best = {}
    for a in range(dc.MAX_RETRIES + 1):
        for r in dc.read_jsonl(T / f"{name}_a{a}.jsonl"):
            if ok(r) and r["id"] not in best:
                best[r["id"]] = r
    final = T / f"{name}_final.jsonl"
    final.unlink(missing_ok=True)
    dc.append_jsonl(final, [best[r["id"]] for r in recs if r["id"] in best])
    a0 = dc.read_jsonl(T / f"{name}_a0.jsonl")
    summary[name] = {"n": len(recs), "first_try_pass": sum(ok(r) for r in a0), "final": len(best),
                     **{k: sum(r[k] for r in a0) for k in RULE_KEYS if k != "pass"}}
meta["train_data"] = summary
print(json.dumps(summary, ensure_ascii=False, indent=1))'''),
    md("## 평가 (iii) 선생: 평가 입력 934개, greedy, 재생성 없음"),
    code(r'''GREEDY = {"temperature": 0.0, "max_tokens": dc.MAX_NEW_TOKENS}
evals = dc.eval_inputs()
E = dc.DRIVE / "eval"
generate(evals, E / "teacher.jsonl", 0, GREEDY)'''),
    code(r'''# 평균 생성 시간: batch 1, 평가 입력에서 고정 seed로 뽑은 50개
timing_path = E / "teacher_timing.json"
if not timing_path.exists():
    rows = []
    for r in dc.timing_subset(evals):
        t0 = time.time()
        o = llm.chat([prompt.messages(r["input"])], [SamplingParams(**GREEDY)], chat_template_kwargs=CT, use_tqdm=False)
        rows.append({"id": r["id"], "sec": round(time.time() - t0, 2), "new_tokens": len(o[0].outputs[0].token_ids)})
    used = !nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits
    timing = {"mean_sec": round(sum(x["sec"] for x in rows) / len(rows), 2), "n": len(rows),
              "nvidia_smi_used_gb": round(int(used[0]) / 1024, 2), "note": "vLLM은 gpu_memory_utilization만큼 미리 잡으므로 학생 VRAM과 비교하지 않는다",
              "gpu": torch.cuda.get_device_name(0), "rows": rows}
    timing_path.write_text(json.dumps(timing, ensure_ascii=False, indent=1))
print(json.loads(timing_path.read_text())["mean_sec"])
(dc.DRIVE / "teacher" / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))'''),
    md("""## repo로 가져올 파일
- `teacher/pilot_*.jsonl`, `teacher/train_final.jsonl`, `teacher/val_final.jsonl`, `teacher/train_a*.jsonl`, `teacher/val_a*.jsonl`, `teacher/meta.json` → `distill/teacher/`
- `eval/teacher.jsonl`, `eval/teacher_timing.json` → `distill/eval/`"""),
    code(SHUTDOWN),
])

NB["02_qlora_train.ipynb"] = notebook([
    md(HEADER.format(
        title="02 QLoRA 학습 (HyperCLOVA X SEED 14B Think)",
        gpu="A100 40GB 또는 80GB (둘 다 가능)",
        time="약 3~3.5시간 (다운로드 15분, 학습률 2개 × 2 epoch 학습 2.5시간, 검증 생성 4회 30분)",
        cu="약 40~45 CU", disk="학생 원본 float32 59GB",
        resume="Trainer 체크포인트(epoch마다)를 Drive `lora/`에 저장하고, 다시 실행하면 마지막 체크포인트에서 이어 한다. 검증 생성도 이어 쓴다.")),
    code(SETUP),
    code(r'''!pip install -q -U "transformers>=5.9.0" peft bitsandbytes accelerate
import torch, transformers, peft, bitsandbytes
print(transformers.__version__, peft.__version__, bitsandbytes.__version__)'''),
    md("## 데이터: 선생 출력 중 근거 검사·형식 통과분 (01에서 만든 `*_final.jsonl`)"),
    code(r'''train_in, val_in = dc.subsets()
inputs = {r["id"]: r["input"] for r in train_in + val_in}
train_t = dc.read_jsonl(dc.DRIVE / "teacher" / "train_final.jsonl")
val_t = dc.read_jsonl(dc.DRIVE / "teacher" / "val_final.jsonl")
print(len(train_t), len(val_t))
from transformers import AutoTokenizer
tok = AutoTokenizer.from_pretrained(dc.STUDENT_ID, revision=dc.STUDENT_REV)
tok.padding_side = "right"
train_ds = [dc.sft_features(tok, prompt, inputs[r["id"]], r["text"]) for r in train_t]
val_ds = [dc.sft_features(tok, prompt, inputs[r["id"]], r["text"]) for r in val_t]
print("최대 토큰", max(len(x["input_ids"]) for x in train_ds))
print(tok.decode(train_ds[0]["input_ids"])[-600:])'''),
    md("## 학습: r 16, alpha 32, 학습률 {1e-4, 2e-4} × epoch {1, 2} (epoch마다 체크포인트)"),
    code(r'''from transformers import AutoModelForCausalLM, Trainer, TrainingArguments, DataCollatorForSeq2Seq
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
import glob

def load_base():
    m = AutoModelForCausalLM.from_pretrained(dc.STUDENT_ID, revision=dc.STUDENT_REV, quantization_config=dc.bnb_config(),
                                             dtype=torch.bfloat16, device_map={"": 0})
    return prepare_model_for_kbit_training(m, use_gradient_checkpointing=True)

G = dc.LORA_GRID
for lr in G["lr"]:
    out = dc.DRIVE / "lora" / f"r{G['r']}_lr{lr:g}"
    if (out / "done").exists():
        continue
    model = get_peft_model(load_base(), LoraConfig(r=G["r"], lora_alpha=G["alpha"], lora_dropout=G["dropout"],
                                                   target_modules=G["targets"], task_type="CAUSAL_LM"))
    args = TrainingArguments(output_dir=str(out), num_train_epochs=G["epochs"], learning_rate=lr,
                             per_device_train_batch_size=4, gradient_accumulation_steps=4, per_device_eval_batch_size=8,
                             lr_scheduler_type="cosine", warmup_ratio=0.03, bf16=True, logging_steps=10,
                             eval_strategy="epoch", save_strategy="epoch", save_total_limit=None, seed=dc.SEED,
                             gradient_checkpointing=True, optim="paged_adamw_8bit", report_to="none")
    trainer = Trainer(model=model, args=args, train_dataset=train_ds, eval_dataset=val_ds,
                      data_collator=DataCollatorForSeq2Seq(tok, padding=True, label_pad_token_id=-100))
    ckpts = sorted(glob.glob(f"{out}/checkpoint-*"), key=lambda p: int(p.rsplit("-", 1)[1]))
    trainer.train(resume_from_checkpoint=ckpts[-1] if ckpts else None)
    (out / "log_history.json").write_text(json.dumps(trainer.state.log_history, indent=1))
    (out / "done").write_text("ok")
    del model, trainer; gc.collect(); torch.cuda.empty_cache()'''),
    md("## 설정 선택: 검증(2022) 200개 greedy 생성의 근거 검사 통과율(a·b·c), 동률이면 검증 손실이 낮은 쪽, 그다음 작은 학습률·적은 epoch"),
    code(r'''from peft import PeftModel
results = []
for lr in G["lr"]:
    out = dc.DRIVE / "lora" / f"r{G['r']}_lr{lr:g}"
    hist = json.loads((out / "log_history.json").read_text())
    evals = [h for h in hist if "eval_loss" in h]
    ckpts = sorted(glob.glob(f"{out}/checkpoint-*"), key=lambda p: int(p.rsplit("-", 1)[1]))
    for ep, ck in enumerate(ckpts, start=1):
        path = out / f"val_gen_ep{ep}.jsonl"
        if len(dc.read_jsonl(path)) < len(val_in):
            base, tok_g = dc.load_student(deploy=False)
            model = PeftModel.from_pretrained(base, ck).eval()
            dc.student_generate(model, tok_g, prompt, val_in, batch_size=16, out_path=path, label=f"lr{lr:g} ep{ep}")
            del model, base; gc.collect(); torch.cuda.empty_cache()
        gens = {r["id"]: r["text"] for r in dc.read_jsonl(path)}
        checks = [grounding.check(gens[r["id"]], r["input"]) for r in val_in]
        results.append({"lr": lr, "epoch": ep, "checkpoint": ck, "val_pass": sum(c["pass"] for c in checks) / len(checks),
                        "val_format": sum(c["format"] for c in checks) / len(checks),
                        "val_loss": evals[ep - 1]["eval_loss"]})
chosen = sorted(results, key=lambda x: (-x["val_pass"], x["val_loss"], x["lr"], x["epoch"]))[0]
sel = {"grid": {k: v for k, v in G.items()}, "results": results, "chosen": chosen, "n_train": len(train_ds), "n_val": len(val_in)}
(dc.DRIVE / "lora" / "selection.json").write_text(json.dumps(sel, indent=1, default=str))
print(json.dumps(sel, indent=1, default=str))'''),
    code(r'''# 고른 어댑터만 lora/chosen/에 복사하고 해시를 남긴다
import shutil
dst = dc.DRIVE / "lora" / "chosen"
shutil.rmtree(dst, ignore_errors=True)
shutil.copytree(chosen["checkpoint"], dst, ignore=shutil.ignore_patterns("optimizer.pt", "scheduler.pt", "rng_state*", "trainer_state.json", "training_args.bin"))
print(dc.dir_hashes(dst))'''),
    md("""## repo로 가져올 파일
- `lora/selection.json`, 각 설정의 `log_history.json`, `val_gen_ep*.jsonl` → `distill/lora/`
- `lora/chosen/`(adapter_config.json, adapter_model.safetensors) → `distill/lora/chosen/`
  - r 16, 모든 linear 대상이면 adapter 파라미터가 약 6,100만 개라 파일이 약 120MB(bf16)~250MB(fp32)다. GitHub의 파일당 100MB 제한을 넘으므로 push할 때는 Git LFS를 쓰거나 Drive에 두고 해시만 기록한다."""),
    code(SHUTDOWN),
])

NB["03_merge_quantize.ipynb"] = notebook([
    md(HEADER.format(
        title="03 merge(bf16) + 4bit 양자화 (배포본, 양자화하지 않는 가중치는 fp16)",
        gpu="A100 40GB 또는 80GB (bf16 14.7B 약 29.5GB가 GPU에 올라가야 함), 고용량 RAM",
        time="약 40분 (bf16 로드·merge 10분, 로컬 저장 30GB 10분, NF4 재로드·Drive 저장 9.6GB 15분)",
        cu="약 8~10 CU", disk="원본 59GB + merge bf16 30GB (Colab 로컬 디스크, Drive에는 NF4 9.6GB만)",
        resume="Drive `merged_nf4/hashes.json`이 있으면 끝난 것이다. 중간에 끊기면 처음부터 다시 한다.")),
    code(SETUP),
    code(r'''!pip install -q -U "transformers>=5.9.0" peft bitsandbytes accelerate
import torch, shutil
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
OUT = dc.DRIVE / "merged_nf4"
LOCAL = "/content/merged_bf16"'''),
    code(r'''# 1) bf16 원본에 LoRA merge → 로컬 디스크에 저장
if not (OUT / "hashes.json").exists():
    base = AutoModelForCausalLM.from_pretrained(dc.STUDENT_ID, revision=dc.STUDENT_REV, dtype=torch.bfloat16, device_map={"": 0})
    tok = AutoTokenizer.from_pretrained(dc.STUDENT_ID, revision=dc.STUDENT_REV)
    merged = PeftModel.from_pretrained(base, str(dc.DRIVE / "lora" / "chosen")).merge_and_unload()
    merged.save_pretrained(LOCAL, safe_serialization=True)
    tok.save_pretrained(LOCAL)
    del base, merged; gc.collect(); torch.cuda.empty_cache()'''),
    code(r'''# 2) NF4(이중 양자화)로 다시 읽어 4bit로 저장 → Drive. 데모 서버(2080 Ti)가 bf16을 지원하지 않으므로
#    양자화하지 않는 가중치(embedding·lm_head·norm)와 계산 dtype은 fp16으로 저장한다(spec §6.2)
if not (OUT / "hashes.json").exists():
    q = AutoModelForCausalLM.from_pretrained(LOCAL, quantization_config=dc.bnb_config(dc.EVAL_COMPUTE_DTYPE),
                                             dtype=dc.torch_dtype(dc.EVAL_COMPUTE_DTYPE), device_map={"": 0})
    q.save_pretrained(str(OUT), safe_serialization=True)
    AutoTokenizer.from_pretrained(LOCAL).save_pretrained(str(OUT))
    print("GPU 메모리(4bit 전체 GPU)", round(torch.cuda.memory_allocated() / 1e9, 2), "GB")
    del q; gc.collect(); torch.cuda.empty_cache()
    hashes = dc.dir_hashes(OUT)
    (OUT / "hashes.json").write_text(json.dumps({"source": dc.STUDENT_ID, "revision": dc.STUDENT_REV,
                                                 "adapter": dc.dir_hashes(dc.DRIVE / "lora" / "chosen"),
                                                 "files": hashes}, indent=1))
print((OUT / "hashes.json").read_text())'''),
    md("""## repo로 가져올 파일
- `merged_nf4/hashes.json`만 → `distill/merged_nf4_hashes.json`. 가중치(약 9.6GB)는 Drive에 둔다."""),
    code(SHUTDOWN),
])

NB["04_evaluate.ipynb"] = notebook([
    md(HEADER.format(
        title="04 평가: (i) 학생 원본 4bit, (ii) LoRA 학생 merge 후 4bit (배포본). (iii) 선생은 01에서 생성",
        gpu="A100 40GB 또는 80GB",
        time="약 1.5~2시간 (모델마다 로드 5분, batch 1 시간 측정 50개 15분, 평가 934개 batch 16 생성 25~40분)",
        cu="약 20~25 CU", disk="학생 원본 59GB(캐시) + Drive NF4 9.6GB",
        resume="생성은 batch마다 Drive `eval/*.jsonl`에 이어 쓰고, 시간 측정은 json이 있으면 건너뛴다.")),
    code(SETUP),
    code(r'''!pip install -q -U "transformers>=5.9.0" peft bitsandbytes accelerate
import torch
evals = dc.eval_inputs()
timing = dc.timing_subset(evals)
E = dc.DRIVE / "eval"
print(len(evals), len(timing))'''),
    md("## 배포 형식 그대로 로드 (NF4, embedding만 CPU), greedy, 사고 출력 끔 (skip_reasoning)\n"
       "계산 dtype은 fp16 하나로 (i)·(ii)를 평가한다(spec §6.2, 2026-11-12 확정. 데모 서버 RTX 2080 Ti는 bf16 미지원)."),
    code(r'''COMPUTE_DTYPE = "fp16"  # spec §6.2 (2026-11-12 확정)
assert COMPUTE_DTYPE == dc.EVAL_COMPUTE_DTYPE
MODELS = [("student_base", dc.STUDENT_ID), ("student_lora", str(dc.DRIVE / "merged_nf4"))]
for label, path in MODELS:
    tpath, gpath = E / f"{label}_timing.json", E / f"{label}.jsonl"
    if tpath.exists() and len(dc.read_jsonl(gpath)) >= len(evals):
        continue
    model, tok = dc.load_student(path, compute=COMPUTE_DTYPE)
    print(label, "device map 확인:", {k: v for k, v in model.hf_device_map.items() if v == "cpu"})
    if not tpath.exists():
        t = dc.measure_latency(model, tok, prompt, timing)
        t.update({"model": label, "path": path, "prompt_version": prompt.PROMPT_VERSION, "compute_dtype": COMPUTE_DTYPE})
        tpath.write_text(json.dumps(t, ensure_ascii=False, indent=1))
        print(label, t["mean_sec"], "초", t["max_reserved_gb"], "GB")
    dc.student_generate(model, tok, prompt, evals, batch_size=16, out_path=gpath, label=label)
    del model; gc.collect(); torch.cuda.empty_cache()'''),
    code(r'''# 빠른 확인용 통과율. 최종 지표는 repo의 scripts/score_distill.py로 계산한다.
inputs = {r["id"]: r["input"] for r in evals}
for label in ("student_base", "student_lora", "teacher"):
    rows = dc.read_jsonl(E / f"{label}.jsonl")
    if rows:
        cs = [grounding.check(r["text"], inputs[r["id"]]) for r in rows]
        print(label, len(rows), "pass", round(sum(c["pass"] for c in cs) / len(cs), 3))'''),
    md("""## repo로 가져올 파일
- `eval/student_base.jsonl`, `eval/student_lora.jsonl`, `eval/*_timing.json` → `distill/eval/`
- `merged_nf4/`를 데모 서버로 옮겨 `scripts/demo_gpu_check.py --timing`으로 VRAM을 잰다(채택 기준 2, spec §6.3).
- 그다음 repo에서 `uv run python scripts/score_distill.py`를 실행한다."""),
    code(SHUTDOWN),
])


def main():
    OUT.mkdir(exist_ok=True)
    for name, nb in NB.items():
        (OUT / name).write_text(json.dumps(nb, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(OUT / name)


if __name__ == "__main__":
    main()
