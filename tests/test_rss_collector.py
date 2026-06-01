from pathlib import Path

from src.collectors.rss import parse_rss_feed
from src.collectors import build_rss_collectors, RSSCollector
from src.models import Category


def _load(name: str) -> str:
    return Path(f"tests/fixtures/{name}").read_text(encoding="utf-8")


def test_parse_rss2_normalizes_items():
    items = parse_rss_feed(
        _load("rss_global_ai.xml"), category=Category.GLOBAL_AI, source_name="GoogleNews AI"
    )
    # link 없는 3번째 항목은 스킵 → 2건
    assert len(items) == 2
    first = items[0]
    assert first.category == Category.GLOBAL_AI
    assert first.title == "OpenAI unveils new frontier model - TechCrunch"
    # 쿼리스트링은 make_id 정규화 대상이지만 url 자체는 원문 보존
    assert first.url.startswith("https://techcrunch.com/2026/05/29/openai-frontier-model/")
    # GoogleNews <source> → 원기사 발행처로 재정규화
    assert first.source == "TechCrunch"
    # RFC822 pubDate → ISO8601(UTC)
    assert first.published_at == "2026-05-29T08:30:00+00:00"
    assert len(first.id) == 16
    assert first.summary_raw.startswith("OpenAI announced")
    # 수집 단계 기본값 — filter가 채움
    assert first.keyword_passed is False
    assert first.importance_score is None


def test_parse_atom_handles_published_and_content():
    items = parse_rss_feed(
        _load("atom_finance_ai.xml"),
        category=Category.GLOBAL_FINANCE_AI,
        source_name="Finextra Headlines",
    )
    assert len(items) == 2
    a, b = items
    assert a.category == Category.GLOBAL_FINANCE_AI
    assert a.url == "https://www.finextra.com/newsarticle/jpmorgan-ai-trading"
    # Atom엔 <source> 없음 → URL 도메인으로 폴백
    assert a.source == "www.finextra.com"
    assert a.published_at == "2026-05-29T08:00:00+00:00"
    assert a.summary_raw.startswith("The bank rolled out")
    # content type=html 발췌
    assert b.summary_raw.startswith("A new platform")
    assert b.published_at == "2026-05-28T11:30:00+00:00"


def test_parse_empty_feed():
    assert parse_rss_feed("<rss version='2.0'><channel></channel></rss>",
                          category=Category.GLOBAL_AI, source_name="x") == []
    # 사전파싱된 빈 entries 리스트도 안전
    assert parse_rss_feed([], category=Category.GLOBAL_AI, source_name="x") == []


def test_parse_truncates_long_summary():
    long = "x" * 2000
    raw = f"""<rss version='2.0'><channel>
      <item><title>T</title><link>https://e.com/a</link>
        <description>{long}</description></item>
    </channel></rss>"""
    items = parse_rss_feed(raw, category=Category.GLOBAL_AI, source_name="x")
    assert len(items) == 1
    assert len(items[0].summary_raw) == 1000


def test_parse_entries_dict_path():
    """list[dict] 입력(사전 파싱) 경로 — feedparser 구조를 흉내."""
    entries = [{
        "title": "Pre-parsed",
        "link": "https://e.com/p",
        "published_parsed": (2026, 5, 29, 8, 0, 0, 0, 0, 0),
        "summary": "hi",
    }]
    items = parse_rss_feed(entries, category=Category.GLOBAL_AI, source_name="x")
    assert len(items) == 1
    assert items[0].published_at == "2026-05-29T08:00:00+00:00"
    assert items[0].source == "e.com"


def test_build_rss_collectors_from_config():
    config = {"sources": {
        "woori": {"name": "우리", "toss_stock": "A1", "category": "domestic_finance_ai"},
        "gn_ai": {"type": "rss", "name": "GN AI", "category": "global_ai",
                  "url": "https://news.google.com/rss/x"},
        "bad": {"type": "rss", "name": "no url", "category": "global_ai"},
    }}
    collectors = build_rss_collectors(config)
    # woori(비 rss)·bad(url 없음) 제외 → 1개
    assert len(collectors) == 1
    c = collectors[0]
    assert isinstance(c, RSSCollector)
    assert c.category == "global_ai"
    assert c.source_name == "GN AI"
    assert c.feed_url == "https://news.google.com/rss/x"


