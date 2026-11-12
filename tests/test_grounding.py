"""LLM 해설 근거 검사 (spec §6): (a) 숫자, (b) 입력에 없는 원인, (c) 문장 수·필수 문구, 형식."""
import pytest

from tomato.explain import grounding, prompt

X = {
    "origin_date": "2026-11-10", "target_date_est": "2026-11-13", "horizon_tdays": 3, "model": "chronos2",
    "y_origin": 17900, "y_hat": 17763, "diff": -137, "change_pct": -0.8, "direction": "flat",
    "trend20": {"start_date": "2026-10-13", "start_price": 15200, "change_pct": 17.8, "min": 14800, "max": 18400},
    "seasonal": {"month": 11, "median": 16250, "vs_median_pct": 10.2},
    "markets": {"today": 5, "prev": 4},
    "performance": {"mae": 1412, "mape": 6.3, "n": 934, "mae_reduction_pct": 9.1},
}

GOOD = (
    "11월 13일 예상가격은 17,763원입니다. 현재가 17,900원보다 137원(0.8%) 낮은 수준입니다. "
    "최근 20거래일 동안 15,200원에서 17.8% 올랐고, 과거 11월 중앙값 16,250원보다 10.2% 높습니다. "
    "오늘은 가격을 낸 시장이 5곳으로 직전 거래일 4곳과 달라 평균이 흔들릴 수 있으니 주의하세요. "
    "이 모델의 평균 오차는 1,412원이며 예측은 틀릴 수 있습니다."
)


def test_good_text_passes_all_rules():
    r = grounding.check(GOOD, X)
    assert r == {"pass": True, "a": True, "a_numbers": True, "a_median": True, "b": True, "c": True,
                 "c_caution": True, "format": True, "perf_caution": False, "errors": []}


# (a) 계절 중앙값 표기 (2026-11-12 개정, 학습용 입력 시험에서 발견)
@pytest.mark.parametrize("sent,ok", [
    ("과거 11월 중앙값 16,250원보다 높습니다.", True),
    ("과거 11월 평균 가격 16,250원보다 높습니다.", False),
    ("11월 과거 가격 16,300원보다 높습니다.", False),        # 100원 반올림도 중앙값 금액으로 본다
    ("11월의 과거 수준인 1만 6천 원보다 높습니다.", False),   # '만'·'천' 표기
    ("현재가 17,900원은 높은 편입니다.", True),               # 중앙값이 아닌 금액
])
def test_median_label_required_in_sentence(sent, ok):
    r = grounding.check_median_label(sent, X)
    assert r[0] is ok, r


def test_median_label_is_part_of_rule_a_and_counted_separately():
    bad = GOOD.replace("과거 11월 중앙값 16,250원", "과거 11월 평균 가격 16,250원")
    r = grounding.check(bad, X)
    assert r["a_numbers"] and not r["a_median"] and not r["a"] and not r["pass"]
    assert "중앙값" in " ".join(r["errors"])


def test_median_label_skipped_when_null_or_ambiguous():
    assert grounding.check_median_label("과거 평균 16,250원입니다.", X | {"seasonal": {"month": 11, "median": None,
                                                                              "vs_median_pct": None}})[0]
    # 중앙값이 현재가와 정확히 같으면 어느 값인지 알 수 없으므로 검사하지 않는다
    same = X | {"seasonal": {"month": 11, "median": 17900, "vs_median_pct": 0.0}}
    assert grounding.check_median_label("현재가는 17,900원입니다.", same)[0]


# (a) 입력 JSON의 영문+숫자 식별자는 숫자 검사에서 뺀다 (2026-11-12 오탐 수정)
def test_identifier_in_input_is_not_a_number():
    assert grounding.identifiers(X) == {"chronos2"}
    assert grounding.check_numbers("이 예측은 chronos2 모델로 만들었습니다.", X)[0]
    assert grounding.check_numbers("이 예측은 chronos2모델로 만들었습니다.", X)[0]


@pytest.mark.parametrize("text", ["chronos7 모델입니다.", "Chronos2 모델입니다.", "chronos22 모델입니다.", "gpt8 모델입니다.",
                                  "x2 배입니다."])  # 7·8·22·2는 입력에 없는 숫자
