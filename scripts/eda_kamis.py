"""KAMIS 토마토 원본(data/raw/) 점검: 단위, 공표가 대조, 그래프, 결측.

사용법: .venv/bin/python scripts/eda_kamis.py [--skip-api]
결과: 표준출력 요약 + docs/research/eda/*.png
"""
import argparse
import collections
import csv
import datetime as dt
import glob
import json
import statistics
import time
import urllib.parse
import urllib.request
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "research" / "eda"
URL = "https://www.kamis.or.kr/service/price/xml.do"
YEAR_ROUND_FROM = dt.date(2002, 11, 1)
plt.rcParams["font.family"] = ["Noto Sans CJK JP", "sans-serif"]  # 같은 ttc에 한글 글리프 포함


DASH = collections.Counter()  # (market, countyname) -> 가격이 "-"인 행 수


def load(market):
    rows = []
    for f in sorted(glob.glob(str(ROOT / "data" / "raw" / f"kamis_{market}_tomato_*.csv"))):
        with open(f, encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                if r["countyname"] == "평년":
                    continue
                m, d = r["regday"].split("/")
                r["date"] = dt.date(int(r["yyyy"]), int(m), int(d))
                if r["price"].strip() == "-":
                    DASH[(market, r["countyname"], r["date"] >= YEAR_ROUND_FROM)] += 1
                    continue
                r["price"] = int(r["price"].replace(",", ""))
                rows.append(r)
    return rows


def unit_changes(rows):
    """연도·등급별 kindname(단위 포함) 집합. 시장 행만 kindname이 채워져 있다."""
    by = collections.defaultdict(collections.Counter)
    for r in rows:
        if r["countyname"] != "평균":
            by[(r["date"].year, r["productrankcode"])][r["kindname"]] += 1
    return dict(sorted(by.items()))


def average_series(rows, rank="04", since=None):
    s = {r["date"]: r["price"] for r in rows
         if r["countyname"] == "평균" and r["productrankcode"] == rank and (since is None or r["date"] >= since)}
    return dict(sorted(s.items()))


def gaps(rows, since):
    trade_days = {r["date"] for r in rows if r["countyname"] != "평균" and r["date"] >= since}
    avg_days = {r["date"] for r in rows if r["countyname"] == "평균" and r["productrankcode"] == "04" and r["date"] >= since}
    days = sorted(trade_days | avg_days)
    longest, at = 0, None
    for a, b in zip(days, days[1:]):
        if (b - a).days - 1 > longest:
            longest, at = (b - a).days - 1, (a, b)
    return len(trade_days - avg_days), sorted(trade_days - avg_days), longest, at


def published_price(regday, env):
    key, cid = env["KAMIS_API_KEY"], env["KAMIS_CERT_ID"]
    q = {"action": "dailyPriceByCategoryList", "p_product_cls_code": "02", "p_item_category_code": "200",
         "p_regday": regday.isoformat(), "p_convert_kg_yn": "N",
         "p_cert_key": key, "p_cert_id": cid, "p_returntype": "json"}
    body = urllib.request.urlopen(URL + "?" + urllib.parse.urlencode(q), timeout=60).read().decode("utf-8")
    data = json.loads(body).get("data", {})
    for it in data.get("item", []) if isinstance(data, dict) else []:
        if it.get("item_code") == "225" and it.get("rank_code") == "04":
            return it.get("day1"), int(it["dpr1"].replace(",", ""))
    return None, None


def load_env():
    env = {}
    for line in (ROOT / ".env").read_text().splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip("\"'")
    return env


def plot(series):
    OUT.mkdir(parents=True, exist_ok=True)
    xs, ys = list(series), list(series.values())
    fig, ax = plt.subplots(figsize=(11, 4))
    ax.plot(xs, ys, lw=0.6, color="#c0392b")
    ax.set_title("토마토 도매 평균가격(상품, 5kg) 일별, 2002-11 ~ 2026-10")
    ax.set_ylabel("원 / 5kg")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT / "wholesale_daily.png", dpi=130)
    plt.close(fig)

    by_month = collections.defaultdict(list)
    for d, p in series.items():
        by_month[d.month].append(p)
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.boxplot([by_month[m] for m in range(1, 13)], tick_labels=[f"{m}월" for m in range(1, 13)], showfliers=False)
    ax.plot(range(1, 13), [statistics.median(by_month[m]) for m in range(1, 13)], color="#c0392b", marker="o", lw=1)
    ax.set_title("월별 분포: 토마토 도매 평균가격(상품, 5kg), 2002-11 ~ 2026-10")
    ax.set_ylabel("원 / 5kg")
    ax.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(OUT / "wholesale_monthly.png", dpi=130)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-api", action="store_true")
    args = ap.parse_args()

    data = {m: load(m) for m in ("wholesale", "retail")}

    print("## 1. 연도·등급별 kindname")
    for m, rows in data.items():
        prev = {}
        for (year, rank), c in unit_changes(rows).items():
            names = sorted(c)
            if prev.get(rank) != names:
                print(f"{m} {year} 등급{rank}: {dict(c)}")
            prev[rank] = names

    series = average_series(data["wholesale"])
    print("\n## 2. 공표가 대조 (도매 평균, 상품)")
    if not args.skip_api:
        env = load_env()
        picks = [d for d in series if d >= YEAR_ROUND_FROM]
        picks = [picks[int(i * (len(picks) - 1) / 5)] for i in range(5)]  # 이미 대조한 마지막 날 제외
        for d in picks:
            label, price = published_price(d, env)
            print(f"{d} csv={series[d]} api={price} label={label} {'일치' if price == series[d] else '불일치'}")
            time.sleep(3)

    print("\n## 3. 그래프")
    plot(average_series(data["wholesale"], since=YEAR_ROUND_FROM))
    print("저장:", *sorted(p.name for p in OUT.glob("*.png")))

    print("\n## 4. 결측 (2002-11 이후)")
    print("가격 '-' 행 (market, county, 2002-11 이후):", dict(DASH))
    for m, rows in data.items():
        n, missing, longest, at = gaps(rows, YEAR_ROUND_FROM)
        print(f"{m}: 평균 행 없는 거래일 {n}일 {[str(d) for d in missing[:10]]} / 최장 무거래 {longest}일 {at}")


if __name__ == "__main__":
    main()
