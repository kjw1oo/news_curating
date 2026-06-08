from fastapi.testclient import TestClient
from src.api.app import create_app
from src.storage import Storage
from src.models import NewsItem, Category, make_id


def _seed(st, **kw):
    defaults = dict(
        id=make_id("u1"), category=Category.DOMESTIC_FINANCE_AI, title="우리금융 AI",
        url="https://t.com/u1", source="토스", published_at="2026-05-29T00:00:00+09:00",
        collected_at="", summary_raw="요약 본문", importance_score=6.0,
        importance_reason="근거", send_recommended=True)
    defaults.update(kw)
    st.upsert([NewsItem(**defaults)])


def _client(st, config=None):
    return TestClient(create_app(storage=st, config=config or {},
                                 run_collect=lambda: {"stored": 0}))


# ─── /api/send ─────────────────────────────────────────────
def test_send_dispatches_recommended_and_records_history(tmp_path):
    st = Storage(tmp_path / "a.db"); _seed(st)
    client = _client(st, {"notifiers": ["console"]})
    r = client.post("/api/send")
    assert r.status_code == 200
    body = r.json()
    assert body["sent"] == 1 and body["batch_id"]
    # 이력 반영
    h = client.get("/api/history").json()
    assert "items" in h and "total" in h
    assert h["total"] == 1
    assert h["items"][0]["news_id"] == make_id("u1")
    assert h["items"][0]["category_label"] == "국내 금융 AI"


def test_send_is_idempotent_within_24h(tmp_path):
    st = Storage(tmp_path / "b.db"); _seed(st)
    client = _client(st, {"notifiers": ["console"]})
    assert client.post("/api/send").json()["sent"] == 1
    # 두 번째 호출은 24h 재발송 차단으로 0건
    assert client.post("/api/send").json()["sent"] == 0
    assert client.get("/api/history").json()["total"] == 1


def test_send_respects_monthly_cap(tmp_path):
    st = Storage(tmp_path / "c.db")
    _seed(st, id=make_id("g1"), url="https://t.com/g1",
          category=Category.GLOBAL_FINANCE_AI, importance_score=9.0)
    _seed(st, id=make_id("g2"), url="https://t.com/g2",
          category=Category.GLOBAL_FINANCE_AI, importance_score=8.0)
    client = _client(st, {"notifiers": ["console"],
                          "monthly_cap": {"global_finance_ai": 1}})
    assert client.post("/api/send").json()["sent"] == 1


def test_send_empty_returns_zero(tmp_path):
    st = Storage(tmp_path / "d.db")
    client = _client(st, {"notifiers": ["console"]})
    body = client.post("/api/send").json()
    assert body["sent"] == 0 and body["batch_id"] is None


def test_history_empty_wrapped(tmp_path):
    st = Storage(tmp_path / "e.db")
    client = _client(st)
    assert client.get("/api/history").json() == {"items": [], "total": 0}


# ─── /api/feedback ─────────────────────────────────────────
def test_feedback_post_then_get(tmp_path):
    st = Storage(tmp_path / "f.db"); _seed(st)
    client = _client(st)
    r = client.post("/api/feedback", json={"news_id": make_id("u1"),
                                           "kind": "false_positive", "note": "오발송"})
    assert r.status_code == 200
    assert r.json()["kind"] == "false_positive"
    got = client.get("/api/feedback").json()
    assert got["total"] == 1
    assert got["items"][0]["news_id"] == make_id("u1")
    assert got["items"][0]["note"] == "오발송"


def test_feedback_rejects_invalid_kind(tmp_path):
    st = Storage(tmp_path / "g.db"); _seed(st)
    client = _client(st)
    r = client.post("/api/feedback", json={"news_id": "x", "kind": "bogus"})
    assert r.status_code == 422


def test_feedback_accepts_all_valid_kinds(tmp_path):
    st = Storage(tmp_path / "h.db"); _seed(st)
    client = _client(st)
    for kind in ("false_positive", "false_negative", "good"):
        assert client.post("/api/feedback",
                           json={"news_id": "x", "kind": kind}).status_code == 200
    assert client.get("/api/feedback").json()["total"] == 3


def test_feedback_get_empty_wrapped(tmp_path):
    st = Storage(tmp_path / "i.db")
    client = _client(st)
    assert client.get("/api/feedback").json() == {"items": [], "total": 0}


# ─── 기존 계약 회귀 확인 ────────────────────────────────────
def test_existing_news_contract_unchanged(tmp_path):
    st = Storage(tmp_path / "j.db"); _seed(st)
    client = _client(st)
    # days=0 으로 표시창 비활성 — 시드 발행일이 오래돼도 계약 검증이 날짜에 휘둘리지 않게.
    body = client.get("/api/news?days=0").json()
    assert "items" in body and "total" in body
    assert body["items"][0]["importance_reason"] == "근거"
    assert body["items"][0]["category_label"] == "국내 금융 AI"