def test_identifier_exclusion_does_not_widen_other_numbers(text):
    assert not grounding.check_numbers(text, X)[0]


# (a) 숫자
@pytest.mark.parametrize("phrase", ["17,763원", "17,760원", "17,800원", "18,000원", "1만 7,763원", "1.8만 원", "1만 8천 원"])
def test_amount_exact_or_rounded_to_10_100_1000(phrase):
    ok, errors, hits = grounding.check_numbers(f"예상가격은 약 {phrase}입니다.", X)
    assert ok, errors
    assert "y_hat" in hits


@pytest.mark.parametrize("phrase", ["17,700원", "17,770원", "20,000원", "2만 원", "17,663원"])
def test_amount_not_in_input_fails(phrase):
    ok, errors, _ = grounding.check_numbers(f"예상가격은 {phrase}입니다.", X)
    assert not ok and errors


def test_derived_number_fails():
    # 최고가 - 최저가 = 3,600원은 입력에 없는 새 숫자
    ok, errors, _ = grounding.check_numbers("최근 20거래일 가격 폭은 3,600원이었습니다.", X)
    assert not ok


@pytest.mark.parametrize("phrase,ok", [("0.8%", True), ("1%", True), ("-0.8%", True), ("0.9%", False),
                                       ("17.8%", True), ("18%", True), ("17%", False), ("10.2퍼센트", True)])
def test_percent_exact_or_integer_rounding(phrase, ok):
    assert grounding.check_numbers(f"변화는 {phrase}입니다.", X)[0] is ok


@pytest.mark.parametrize("phrase,ok", [("2026-11-13", True), ("11월 13일", True), ("2026년 11월 13일", True),
                                       ("11/13", True), ("10월 13일", True), ("11월", True), ("11월 14일", False),
                                       ("12월", False), ("2025년", False), ("2023년", True)])
def test_dates_must_be_input_dates(phrase, ok):
    assert grounding.check_numbers(f"{phrase} 기준입니다.", X)[0] is ok


@pytest.mark.parametrize("phrase,ok", [("3거래일", True), ("20거래일", True), ("5곳", True), ("934회", True),
                                       ("5kg", True), ("7거래일", False), ("6곳", False), ("10kg", False)])
def test_plain_numbers_exact(phrase, ok):
    assert grounding.check_numbers(f"{phrase}입니다.", X)[0] is ok


# (b) 입력에 없는 원인
@pytest.mark.parametrize("word", ["비", "태풍", "폭염", "날씨", "수입", "작황", "출하량", "뉴스", "추석", "수요"])
def test_cause_not_in_input_fails(word):
    ok, errors = grounding.check_causes(f"{word}{"가 많이 온" if word == "비" else ""} 영향으로 가격이 오를 수 있습니다.")
    assert not ok and word in errors[0]
    assert grounding.check(GOOD.replace("주의하세요.", f"주의하세요. {word} 때문입니다."), X)["b"] is False


def test_input_based_reasons_are_allowed():
    assert grounding.check_causes("최근 20거래일 추이와 계절 비교, 시장 수 변화를 보면 대비가 필요합니다.")[0]


# (c) 문장 수와 필수 문구
def test_sentence_count_bounds():
    three = "예상가격은 17,763원입니다. 현재가 17,900원보다 137원 낮습니다. 최근 17.8% 올라 주의하고 틀릴 수 있습니다."
    r = grounding.check(three, X)
    assert not r["c"] and any("문장 수 3개" in e for e in r["errors"])
    seven = GOOD + " 참고하세요. 감사합니다."
    assert not grounding.check(seven, X)["c"]


def test_decimal_point_is_not_sentence_end():
    assert len(grounding.sentences("MAPE는 6.3%입니다. 오차는 1,412원입니다.")) == 2


