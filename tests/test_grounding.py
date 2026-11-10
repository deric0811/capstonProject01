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
    assert r == {"pass": True, "a": True, "b": True, "c": True, "format": True, "errors": []}


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


# 증류 평가 채점 (spec §6.3)
def test_scoring_counts_missing_as_fail_and_decides_by_threshold():
    from tomato.explain import scoring

    inputs = [{"id": f"x{k}", "input": X} for k in range(10)]
    s, per = scoring.score(inputs, {f"x{k}": GOOD for k in range(9)})
    assert s["n"] == 10 and s["missing"] == 1 and s["pass"] == 0.9 and per["x9"]["pass"] is False
    base, per_b = scoring.score(inputs, {"x0": GOOD})
    d = scoring.decide({"student_lora": s, "student_base": base})
    assert d["adopt_student"] and d["explain"] == "student" and d["distill_effect_pts"] == 80.0
    assert scoring.paired(per_b, per) == {"both": 1, "only_base": 0, "only_lora": 8, "neither": 1}
    s2, _ = scoring.score(inputs, {f"x{k}": GOOD for k in range(8)})
    assert scoring.decide({"student_lora": s2, "student_base": base})["explain"] == "template"


def test_human_sample_is_fixed():
    from tomato.explain import scoring

    inputs = [{"id": f"h3-{k:04d}"} for k in range(934)]
    a = scoring.human_sample(inputs)
    assert len(a) == 30 and a == scoring.human_sample(inputs)
