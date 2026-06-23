from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
from src.models import LABELS
from src.filters.postprocess import group_events, _best_of

_WEB = Path(__file__).resolve().parent.parent / "web"

# 피드백 종류: good(정상) / false_positive(비정상 — 중요뉴스로 잘못 분류).
_FEEDBACK_KINDS = {"false_positive", "good"}


def _collapse(items):
    """같은 사건(유사 제목)을 묶어 대표 1건만 남긴다(표시용 안전망).

    DB는 prune_duplicates로 물리 제거되지만, 잔여 중복이 있어도 피드엔 1건만 보이게 한다.
    대표 = 발송추천 > 점수 > 최신. duplicate_count에 합쳐진 추가 건수를 담는다.
    """
    return [(_best_of(g), len(g) - 1) for g in group_events(list(items))]


def _wrap(items, collapse=False):
    if collapse:
        rows = []
        for rep, dups in _collapse(items):
            d = rep.to_dict()
            d["category_label"] = LABELS.get(d["category"], d["category"])
            d["duplicate_count"] = dups
            rows.append(d)
        return {"items": rows, "total": len(rows)}
    rows = [it.to_dict() for it in items]
    for r in rows:
        r["category_label"] = LABELS.get(r["category"], r["category"])
        r["duplicate_count"] = 0
    return {"items": rows, "total": len(rows)}


def _wrap_rows(rows):
    rows = list(rows or [])
    for r in rows:
        if "category" in r:
            r["category_label"] = LABELS.get(r["category"], r["category"])
    return {"items": rows, "total": len(rows)}


class FeedbackIn(BaseModel):
    news_id: str
    kind: str
    note: str | None = None


def create_app(storage, config, run_collect):
    app = FastAPI(title="News Monitoring Demo")
    # 기본 표시 창(일). 운영자가 config로 조정. 요청 시 ?days=N 으로 덮어씀(0=전체).
    default_days = (config or {}).get("display_window_days", 7)

    @app.get("/api/news")
    def news(category: str | None = None, min_score: float | None = None,
             days: int | None = None, collapse: int = 1):
        d = default_days if days is None else days
        return _wrap(storage.query(category=category, min_score=min_score, max_age_days=d),
                     collapse=bool(collapse))

    @app.get("/api/alerts")
    def alerts(days: int | None = None, collapse: int = 1):
        d = default_days if days is None else days
        return _wrap([it for it in storage.query(max_age_days=d) if it.send_recommended],
                     collapse=bool(collapse))

    @app.get("/api/status")
    def status():
        """마지막 실행(수집) 시각·전체 건수 — 헤더 표시용."""
        return {"last_collected_at": storage.last_collected_at(),
                "total": storage.count()}

    @app.get("/api/config")
    def get_config():
        # is_remote: 클라우드(Turso) 배포 여부 — 프론트가 수집 버튼 노출을 결정한다.
        return {**(config or {}), "is_remote": bool(getattr(storage, "is_remote", False))}

    @app.post("/api/collect")
    def collect():
        return run_collect()

    @app.post("/api/feedback")
    def post_feedback(body: FeedbackIn):
        if body.kind not in _FEEDBACK_KINDS:
            raise HTTPException(
                status_code=422,
                detail=f"kind must be one of {sorted(_FEEDBACK_KINDS)}")
        return storage.add_feedback(body.news_id, body.kind, body.note or "")

    @app.get("/api/feedback")
    def get_feedback():
        return _wrap_rows(storage.feedback())

    @app.get("/")
    def index():
        path = _WEB / "index.html"
        if not path.exists():
            return HTMLResponse("<h1>대시보드 빌드 대기 중</h1>", status_code=503)
        return FileResponse(path)

    return app