@pytest.mark.parametrize("drop,msg", [
    ("11월 13일 예상가격은 17,763원입니다. ", "예상가격 없음"),
    ("현재가 17,900원보다 137원(0.8%) 낮은 수준입니다. ", "현재가와 차이 없음"),
    ("예측은 틀릴 수 있습니다.", "틀릴 수 있다는 문구 없음"),
])
def test_required_content(drop, msg):
    text = GOOD.replace(drop, "이 모델은 chronos2입니다. " if "틀릴" not in drop else "참고하세요.")
    r = grounding.check(text, X)
    assert not r["c"] and msg in " ".join(r["errors"])


def test_factor_and_caution_required():
    text = ("11월 13일 예상가격은 17,763원입니다. 현재가 17,900원보다 137원 낮습니다. 이 모델은 chronos2입니다. "
            "평균 오차는 1,412원입니다. 예측은 틀릴 수 있습니다.")
    errors = " ".join(grounding.check(text, X)["errors"])
    assert "주요 요인" in errors and "주의사항" in errors


# 형식
@pytest.mark.parametrize("bad", ["- " + GOOD, "**예상**: " + GOOD, "<think>계산</think>" + GOOD, "1. " + GOOD,
                                 "Price will be 17,763 won. " * 3])
def test_format_violations(bad):
    assert grounding.check(bad, X)["format"] is False


def test_prompt_carries_input_and_rules():
    m = prompt.messages(X)
    assert [x["role"] for x in m] == ["system", "user"]
    assert '"y_hat": 17763' in m[1]["content"]
    assert "4~6개" in m[0]["content"] and "틀릴 수" in m[0]["content"]
    for w in ("태풍", "날씨", "수입", "뉴스"):
        assert w in m[0]["content"]  # 금지어를 프롬프트로도 알린다


# (c) 주의 문장 (2026-11-12 개정, 학습용 입력 시험에서 발견): 성능 숫자가 있는 문장의 주의 단어는 세지 않는다
CAUTION_SENT = "오늘은 가격을 낸 시장이 5곳으로 직전 거래일 4곳과 달라 평균이 흔들릴 수 있으니 주의하세요. "


@pytest.mark.parametrize("perf_sent", [
    "이 모델의 평균 오차는 1,412원이므로 참고하시기 바랍니다. ",
    "직전가를 쓰는 방식보다 오차가 9.1% 작으니 참고하세요. ",
    "평균 백분율 오차 6.3%를 감안하세요. ",
    "934번 예측한 결과이니 유의하세요. ",
    "평균 오차는 약 1,400원이니 참고하세요. ",
])
def test_caution_in_performance_sentence_not_counted(perf_sent):
    text = GOOD.replace(CAUTION_SENT, perf_sent)
    r = grounding.check(text, X)
    assert r["a"] and r["b"]
    assert not r["c_caution"] and not r["c"] and not r["pass"] and r["perf_caution"]
    assert "성능 수치 문장에만" in " ".join(r["errors"])
    # 따로 쓴 주의 문장이 있으면 통과하지만 perf_caution은 센다
    r2 = grounding.check(GOOD.replace(CAUTION_SENT, CAUTION_SENT + perf_sent).replace("이 모델의 평균 오차는 1,412원이며 ", ""), X)
    assert r2["c_caution"] and r2["pass"] and r2["perf_caution"]


def test_caution_without_performance_numbers_counts():
    for sent in ("2023년 이후 성능이니 참고하세요. ", "과거 성적일 뿐이니 참고하세요. "):
        r = grounding.check(GOOD.replace(CAUTION_SENT, sent), X)
        assert r["c_caution"] and not r["perf_caution"], sent
    # performance가 null이면 성능 숫자가 없다
    x = X | {"performance": None}
    text = GOOD.replace("이 모델의 평균 오차는 1,412원이며 ", "")
    assert grounding.check(text, x)["c_caution"]


