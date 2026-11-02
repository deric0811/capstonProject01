"""완료 기준 §11-2 확인: DB의 가격 있는 행과 `평균` 행이 data/raw CSV와 키·값 모두 일치하는지.

사용법: DATABASE_URL=postgresql://... uv run python scripts/check_backfill.py [--to 2026-10-28]
"""
import argparse
import csv
import datetime as dt
import glob
import os
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parent.parent
FROM = dt.date(2002, 11, 1)


def csv_rows(to):
    priced, dash = {}, 0
    for f in sorted(glob.glob(str(ROOT / "data" / "raw" / "kamis_wholesale_tomato_*.csv"))):
        with open(f, encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                m, d = r["regday"].split("/")
                day = dt.date(int(r["yyyy"]), int(m), int(d))
                if not FROM <= day <= to or r["countyname"] == "평년":
                    continue
                if r["price"].strip() == "-":
                    dash += 1
                    continue
                priced[(r["productrankcode"], r["countyname"], r["marketname"] or "", day)] = int(r["price"].replace(",", ""))
    return priced, dash


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--to", type=dt.date.fromisoformat, default=dt.date(2026, 10, 28))
    args = ap.parse_args()
    c, c_dash = csv_rows(args.to)
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        q = ("SELECT rank_code, county, market, trade_date, price FROM price_raw"
             " WHERE market_type = 'wholesale' AND trade_date BETWEEN %s AND %s")
        rows = conn.execute(q, (FROM, args.to)).fetchall()
    db = {r[:4]: r[4] for r in rows if r[4] is not None}
    db_dash = sum(r[4] is None for r in rows)
    avg_ok = {k: v for k, v in c.items() if k[1] == "평균"} == {k: v for k, v in db.items() if k[1] == "평균"}
    print(f"가격 있는 행: CSV {len(c):,} / DB {len(db):,} → {'일치' if c == db else '불일치'}")
    print(f"평균 행: CSV {sum(k[1] == '평균' for k in c):,} / DB {sum(k[1] == '평균' for k in db):,} → {'일치' if avg_ok else '불일치'}")
    print(f"(참고, 기준 제외) '-' 행: CSV {c_dash:,} / DB {db_dash:,}")
    if c != db:
        for k in sorted(set(c) ^ set(db) | {k for k in set(c) & set(db) if c[k] != db[k]})[:20]:
            print("  차이:", k, c.get(k), db.get(k))
    return 0 if c == db and avg_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
