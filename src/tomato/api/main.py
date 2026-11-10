"""FastAPI: 대시보드 한 화면(/)과 JSON API (/health, /prices, /forecast/latest)."""
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from tomato import cli
from tomato.config import load_settings
from tomato.db import repo

WEB = Path(__file__).resolve().parent.parent / "web"
CHART_DAYS = 120

app = FastAPI(title="tomato", description="KAMIS 토마토 도매가 3거래일 후 예측")
app.mount("/static", StaticFiles(directory=WEB / "static"), name="static")
templates = Jinja2Templates(directory=WEB / "templates")
settings = load_settings()


def _conn():
    return repo.connect(settings.database_url)


def _prices(conn, days):
    rows = repo.wholesale_series(conn)[-days:]
    return [{"date": d.isoformat(), "price": p, "n_markets": n} for d, p, n in rows]


def _latest(conn):
    f = repo.latest_forecast(conn)
    if not f:
        return None
    m = repo.metrics_for(conn, f["model"], cli.metric_experiment(f["model"], f["horizon_tdays"]), horizon=f["horizon_tdays"])
    label = cli.model_label(f["model"], f["horizon_tdays"])
    return {
        "model_label": label,
        **{k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in f.items()},
        "change_pct": float(f["change_pct"]),
        "explanation": repo.latest_explanation(conn, f["id"]),
        "performance": {k: {"value": v, "n": n} for k, (v, n) in m.items()} or None,
    }


@app.get("/health")
def health():
    try:
        with _conn() as conn:
            conn.execute("SELECT 1")
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"status": "error", "db": type(e).__name__}, status_code=503)
    return {"status": "ok", "db": "ok"}


@app.get("/prices")
def prices(days: int = CHART_DAYS):
    with _conn() as conn:
        return _prices(conn, days)


@app.get("/forecast/latest")
def forecast_latest():
    with _conn() as conn:
        return _latest(conn) or JSONResponse({"detail": "forecast 없음"}, status_code=404)


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    with _conn() as conn:
        ctx = {"prices": _prices(conn, CHART_DAYS), "f": _latest(conn)}
    return templates.TemplateResponse(request, "index.html", ctx)
