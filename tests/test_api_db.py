"""DB가 필요한 테스트. TEST_DATABASE_URL이 없으면 건너뛴다. 데이터가 채워진 DB(predict·explain 이후)를 가정."""
import os

import pytest

URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="TEST_DATABASE_URL 없음")


@pytest.fixture(scope="module")
def client():
    os.environ["DATABASE_URL"] = URL
    from fastapi.testclient import TestClient

    from tomato.api import main

    main.settings = main.load_settings()
    return TestClient(main.app)


def test_health(client):
    assert client.get("/health").json() == {"status": "ok", "db": "ok"}


def test_dashboard_has_required_elements(client):
    html = client.get("/").text
    f = client.get("/forecast/latest").json()
    assert f"{f['y_origin']:,}원" in html  # 현재 공표가
    assert f"{f['y_hat']:,}원" in html and f["target_date_est"] in html  # 예상가와 예상 날짜
    assert 'id="price-chart"' in html and "const prices" in html  # 그래프와 예측점
    assert f["explanation"]["text"] in html  # 설명
    assert "평균 오차" in html  # 성능 한 줄
    assert f["horizon_tdays"] == 3  # 대시보드는 3거래일
    if f["model"] == "lgbm":
        assert "LightGBM" in html and "직전가(B1) 대비 평균 오차" in html
    if f["model"] == "chronos2":
        assert "Chronos-2" in html and "직전가(B1) 대비 평균 오차" in html and "유의하지 않습니다" in html
