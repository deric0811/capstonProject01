"""KAMIS 토마토 일별 도매/소매 가격(기본: 최근 1년)을 받아 data/raw/에 CSV로 저장한다.

API: periodWholesaleProductList (16번, 도매) / periodRetailProductList (17번, 소매). 기간 최대 1년.
인증: .env의 KAMIS_API_KEY(p_cert_key), KAMIS_CERT_ID(p_cert_id). 키는 출력하지 않는다.

사용법: python3 scripts/fetch_kamis.py [--market wholesale|retail]
        [--start YYYY-MM-DD] [--end YYYY-MM-DD] [--dry-run]
"""
import argparse
import csv
import datetime as dt
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
URL = "https://www.kamis.or.kr/service/price/xml.do"

# 코드표(productInfo) 기준: 채소류 / 토마토 / 품종 00 / 도매 5kg / 등급 04, 05
ITEM = {"p_itemcategorycode": "200", "p_itemcode": "225", "p_kindcode": "00"}
RANKS = ["04", "05"]
ACTIONS = {"wholesale": "periodWholesaleProductList", "retail": "periodRetailProductList"}
DELAY_SEC = 2  # 요청 사이 간격
FIELDS = ["productrankcode", "itemname", "kindname", "countyname", "marketname", "yyyy", "regday", "price"]


def load_env(path):
    env = {}
    for line in path.read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip("\"'")
    return env


def fetch(params, secrets):
    url = URL + "?" + urllib.parse.urlencode(params)
    try:
        body = urllib.request.urlopen(url, timeout=60).read().decode("utf-8")
    except Exception as e:
        msg = str(e)
        for s in secrets:
            msg = msg.replace(s, "***")
        sys.exit(f"요청 실패: {type(e).__name__}: {msg}")
    return json.loads(body)


def main():
    yesterday = dt.date.today() - dt.timedelta(days=1)
    ap = argparse.ArgumentParser()
    ap.add_argument("--end", default=yesterday.isoformat())
    ap.add_argument("--start")
    ap.add_argument("--market", choices=ACTIONS, default="wholesale")
    ap.add_argument("--dry-run", action="store_true", help="행 수만 출력하고 저장하지 않음")
    args = ap.parse_args()
    end = dt.date.fromisoformat(args.end)
    start = dt.date.fromisoformat(args.start) if args.start else end - dt.timedelta(days=364)

    env = load_env(ROOT / ".env")
    key, cert_id = env.get("KAMIS_API_KEY", ""), env.get("KAMIS_CERT_ID", "")
    if not key or not cert_id:
        sys.exit(".env에 KAMIS_API_KEY와 KAMIS_CERT_ID가 모두 필요합니다.")

    rows = []
    for i, rank in enumerate(RANKS):
        if i:
            time.sleep(DELAY_SEC)
        params = {
            "action": ACTIONS[args.market],
            "p_cert_key": key,
            "p_cert_id": cert_id,
            "p_returntype": "json",
            "p_startday": start.isoformat(),
            "p_endday": end.isoformat(),
            "p_productrankcode": rank,
            "p_convert_kg_yn": "N",  # 조사 단위(5kg) 그대로
            **ITEM,
        }
        data = fetch(params, [key, cert_id]).get("data", {})
        code = data.get("error_code") if isinstance(data, dict) else None
        if code == "001":
            print(f"등급 {rank}: 데이터 없음")
            continue
        if code != "000":
            sys.exit(f"등급 {rank}: API 오류 error_code={code}")
        items = data.get("item", [])
        if isinstance(items, dict):
            items = [items]
        for it in items:
            rows.append({"productrankcode": rank, **{f: it.get(f, "") for f in FIELDS[1:]}})
        days = sorted({(it.get("yyyy", ""), it.get("regday", "")) for it in items if it.get("countyname") != "평년"})
        span = f" ({'-'.join(days[0])} ~ {'-'.join(days[-1])})" if days else ""
        print(f"등급 {rank}: {len(items)}행{span}")

    if args.dry_run:
        return

    out = ROOT / "data" / "raw" / f"kamis_{args.market}_tomato_{start:%Y%m%d}_{end:%Y%m%d}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    print(f"저장: {out.relative_to(ROOT)} ({len(rows)}행)")


if __name__ == "__main__":
    main()
