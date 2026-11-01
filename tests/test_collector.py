import datetime as dt
import json

import pytest

from tomato.collectors import kamis
from tomato.config import Settings

S = Settings(kamis_api_key="SECRETKEY123", kamis_cert_id="CERT9", database_url="postgresql://x")
BODY = json.dumps({"data": {"error_code": "000", "item": [
    {"countyname": "평균", "marketname": "", "yyyy": "2026", "regday": "10/28", "price": "20,600"},
    {"countyname": "부산", "marketname": "엄궁도매", "yyyy": "2026", "regday": "10/28", "price": "-"},
    {"countyname": "평년", "marketname": "", "yyyy": "2026", "regday": "10/28", "price": "15,000"},
]}})


def test_parse_drops_normal_year_and_nulls_dash():
    rows = kamis.parse(BODY, "wholesale", "04")
    assert [(r["county"], r["market"], r["price"]) for r in rows] == [("평균", "", 20600), ("부산", "엄궁도매", None)]
    assert rows[0]["trade_date"] == dt.date(2026, 10, 28) and rows[0]["unit"] == "5kg"


def test_no_data_code_is_empty():
    assert kamis.parse(json.dumps({"data": ["001"]}), "wholesale", "04") == []


def test_retry_then_success():
    calls, waits = [], []

    def http(url):
        calls.append(url)
        if len(calls) < 3:
            raise OSError("network down")
        return BODY

    rows, attempts = kamis.fetch_range(S, dt.date(2026, 10, 28), dt.date(2026, 10, 28), "04",
                                       http_get=http, sleep=waits.append)
    assert attempts == 3 and len(rows) == 2 and waits == [2, 4]


def test_retry_exhausted_masks_secrets():
    def http(url):
        raise OSError(f"failed {url}")  # 오류 메시지에 키가 포함된 URL

    with pytest.raises(kamis.FetchError) as e:
        kamis.fetch_range(S, dt.date(2026, 10, 28), dt.date(2026, 10, 28), "04", http_get=http, sleep=lambda s: None)
    assert e.value.attempts == 3
    assert "SECRETKEY123" not in str(e.value) and "CERT9" not in str(e.value) and "***" in str(e.value)


def test_settings_repr_hides_secrets():
    assert "SECRETKEY123" not in repr(S) and "CERT9" not in repr(S)


def test_year_chunks():
    chunks = list(kamis.year_chunks(dt.date(2024, 1, 1), dt.date(2025, 6, 1)))
    assert chunks == [(dt.date(2024, 1, 1), dt.date(2024, 12, 30)), (dt.date(2024, 12, 31), dt.date(2025, 6, 1))]
