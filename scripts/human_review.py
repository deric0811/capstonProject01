"""사람 점검 (spec §6.3, 2026-11-12 개정. 채택 판정에는 쓰지 않는다).

같은 30개 평가 입력(seed 20261111)에 대해 (i) 학생 원본과 (ii) LoRA 학생 출력을 둘 다 점검한다.
어느 모델 출력인지 가리고 60행 순서를 섞은 점검 파일과, 나중에 맞춰 보는 정답 파일을 따로 만든다.

1) 만들기 (score_distill.py와 같은 distill/eval/*.jsonl을 읽는다)
   uv run python scripts/human_review.py make
   → distill/eval/human/review.csv (점검용, 모델 표시 없음), distill/eval/human/key.csv (정답, 점검 끝날 때까지 열지 않는다)
2) review.csv의 사실_오류·근거없는_원인·어색한_문장 칸에 오류 개수(없으면 0)와 메모를 적는다.
3) 맞춰 보기
   uv run python scripts/human_review.py merge → distill/eval/human/summary.json
"""
import argparse
import csv
import json
import sys

from tomato import config
from tomato.explain import scoring

D = config.ROOT / "distill"
H = D / "eval" / "human"
ERR_COLS = ("사실_오류", "근거없는_원인", "어색한_문장")


def read(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in open(path, encoding="utf-8") if line.strip()]


def make(force=False):
    inputs = read(D / "inputs" / "eval.jsonl")
    assert len(inputs) == 934, len(inputs)
    outputs = {m: {r["id"]: r["text"] for r in read(D / "eval" / f"{m}.jsonl")} for m in scoring.HUMAN_MODELS}
    for m, o in outputs.items():
        if not o:
            sys.exit(f"distill/eval/{m}.jsonl이 없다. Colab 04 결과를 가져온 뒤 실행한다.")
    review, key = H / "review.csv", H / "key.csv"
    if review.exists() and not force:
        sys.exit(f"{review}가 이미 있다(점검 내용을 덮어쓰지 않는다). 다시 만들려면 --force.")
    blind, answers = scoring.human_blind(inputs, outputs)
    H.mkdir(parents=True, exist_ok=True)
    with open(review, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["점검번호", "id", "기준일", "현재가", "예상가", "등락률(%)", "20거래일 추이", "계절 중앙값", "시장 수",
                    "해설", *ERR_COLS, "메모"])
        for b in blind:
            x = b["input"]
            t, s, mk = x.get("trend20") or {}, x.get("seasonal") or {}, x.get("markets") or {}
            w.writerow([b["점검번호"], b["id"], x["origin_date"], x["y_origin"], x["y_hat"], x["change_pct"],
                        f"{t.get('start_price')}원에서 {t.get('change_pct')}% (최저 {t.get('min')}, 최고 {t.get('max')})" if t else "",
                        f"{s.get('month')}월 {s.get('median')} ({s.get('vs_median_pct')}%)" if s else "",
                        f"{mk.get('prev')}→{mk.get('today')}" if mk else "", b["해설"], "", "", "", ""])
    with open(key, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["점검번호", "id", "model"])
        w.writeheader()
        w.writerows(answers)
    print(f"{review} ({len(blind)}행, 모델 가림)\n{key} (정답, 점검이 끝날 때까지 열지 않는다)")
    return 0


def merge():
    with open(H / "review.csv", encoding="utf-8-sig") as f:
        review = {r["점검번호"]: r for r in csv.DictReader(f)}
    with open(H / "key.csv", encoding="utf-8") as f:
        key = {r["점검번호"]: r for r in csv.DictReader(f)}
    assert review.keys() == key.keys(), "점검 파일과 정답 파일의 점검번호가 다르다"
    blank = [k for k, r in review.items() if any(not r[c].strip() for c in ERR_COLS)]
    if blank:
        sys.exit(f"오류 칸이 빈 행이 있다(없으면 0): {', '.join(blank[:10])}")
    out = {}
    for m in scoring.HUMAN_MODELS:
        rows = [review[k] for k, v in key.items() if v["model"] == m]
        counts = {c: sum(int(r[c]) for r in rows) for c in ERR_COLS}
        out[m] = {"n": len(rows), **counts, "rows_with_error": sum(any(int(r[c]) for c in ERR_COLS) for r in rows)}
    (H / "summary.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("make", "merge"))
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    return make(a.force) if a.cmd == "make" else merge()


if __name__ == "__main__":
    sys.exit(main())
