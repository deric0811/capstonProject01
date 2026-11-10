"""증류 평가 지표와 채택 판정 (spec §6.3, 결과를 보기 전에 고정).

- 분모는 평가 입력 전체(934개). 출력이 없는 입력은 모든 규칙에서 실패로 센다.
- 통과율 = 근거 검사 pass(a and b and c) 비율. 규칙별 a·b·c와 형식 준수율을 따로 낸다.
- 채택: (ii) LoRA 학생 통과율 >= 0.90이면 explain에 학생을 쓴다. 미달이면 템플릿 유지.
- 증류 효과: (ii) - (i) 통과율 차이와 짝지은 개수(둘 다 통과, (i)만, (ii)만, 둘 다 실패).
"""
import random

from tomato.explain import grounding

MODELS = ("student_base", "student_lora", "teacher")
ADOPT_THRESHOLD = 0.90
HUMAN_N, HUMAN_SEED = 30, 20261111
RULES = ("pass", "a", "b", "c", "format")


def score(inputs, outputs):
    """inputs = [{id, input}], outputs = {id: text}. (요약, id별 결과)."""
    per = {}
    for r in inputs:
        text = outputs.get(r["id"])
        per[r["id"]] = grounding.check(text, r["input"]) if text else {k: False for k in RULES} | {"errors": ["출력 없음"]}
    n = len(inputs)
    return {"n": n, "missing": sum(r["id"] not in outputs for r in inputs),
            **{k: round(sum(c[k] for c in per.values()) / n, 4) for k in RULES}}, per


def paired(per_i, per_ii):
    keys = per_i.keys()
    return {
        "both": sum(per_i[k]["pass"] and per_ii[k]["pass"] for k in keys),
        "only_base": sum(per_i[k]["pass"] and not per_ii[k]["pass"] for k in keys),
        "only_lora": sum(per_ii[k]["pass"] and not per_i[k]["pass"] for k in keys),
        "neither": sum(not per_i[k]["pass"] and not per_ii[k]["pass"] for k in keys),
    }


def decide(summary):
    rate = summary["student_lora"]["pass"]
    return {"adopt_student": rate >= ADOPT_THRESHOLD, "student_lora_pass": rate, "threshold": ADOPT_THRESHOLD,
            "explain": "student" if rate >= ADOPT_THRESHOLD else "template",
            "distill_effect_pts": round(100 * (rate - summary["student_base"]["pass"]), 1)}


def human_sample(inputs):
    return sorted(random.Random(HUMAN_SEED).sample([r["id"] for r in inputs], HUMAN_N))