def test_prompt_v4_rules():
    sysm = prompt.SYSTEM
    assert prompt.PROMPT_VERSION == "v4"
    # 문장 구성 ①~⑥, 6문장 상한
    assert "전체 6문장을 넘기지 않는다" in sysm
    for mark in "①②③④⑤⑥":
        assert mark in sysm
    assert "시장 수가 그대로면 시장 수를 쓰지 않는다" in sysm and "빼도 된다" not in sysm
    assert "모델 성능은 한 문장으로만" in sysm
    # 주의 문장: 활용상 주의, '유의'·'참고', 숫자·성능 내용 없음, 별도 문장
    assert "활용상 주의만" in sysm and "'유의' 또는 '참고'" in sysm and "숫자와 성능 내용은 넣지 않는다" in sysm
    assert "④·⑥과 다른 별도의 문장" in sysm
    # 인과·전망·입력에 없는 요인 금지 (위험을 판단·예측하게 하는 지시는 없다)
    assert "인과를 만들지 않는다" in sysm and "스스로 전망하지 않는다" in sysm and '"외부 요인"' in sysm
    assert "입력에 근거한 주의" not in sysm
    # v2부터 유지
    assert '반드시 "중앙값"' in sysm and "model 값" in sysm
    assert "performance가 null이면 ④를 빼고 모델 성능을 말하지 않는다." in sysm


# 증류 평가 채점 (spec §6.3)
def test_scoring_counts_missing_as_fail_and_decides_by_threshold():
    from tomato.explain import scoring

    inputs = [{"id": f"x{k}", "input": X} for k in range(10)]
    s, per = scoring.score(inputs, {f"x{k}": GOOD for k in range(9)})
    assert s["n"] == 10 and s["missing"] == 1 and s["pass"] == 0.9 and per["x9"]["pass"] is False
    base, per_b = scoring.score(inputs, {"x0": GOOD})
    sm = {"student_lora": s, "student_base": base}
    d = scoring.decide(sm, demo_vram_gb=9.4)
    assert d["adopt_student"] and d["explain"] == "student" and d["distill_effect_pts"] == 80.0
    assert scoring.paired(per_b, per) == {"both": 1, "only_base": 0, "only_lora": 8, "neither": 1}
    # 채택 기준 2: 데모 서버 VRAM <= 10GB (경계 포함), 측정 전이면 보류
    assert scoring.decide(sm, demo_vram_gb=10.0)["adopt_student"]
    d = scoring.decide(sm, demo_vram_gb=10.01)
    assert not d["adopt_student"] and d["explain"] == "api_or_template"
    d = scoring.decide(sm)
    assert not d["adopt_student"] and d["explain"] == "pending_demo_vram"
    s2, _ = scoring.score(inputs, {f"x{k}": GOOD for k in range(8)})
    for v in (None, 9.0):
        assert scoring.decide({"student_lora": s2, "student_base": base}, v)["explain"] == "api_or_template"


def test_human_sample_is_fixed():
    from tomato.explain import scoring

    inputs = [{"id": f"h3-{k:04d}"} for k in range(934)]
    a = scoring.human_sample(inputs)
    assert len(a) == 30 and a == scoring.human_sample(inputs)


def test_human_blind_hides_model_and_shuffles():
    from tomato.explain import scoring

    inputs = [{"id": f"h3-{k:04d}", "input": X} for k in range(934)]
    outs = {"student_base": {r["id"]: "원본 " + r["id"] for r in inputs},
            "student_lora": {r["id"]: "로라 " + r["id"] for r in inputs}}
    blind, key = scoring.human_blind(inputs, outs)
    assert (blind, key) == scoring.human_blind(inputs, outs)  # seed 고정
    ids = scoring.human_sample(inputs)
    assert len(blind) == len(key) == 60 and sorted({b["id"] for b in blind}) == ids
    assert all("model" not in b for b in blind)
    assert sorted((k["id"], k["model"]) for k in key) == sorted((i, m) for i in ids for m in scoring.HUMAN_MODELS)
    for b, k in zip(blind, key, strict=True):
        assert b["점검번호"] == k["점검번호"] and b["해설"] == ("원본 " if k["model"] == "student_base" else "로라 ") + b["id"]
    # 섞였다: 모델 순서가 번갈아 고정되지 않고, 같은 입력의 두 출력이 늘 붙어 있지 않다
    models = [k["model"] for k in key]
    assert models != [m for _ in ids for m in scoring.HUMAN_MODELS]
    assert sum(key[t]["id"] == key[t + 1]["id"] for t in range(59)) < 30
