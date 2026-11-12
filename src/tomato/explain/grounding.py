"""LLM 해설 근거 검사 (spec §6). 규칙 (a) 숫자, (b) 입력에 없는 원인, (c) 문장 수·필수 문구, 그리고 출력 형식.

통과(pass) = a and b and c. 형식(format)은 따로 센다. 실제 explain에서는 pass와 format을 모두 만족해야 LLM 문장을 쓴다.
(a)는 숫자 근거(a_numbers)와 계절 중앙값 표기(a_median)로 이루어지고, 둘 다 따로 집계한다(2026-11-12 개정).

(a) 숫자 허용 범위
- 출력의 모든 숫자는 입력 JSON의 값(부호 무시), 입력 날짜의 연·월·일, 고정 상수 CONSTANTS 중 하나여야 한다.
- 금액(뒤에 '원'): 입력 값과 같거나, 입력 값을 10원·100원·1,000원 단위로 반올림한 값. "1만 7,763원", "1.8만 원",
  "1만 8천 원"처럼 '만'·'천' 단위 표기는 원 단위로 바꿔 같은 규칙을 쓴다.
- 백분율(뒤에 '%' 또는 '퍼센트'): 입력 값(소수 첫째 자리)과 같거나, 정수로 반올림한 값(차이 0.5 이하).
- 날짜: YYYY-MM-DD, YYYY년 M월 D일, M월 D일, M/D, YYYY년 M월, M월, YYYY년은 입력 날짜·seasonal.month와 맞아야 한다.
- 그 밖의 숫자(거래일, 곳, 회 등): 입력 값 또는 상수와 정확히 같아야 한다.
- 식별자: 입력 JSON에 문자열로 그대로 있는 영문+숫자 식별자(예: model "chronos2")는 숫자 검사에서 뺀다.
  정확히 같은 문자열만 빼고(앞뒤가 영문·숫자가 아니어야 함), 그 밖의 허용 범위는 넓히지 않는다(2026-11-12).
- 한계: 값이 맞으면 어느 항목의 값인지는 보지 않는다(최저가를 최고가라고 해도 통과). 한글로 쓴 수("세 거래일")는 잡지 못한다.

(a) 계절 중앙값 표기 (a_median, 2026-11-12 개정. 학습용 입력 시험에서 발견, 평가 결과 보기 전)
- seasonal.median 금액(그대로 또는 10·100·1,000원 반올림, '만'·'천' 표기 포함)이 나오는 문장에는 "중앙값"이 있어야 한다.
- 그 금액이 다른 입력 금액과 정확히 같으면 어느 값인지 알 수 없으므로 검사하지 않는다.
- 한계: 중앙값을 반올림한 값이 다른 입력 금액의 반올림과 겹치면 다른 값을 말한 문장도 걸릴 수 있다.
  문장 나누기는 sentences()와 같다.

(b) 입력에 없는 원인: FORBIDDEN의 낱말이 나오면 실패. 한계는 docs/research/distill-precheck.md 참고.
(c) 문장 4~6개, 예상가격, 현재가와 차이, 주요 요인(추이·계절·시장 수의 숫자 하나 이상), 주의 문구, 틀릴 수 있다는 문구.
"""
import re

CONSTANTS = {5: "5kg 단위", 20: "최근 20거래일 창", 2023: "성능 평가 시작 연도"}
ROUND_UNITS = (10, 100, 1000)
MIN_SENTENCES, MAX_SENTENCES = 4, 6

FORBIDDEN = (
    "날씨", "기상", "기후", "기온", "더위", "추위", "폭염", "한파", "냉해", "태풍", "장마", "폭우", "호우", "강우", "강수",
    "가뭄", "일조", "작황", "생산량", "생산 감소", "생산 증가", "출하량", "출하 물량", "반입량", "재배", "수확",
    "병해", "병충해", "해충", "산지", "수입", "수출", "환율", "유가", "물가", "인건비", "물류비", "운송비", "정책", "정부",
    "뉴스", "보도", "명절", "추석", "설날", "설 연휴", "김장", "휴가철", "수요", "공급", "수급", "소비 심리", "소비량",
    "재고",
)
CAUTION = re.compile(r"주의|유의|참고|감안|조심")
UNCERTAIN = re.compile(r"틀릴 수|다를 수|빗나갈 수|어긋날 수|오차가 (있을|생길|날) 수|보장(하지|할 수 없|되지)")
FORMAT_BAD = re.compile(r"(^|\n)\s*([-*•#>]|\d+[.)]\s)|\*\*|```|</?think>|<\|")

