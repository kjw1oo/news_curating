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
    client = TestClient(create_app(storage=st, config={"display_window_days": 0}, run_collect=lambda: {"stored": 0}))
    r = client.get("/api/news")
    assert r.status_code == 200
    body = r.json()
    assert "items" in body and "total" in body          # 래핑 계약
    assert body["items"][0]["importance_reason"] == "근거"


def test_alerts_endpoint_only_recommended(tmp_path):
    st = Storage(tmp_path / "b.db"); _seed(st)
    client = TestClient(create_app(storage=st, config={"display_window_days": 0}, run_collect=lambda: {"stored": 0}))
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
    client = TestClient(create_app(storage=st, config={"display_window_days": 0}, run_collect=lambda: {"stored": 0}))
    body = client.get("/api/news?category=domestic_finance_ai").json()
    assert body["total"] == 1
    assert body["items"][0]["category"] == Category.DOMESTIC_FINANCE_AI


def test_news_default_window_hides_old_items(tmp_path):
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    recent = (now - timedelta(days=2)).date().isoformat() + "T00:00:00+00:00"
    old = (now - timedelta(days=30)).date().isoformat() + "T00:00:00+00:00"
    st = Storage(tmp_path / "w.db")
    st.upsert([
        NewsItem(id=make_id("r"), category=Category.GLOBAL_AI, title="최근", url="r", source="s",
                 published_at=recent, collected_at="", summary_raw="s", importance_score=9.0,
                 send_recommended=True),
        NewsItem(id=make_id("o"), category=Category.GLOBAL_AI, title="옛날", url="o", source="s",
                 published_at=old, collected_at="", summary_raw="s", importance_score=9.0,
                 send_recommended=True),
    ])
    client = TestClient(create_app(storage=st, config={}, run_collect=lambda: {"stored": 0}))
    assert client.get("/api/news").json()["total"] == 1            # 기본 7일 → 옛날 숨김
    assert client.get("/api/news?days=0").json()["total"] == 2     # 0 = 전체
    assert client.get("/api/alerts").json()["total"] == 1          # 알림도 7일 적용


def test_news_collapses_duplicate_events(tmp_path):
    st = Storage(tmp_path / "dup.db")
    st.upsert([
        NewsItem(id=make_id("u1"), category=Category.GLOBAL_AI, title="신한은행 생성형 AI 플랫폼 도입 발표",
            url="u1", source="A", published_at="2026-05-29T00:00:00+09:00", collected_at="",
            summary_raw="s", importance_score=8.0),
        NewsItem(id=make_id("u2"), category=Category.GLOBAL_AI, title="신한은행 생성형 AI 플랫폼 도입 발표 - 매일경제",
            url="u2", source="B", published_at="2026-05-29T00:00:00+09:00", collected_at="",
            summary_raw="s", importance_score=7.0),
        NewsItem(id=make_id("u3"), category=Category.GLOBAL_AI, title="전혀 다른 뉴스 OpenAI GPT-6 전격 공개",
            url="u3", source="C", published_at="2026-05-29T00:00:00+09:00", collected_at="",
            summary_raw="s", importance_score=9.0),
    ])
    client = TestClient(create_app(storage=st, config={"display_window_days": 0}, run_collect=lambda: {"stored": 0}))
    collapsed = client.get("/api/news").json()
    assert collapsed["total"] == 2                       # 신한 2건 → 대표 1건으로 합쳐짐
    rep = [it for it in collapsed["items"] if "신한" in it["title"]][0]
    assert rep["duplicate_count"] == 1
    assert rep["importance_score"] == 8.0                # 대표는 점수 높은 건
    full = client.get("/api/news?collapse=0").json()
    assert full["total"] == 3                            # collapse=0이면 전부 표시


def test_config_endpoint_echoes_injected_config(tmp_path):
    st = Storage(tmp_path / "f.db")
    cfg = {"thresholds": {"domestic_finance_ai": 4.0}}
    client = TestClient(create_app(storage=st, config=cfg, run_collect=lambda: {"stored": 0}))
    got = client.get("/api/config").json()
    # config를 그대로 에코하되 is_remote 플래그(로컬=False)를 덧붙인다.
    assert got == {**cfg, "is_remote": False}
