from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse
from src.models import LABELS

_WEB = Path(__file__).resolve().parent.parent / "web"


def _wrap(items):
    rows = [it.to_dict() for it in items]
    for r in rows:
        r["category_label"] = LABELS.get(r["category"], r["category"])
    return {"items": rows, "total": len(rows)}


def create_app(storage, config, run_collect):
    app = FastAPI(title="News Monitoring Demo")

    @app.get("/api/news")
    def news(category: str | None = None, min_score: float | None = None):
        return _wrap(storage.query(category=category, min_score=min_score))

    @app.get("/api/alerts")
    def alerts():
        return _wrap([it for it in storage.query() if it.send_recommended])

    @app.get("/api/config")
    def get_config():
        return config

    @app.post("/api/collect")
    def collect():
        return run_collect()

    @app.get("/")
    def index():
        return FileResponse(_WEB / "index.html")

    return app