def test_build_rss_collectors_empty_config():
    assert build_rss_collectors({}) == []
    assert build_rss_collectors({"sources": None}) == []


def test_future_dated_event_entries_are_dropped():
    """미래 발행일(예정 이벤트/웨비나 공지)은 뉴스가 아니므로 제외된다.

    Finextra headlines 피드가 `/event-info/` 미래일 항목을 섞어 넣는 실제
    현상을 재현한다. 정상 과거 기사는 유지되어야 한다.
    """
    from datetime import datetime, timezone, timedelta

    future = (datetime.now(timezone.utc) + timedelta(days=30)).strftime(
        "%a, %d %b %Y %H:%M:%S GMT"
    )
    raw = f"""<rss version='2.0'><channel>
      <item><title>Real news article</title>
        <link>https://www.finextra.com/newsarticle/real-1</link>
        <pubDate>Wed, 28 May 2026 08:30:00 GMT</pubDate>
        <description>An actual past-dated news story.</description></item>
      <item><title>Upcoming webinar: agentic AI</title>
        <link>https://www.finextra.com/event-info/620/from-copilot-to-autopilot</link>
        <pubDate>{future}</pubDate>
        <description>Register for our future event.</description></item>
    </channel></rss>"""
    items = parse_rss_feed(raw, category=Category.GLOBAL_FINANCE_AI, source_name="Finextra")
    urls = [it.url for it in items]
    assert "https://www.finextra.com/newsarticle/real-1" in urls
    assert all("/event-info/" not in u for u in urls)
    assert len(items) == 1


def test_near_future_grace_keeps_just_published_items():
    """게시 직후 시차/타임존 흔들림(수 시간 미래)은 grace로 흡수해 유지."""
    from datetime import datetime, timezone, timedelta

    near = (datetime.now(timezone.utc) + timedelta(hours=2)).strftime(
        "%a, %d %b %Y %H:%M:%S GMT"
    )
    raw = f"""<rss version='2.0'><channel>
      <item><title>Just published</title>
        <link>https://e.com/fresh</link>
        <pubDate>{near}</pubDate></item>
    </channel></rss>"""
    items = parse_rss_feed(raw, category=Category.GLOBAL_AI, source_name="x")
    assert len(items) == 1


def test_max_age_days_drops_stale_archive_items():
    """아카이브 덤프(수개월 전 항목)는 max_age_days로 제외, 최신 항목은 유지."""
    from datetime import datetime, timezone, timedelta

    old = (datetime.now(timezone.utc) - timedelta(days=200)).strftime(
        "%a, %d %b %Y %H:%M:%S GMT"
    )
    fresh = (datetime.now(timezone.utc) - timedelta(days=3)).strftime(
        "%a, %d %b %Y %H:%M:%S GMT"
    )
    raw = f"""<rss version='2.0'><channel>
      <item><title>Fresh post</title><link>https://dm.com/fresh</link>
        <pubDate>{fresh}</pubDate></item>
      <item><title>Archive post from last year</title><link>https://dm.com/archive</link>
        <pubDate>{old}</pubDate></item>
    </channel></rss>"""
    # 기본(None)은 둘 다 유지 — 하위호환
    assert len(parse_rss_feed(raw, category=Category.GLOBAL_AI, source_name="x")) == 2
    # max_age_days=45 → 오래된 아카이브 제외
    kept = parse_rss_feed(raw, category=Category.GLOBAL_AI, source_name="x", max_age_days=45)
    urls = [it.url for it in kept]
    assert urls == ["https://dm.com/fresh"]


def test_build_rss_collectors_passes_max_age_from_config():
    config = {
        "max_feed_age_days": 45,
        "sources": {
            "gn": {"type": "rss", "name": "GN", "category": "global_ai",
                   "url": "https://e.com/feed"},
            "dm": {"type": "rss", "name": "DM", "category": "global_ai",
                   "url": "https://dm.com/feed", "max_age_days": 7},
        },
    }
    collectors = {c.source_name: c for c in build_rss_collectors(config)}
    assert collectors["GN"].max_age_days == 45      # 전역 상속
    assert collectors["DM"].max_age_days == 7        # 소스별 재정의
