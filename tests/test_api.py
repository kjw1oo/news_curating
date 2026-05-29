from fastapi.testclient import TestClient
from src.api.app import create_app
from src.storage import Storage
from src.models import NewsItem, Category, make_id


def _seed(st):
    st.upsert([NewsItem(id=make_id("u1"), category=Category.DOMESTIC_FINANCE_AI, title="우리금융 AI",
        url="u1", source="토스", published_at="2026-05-29T00:00:00+09:00", collected_at="",
        summary_raw="요약", importance_score=6.0, importance_reason="근거", send_recommended=True)])


def test_news_endpoint_returns_wrapped_list(tmp_path):
    st = Storage(tmp_path / "a.db"); _seed(st)
    client = TestClient(create_app(storage=st, config={}, run_collect=lambda: {"stored": 0}))
    r = client.get("/api/news")
    assert r.status_code == 200
    body = r.json()
    assert "items" in body and "total" in body          # 래핑 계약
    assert body["items"][0]["importance_reason"] == "근거"


def test_alerts_endpoint_only_recommended(tmp_path):
    st = Storage(tmp_path / "b.db"); _seed(st)
    client = TestClient(create_app(storage=st, config={}, run_collect=lambda: {"stored": 0}))
    body = client.get("/api/alerts").json()
    assert all(it["send_recommended"] for it in body["items"])


def test_collect_endpoint_triggers_pipeline(tmp_path):
    st = Storage(tmp_path / "c.db")
    client = TestClient(create_app(storage=st, config={}, run_collect=lambda: {"stored": 3}))
    assert client.post("/api/collect").json()["stored"] == 3


def test_news_empty_db_returns_empty_wrapped(tmp_path):
    st = Storage(tmp_path / "d.db")
    client = TestClient(create_app(storage=st, config={}, run_collect=lambda: {"stored": 0}))
    r = client.get("/api/news")
    assert r.status_code == 200
    assert r.json() == {"items": [], "total": 0}


def test_news_filters_by_category(tmp_path):
    st = Storage(tmp_path / "e.db")
    st.upsert([
        NewsItem(id=make_id("u1"), category=Category.DOMESTIC_FINANCE_AI, title="국내",
            url="u1", source="토스", published_at="2026-05-29T00:00:00+09:00", collected_at="",
            summary_raw="요약", importance_score=6.0, importance_reason="근거", send_recommended=True),
        NewsItem(id=make_id("u2"), category=Category.GLOBAL_AI, title="글로벌",
            url="u2", source="RSS", published_at="2026-05-29T00:00:00+09:00", collected_at="",
            summary_raw="요약", importance_score=7.0, importance_reason="근거", send_recommended=True),
    ])
    client = TestClient(create_app(storage=st, config={}, run_collect=lambda: {"stored": 0}))
    body = client.get("/api/news?category=domestic_finance_ai").json()
    assert body["total"] == 1
    assert body["items"][0]["category"] == Category.DOMESTIC_FINANCE_AI


def test_config_endpoint_echoes_injected_config(tmp_path):
    st = Storage(tmp_path / "f.db")
    cfg = {"thresholds": {"domestic_finance_ai": 4.0}}
    client = TestClient(create_app(storage=st, config=cfg, run_collect=lambda: {"stored": 0}))
    assert client.get("/api/config").json() == cfg
