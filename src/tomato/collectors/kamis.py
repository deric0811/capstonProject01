"""KAMIS 16번(도매) 일별 기간 조회 수집기. scripts/fetch_kamis.py의 요청 방식을 따른다.

- 요청마다 최대 3회 시도하고, 시도 사이에 2초, 4초를 기다린다.
- 오류 메시지에서 키를 가린다(config.mask).
- 평년 행은 버리고, 가격 '-'는 None으로 둔다.
"""
import datetime as dt
import json
import time
import urllib.parse
import urllib.request

from tomato.config import mask

ITEM = {"p_itemcategorycode": "200", "p_itemcode": "225", "p_kindcode": "00"}
RANKS = ("04", "05")
ACTIONS = {"wholesale": "periodWholesaleProductList"}
UNITS = {"wholesale": "5kg"}
TRIES = 3
BACKOFF_SEC = 2
DELAY_SEC = 2  # 요청 사이 간격


class FetchError(Exception):
    def __init__(self, message, attempts):
        super().__init__(message)
        self.attempts = attempts


def _http_get(url):
    return urllib.request.urlopen(url, timeout=60).read().decode("utf-8")


def with_retry(fn, secrets, tries=TRIES, backoff=BACKOFF_SEC, sleep=time.sleep):
    """fn()을 최대 tries번 시도한다. (결과, 시도 횟수). 모두 실패하면 FetchError(키를 가린 메시지)."""
    for attempt in range(1, tries + 1):
        try:
            return fn(), attempt
        except Exception as e:  # noqa: BLE001 - 네트워크·파싱 오류를 모두 재시도한다
            err = mask(f"{type(e).__name__}: {e}", secrets)
            if attempt == tries:
                raise FetchError(err, attempt) from None
            sleep(backoff * 2 ** (attempt - 1))


def parse(body, market_type, rank):
    payload = json.loads(body)
    data = payload.get("data", {})
    code = data.get("error_code") if isinstance(data, dict) else (data[0] if data else None)
    if code == "001":  # 데이터 없음
        return []
    if code != "000":
        raise ValueError(f"KAMIS error_code={code}")
    items = data.get("item", [])
    if isinstance(items, dict):
        items = [items]
    rows = []
    for it in items:
        if it.get("countyname") == "평년":
            continue
        m, d = it["regday"].split("/")
        price = it.get("price", "").replace(",", "").strip()
        rows.append({
            "market_type": market_type, "item_code": ITEM["p_itemcode"], "kind_code": ITEM["p_kindcode"],
            "rank_code": rank, "county": it.get("countyname", ""), "market": it.get("marketname") or "",
            "trade_date": dt.date(int(it["yyyy"]), int(m), int(d)),
            "price": None if price in ("", "-") else int(price), "unit": UNITS[market_type],
        })
    return rows


def fetch_range(settings, start, end, rank, market_type="wholesale", http_get=_http_get, sleep=time.sleep):
    """[start, end] (최대 1년) 한 등급의 행. (rows, 시도 횟수)"""
    params = {
        "action": ACTIONS[market_type], "p_cert_key": settings.kamis_api_key, "p_cert_id": settings.kamis_cert_id,
        "p_returntype": "json", "p_startday": start.isoformat(), "p_endday": end.isoformat(),
        "p_productrankcode": rank, "p_convert_kg_yn": "N", **ITEM,
    }
    url = settings.kamis_url + "?" + urllib.parse.urlencode(params)
    return with_retry(lambda: parse(http_get(url), market_type, rank), settings.secrets, sleep=sleep)


def year_chunks(start, end):
    while start <= end:
        stop = min(start + dt.timedelta(days=364), end)
        yield start, stop
        start = stop + dt.timedelta(days=1)


def collect(settings, start, end, market_type="wholesale", http_get=_http_get, sleep=time.sleep):
    """기간을 1년 단위로 나눠 두 등급을 받는다. (rows, 가장 많이 시도한 횟수)"""
    rows, max_attempts, first = [], 0, True
    for a, b in year_chunks(start, end):
        for rank in RANKS:
            if not first:
                sleep(DELAY_SEC)
            first = False
            got, attempts = fetch_range(settings, a, b, rank, market_type, http_get, sleep)
            rows += got
            max_attempts = max(max_attempts, attempts)
    return rows, max_attempts
