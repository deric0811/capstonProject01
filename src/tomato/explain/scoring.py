"""증류 평가 지표와 채택 판정 (spec §6.3, 결과를 보기 전에 고정).

- 분모는 평가 입력 전체(934개). 출력이 없는 입력은 모든 규칙에서 실패로 센다.
- 통과율 = 근거 검사 pass(a and b and c) 비율. 규칙별 a(a_numbers·a_median)·b·c(c_caution)와 형식 준수율을 따로 낸다.
- 채택(2026-11-12 개정): (ii) LoRA 학생 통과율 >= 0.90 그리고 데모 서버(RTX 2080 Ti) batch 1 최대 VRAM
  (max_memory_reserved) <= 10GB(10 × 10⁹ 바이트)이면 explain에 학생을 쓴다.
  미달이면 API(BYOK) → 템플릿. 데모 측정이 아직 없으면 판정을 보류한다.
- 증류 효과: (ii) - (i) 통과율 차이와 짝지은 개수(둘 다 통과, (i)만, (ii)만, 둘 다 실패).
"""
import random

from tomato.explain import grounding

MODELS = ("student_base", "student_lora", "teacher")
ADOPT_THRESHOLD = 0.90
VRAM_LIMIT_GB = 10.0  # 10 × 10⁹ 바이트
HUMAN_N, HUMAN_SEED = 30, 20261111
HUMAN_SHUFFLE_SEED = 20261115  # 사람 점검 행 순서와 모델 가림 (2026-11-12 개정)
HUMAN_MODELS = ("student_base", "student_lora")  # (i), (ii)
RULES = ("pass", "a", "a_numbers", "a_median", "b", "c", "c_caution", "format")  # a = a_numbers and a_median, c ⊇ c_caution


def score(inputs, outputs):
    """inputs = [{id, input}], outputs = {id: text}. (요약, id별 결과)."""
    per = {}
    for r in inputs:
        text = outputs.get(r["id"])
        per[r["id"]] = grounding.check(text, r["input"]) if text else {k: False for k in RULES} | {"errors": ["출력 없음"]}
    n = len(inputs)
    return {"n": n, "missing": sum(r["id"] not in outputs for r in inputs),
            **{k: round(sum(c[k] for c in per.values()) / n, 4) for k in RULES},
            "perf_caution": round(sum(c.get("perf_caution", False) for c in per.values()) / n, 4)}, per


def paired(per_i, per_ii):
    keys = per_i.keys()
    return {
        "both": sum(per_i[k]["pass"] and per_ii[k]["pass"] for k in keys),
        "only_base": sum(per_i[k]["pass"] and not per_ii[k]["pass"] for k in keys),
        "only_lora": sum(per_ii[k]["pass"] and not per_i[k]["pass"] for k in keys),
        "neither": sum(not per_i[k]["pass"] and not per_ii[k]["pass"] for k in keys),
    }


def decide(summary, demo_vram_gb=None):
    """demo_vram_gb: 데모 서버에서 잰 (ii)의 최대 VRAM(GB). None이면 아직 재지 않은 것."""
    rate = summary["student_lora"]["pass"]
    pass_ok = rate >= ADOPT_THRESHOLD
    vram_ok = None if demo_vram_gb is None else demo_vram_gb <= VRAM_LIMIT_GB
    adopt = pass_ok and vram_ok is True
    if adopt:
        explain = "student"
    elif pass_ok and vram_ok is None:
        explain = "pending_demo_vram"
    else:
        explain = "api_or_template"
    return {"adopt_student": adopt, "student_lora_pass": rate, "threshold": ADOPT_THRESHOLD, "pass_ok": pass_ok,
            "demo_vram_gb": demo_vram_gb, "vram_limit_gb": VRAM_LIMIT_GB, "vram_ok": vram_ok, "explain": explain,
            "distill_effect_pts": round(100 * (rate - summary["student_base"]["pass"]), 1)}


def human_sample(inputs):
    return sorted(random.Random(HUMAN_SEED).sample([r["id"] for r in inputs], HUMAN_N))


def human_blind(inputs, outputs):
    """사람 점검(spec §6.3, 2026-11-12 개정): 같은 30개 입력의 (i)·(ii) 출력 60개.

    inputs = [{id, input}] (평가 입력 전체), outputs = {모델: {id: text}}.
    (점검 행, 정답 행). 점검 행에는 모델을 쓰지 않고, 60행 전체 순서를 고정 seed로 섞는다.
    정답 행은 점검 번호 → id, 모델이다.
    """
    by_id = {r["id"]: r["input"] for r in inputs}
    rows = [(i, m) for i in human_sample(inputs) for m in HUMAN_MODELS]
    random.Random(HUMAN_SHUFFLE_SEED).shuffle(rows)
    blind, key = [], []
    for k, (i, m) in enumerate(rows, 1):
        rid = f"R{k:02d}"
        blind.append({"점검번호": rid, "id": i, "input": by_id[i], "해설": outputs.get(m, {}).get(i) or "(출력 없음)"})
        key.append({"점검번호": rid, "id": i, "model": m})
    return blind, key