_NUM = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?"
_MAN = re.compile(rf"({_NUM})\s*만\s*(?:({_NUM})\s*(천)?)?\s*원")
_CHEON = re.compile(rf"({_NUM})\s*천\s*원")
_DATE_PATTERNS = (
    (re.compile(r"(\d{4})[-./](\d{1,2})[-./](\d{1,2})"), ("y", "m", "d")),
    (re.compile(r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일"), ("y", "m", "d")),
    (re.compile(r"(\d{4})년\s*(\d{1,2})월"), ("y", "m")),
    (re.compile(r"(\d{1,2})월\s*(\d{1,2})일"), ("m", "d")),
    (re.compile(r"(?<![\d.,])(\d{1,2})/(\d{1,2})(?![\d/])"), ("m", "d")),
    (re.compile(r"(\d{1,2})월"), ("m",)),
    (re.compile(r"(\d{4})년"), ("y",)),
)
_TOKEN = re.compile(rf"(?<![\d.,])({_NUM})\s*(원|%|퍼센트|kg)?")


def _num(s):
    return float(s.replace(",", ""))


def _leaves(x, path=""):
    if isinstance(x, dict):
        for k, v in x.items():
            yield from _leaves(v, f"{path}.{k}" if path else k)
    elif isinstance(x, bool) or x is None:
        return
    elif isinstance(x, (int, float)):
        yield path, abs(float(x))
    elif isinstance(x, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", x):
        yield path, x


def facts(x):
    """입력에서 허용 숫자와 날짜를 뽑는다. values = [(경로, 값)], dates = [(y, m, d)]."""
    values, dates, months = [], [], set()
    for path, v in _leaves(x):
        if isinstance(v, str):
            y, m, d = (int(p) for p in v.split("-"))
            dates.append((y, m, d))
            months.add(m)
        else:
            values.append((path, v))
    if isinstance(x.get("seasonal"), dict) and x["seasonal"].get("month"):
        months.add(int(x["seasonal"]["month"]))
    return {"values": values, "dates": dates, "months": months, "years": {y for y, _, _ in dates} | {2023}}


def _amount_ok(n, v):
    if n == v:
        return True
    return any(n % u == 0 and abs(n - v) <= u / 2 for u in ROUND_UNITS)


def _pct_ok(n, v):
    return abs(n - round(v, 1)) < 1e-9 or (float(n).is_integer() and abs(n - v) <= 0.5)


def _match(n, kind, f):
    """일치하는 입력 경로들. 상수와 맞으면 'const'."""
    hits = set()
    for path, v in f["values"]:
        if (kind == "amount" and _amount_ok(n, v)) or (kind == "pct" and _pct_ok(n, v)) or (kind == "plain" and n == v):
            hits.add(path)
    if kind == "plain" and n in CONSTANTS:
        hits.add("const")
    return hits


def _date_ok(parts, f):
    if set(parts) == {"m"}:
        return parts["m"] in f["months"]
    if set(parts) == {"y"}:
        return parts["y"] in f["years"]
    return any(all(parts[k] == {"y": y, "m": m, "d": d}[k] for k in parts) for y, m, d in f["dates"])


_IDENT = re.compile(r"(?=[A-Za-z0-9_.\-]*[A-Za-z])(?=[A-Za-z0-9_.\-]*\d)[A-Za-z0-9_.\-]+")


def identifiers(x):
    """입력 JSON의 문자열 값 중 영문과 숫자가 함께 있는 식별자(예: "chronos2")."""
    found = set()
    if isinstance(x, dict):
        for v in x.values():
            found |= identifiers(v)
    elif isinstance(x, list):
        for v in x:
            found |= identifiers(v)
    elif isinstance(x, str) and _IDENT.fullmatch(x):
        found.add(x)
    return found


def strip_identifiers(text, x):
    for ident in sorted(identifiers(x), key=len, reverse=True):
        text = re.sub(rf"(?<![A-Za-z0-9]){re.escape(ident)}(?![A-Za-z0-9])", " ", text)
    return text


def _amounts(text):
    """문장 안의 금액(원). '만'·'천' 표기를 원 단위로 바꾼다."""
    out = []
    for mt in _MAN.finditer(text):
        out.append(_num(mt.group(1)) * 10000 + (_num(mt.group(2)) * (1000 if mt.group(3) else 1) if mt.group(2) else 0))
    text = _MAN.sub(" ", text)
    out += [_num(mt.group(1)) * 1000 for mt in _CHEON.finditer(text)]
    text = _CHEON.sub(" ", text)
    out += [_num(mt.group(1)) for mt in _TOKEN.finditer(text) if mt.group(2) == "원"]
    return out


def check_median_label(text, x):
    """(통과 여부, 오류 목록). seasonal.median 금액이 나오는 문장에 '중앙값'이 있어야 한다."""
    med = (x.get("seasonal") or {}).get("median")
    if med is None:
        return True, []
    others = {v for path, v in facts(x)["values"] if path != "seasonal.median"}
    errors = []
    for sent in sentences(strip_identifiers(text, x)):
        hits = [n for n in _amounts(sent) if _amount_ok(n, abs(float(med))) and n not in others]
        if hits and "중앙값" not in sent:
            errors.append(f"계절 중앙값 {int(hits[0]):,}원을 '중앙값'이라고 쓰지 않음")
    return not errors, errors


def check_numbers(text, x):
    """(통과 여부, 오류 목록, 맞은 입력 경로 집합)."""
    f, errors, hits = facts(x), [], set()
    rest = strip_identifiers(text, x)
    for pat, keys in _DATE_PATTERNS:
        for mt in pat.finditer(rest):
            parts = dict(zip(keys, (int(g) for g in mt.groups()), strict=True))
            if not _date_ok(parts, f):
                errors.append(f"날짜 '{mt.group(0)}'이 입력에 없음")
        rest = pat.sub(" ", rest)
    for mt in _MAN.finditer(rest):
        n = _num(mt.group(1)) * 10000 + (_num(mt.group(2)) * (1000 if mt.group(3) else 1) if mt.group(2) else 0)
        h = _match(n, "amount", f)
        hits |= h
        if not h:
            errors.append(f"금액 '{mt.group(0)}'이 입력에 없음")
    rest = _MAN.sub(" ", rest)
    for mt in _CHEON.finditer(rest):
        h = _match(_num(mt.group(1)) * 1000, "amount", f)
        hits |= h
        if not h:
            errors.append(f"금액 '{mt.group(0)}'이 입력에 없음")
    rest = _CHEON.sub(" ", rest)
    for mt in _TOKEN.finditer(rest):
        n, unit = _num(mt.group(1)), mt.group(2)
        if unit == "kg":
            if n not in CONSTANTS:
                errors.append(f"'{mt.group(0)}'이 입력에 없음")
            continue
        kind = "amount" if unit == "원" else "pct" if unit in ("%", "퍼센트") else "plain"
        h = _match(n, kind, f)
        hits |= h
        if not h:
            errors.append(f"숫자 '{mt.group(0).strip()}'이 입력에 없음")
    return not errors, errors, hits


RAIN = re.compile(r"(?<![가-힣])비(가|를|는| 소식| 때문| 영향)")  # '대비가', '준비가'는 제외


def check_causes(text):
    found = [w for w in FORBIDDEN if w in text] + (["비"] if RAIN.search(text) else [])
    return not found, [f"입력에 없는 원인 '{w}'" for w in found]


def sentences(text):
    parts = re.split(r"(?<=[.!?])\s+|\n+", text.strip())
    return [p for p in parts if p.strip()]


FACTOR_PATHS = ("trend20.change_pct", "trend20.start_price", "trend20.min", "trend20.max",
                "seasonal.median", "seasonal.vs_median_pct", "markets.today", "markets.prev")


def check_structure(text, x, hits):
    errors = []
    n = len(sentences(text))
    if not MIN_SENTENCES <= n <= MAX_SENTENCES:
        errors.append(f"문장 수 {n}개 (4~6개)")
    if "y_hat" not in hits:
        errors.append("예상가격 없음")
    if "y_origin" not in hits or not ({"diff", "change_pct"} & hits):
        errors.append("현재가와 차이 없음")
    if not set(FACTOR_PATHS) & hits:
        errors.append("주요 요인(추이·계절·시장 수) 없음")
    if not CAUTION.search(text):
        errors.append("주의사항 문구 없음")
    if not UNCERTAIN.search(text):
        errors.append("예측이 틀릴 수 있다는 문구 없음")
    return not errors, errors


def check_format(text):
    errors = []
    if FORMAT_BAD.search(text):
        errors.append("목록·제목·강조·사고 태그 등 평문이 아님")
    if not 80 <= len(text) <= 800:
        errors.append(f"길이 {len(text)}자 (80~800자)")
    letters = [c for c in text if c.isalpha()]
    hangul = sum("가" <= c <= "힣" for c in letters)
    if not letters or hangul / len(letters) < 0.5:
        errors.append("한국어가 아님")
    return not errors, errors


def check(text, x):
    an, ea, hits = check_numbers(text, x)
    am, em = check_median_label(text, x)
    a = an and am
    b, eb = check_causes(text)
    c, ec = check_structure(text, x, hits)
    fm, ef = check_format(text)
    return {"pass": a and b and c, "a": a, "a_numbers": an, "a_median": am, "b": b, "c": c, "format": fm,
            "errors": ea + em + eb + ec + ef}
