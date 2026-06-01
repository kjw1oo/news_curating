import json
from pathlib import Path
from src.collectors.woori import parse_woori_html, parse_toss_news_json, _to_iso_kst
from src.collectors import build_toss_collectors
from src.models import Category


def test_parse_woori_html_normalizes_items():
    html = Path("tests/fixtures/woori_news.html").read_text(encoding="utf-8")
    items = parse_woori_html(html, source_name="토스인베스트")
    assert len(items) == 2
    first = items[0]
    assert first.category == Category.WOORI
    assert first.title == "우리금융, 생성형 AI 플랫폼 전 계열사 확대"
    assert first.url == "https://www.tossinvest.com/news/111"
    assert first.source == "한국경제"
    assert first.published_at == "2026-05-29T08:30:00+09:00"
    assert first.id == items[0].id and len(first.id) == 16
    assert first.summary_raw.startswith("우리금융지주가 생성형 AI")


def test_parse_handles_empty_html():
    assert parse_woori_html("<html></html>", source_name="토스") == []


def test_parse_graceful_degradation():
    html = """
    <html><body><ul>
      <li class="news-item"><span class="source">노링크</span></li>
      <li class="news-item"><a href="https://www.tossinvest.com/news/200">제목만</a></li>
    </ul></body></html>
    """
    items = parse_woori_html(html, source_name="토스")
    # <a> 없는 노드는 스킵 → 1건만
    assert len(items) == 1
    only = items[0]
    assert only.title == "제목만"
    assert only.source == "토스"  # .source 없으면 source_name 폴백
    assert only.published_at == ""  # <time> 없으면 빈 문자열
    assert only.summary_raw == ""  # .desc 없으면 빈 문자열


def test_parse_truncates_long_desc():
    long_desc = "가" * 2000
    html = f"""
    <html><body><ul>
      <li class="news-item">
        <a href="https://www.tossinvest.com/news/300">긴 설명</a>
        <p class="desc">{long_desc}</p>
      </li>
    </ul></body></html>
    """
    items = parse_woori_html(html, source_name="토스")
    assert len(items) == 1
    assert len(items[0].summary_raw) == 1000


def test_parse_resolves_relative_url():
    html = """
    <html><body><ul>
      <li class="news-item">
        <a href="/news/999">상대경로</a>
      </li>
    </ul></body></html>
    """
    items = parse_woori_html(
        html, source_name="토스", base_url="https://www.tossinvest.com"
    )
    assert len(items) == 1
    assert items[0].url == "https://www.tossinvest.com/news/999"


# ─── 토스 내부 JSON API 파서 ──────────────────────────────────

def test_parse_toss_news_json_normalizes():
    data = json.loads(Path("tests/fixtures/toss_news.json").read_text(encoding="utf-8"))
    items = parse_toss_news_json(data, source_name="토스인베스트")
    # id 없는 항목 1건은 스킵 → 4개 중 3건
    assert len(items) == 3
    first = items[0]
    assert first.category == Category.WOORI
    assert first.title == "우리금융, 생성형 AI 플랫폼 전 계열사 확대"
    assert first.url == "https://www.tossinvest.com/news/edaily_2026060106300000199"
    assert first.source == "이데일리"
    assert first.published_at == "2026-06-01T06:30:00+09:00"   # KST naive → +09:00
    assert len(first.id) == 16
    assert first.summary_raw.startswith("우리금융지주가 생성형 AI")


def test_parse_toss_news_json_preserves_existing_tz():
    data = json.loads(Path("tests/fixtures/toss_news.json").read_text(encoding="utf-8"))
    items = parse_toss_news_json(data)
    second = items[1]
    assert second.published_at == "2026-05-31T10:00:00+09:00"  # 이미 tz 있으면 그대로


def test_parse_toss_news_json_source_fallback():
    data = json.loads(Path("tests/fixtures/toss_news.json").read_text(encoding="utf-8"))
    items = parse_toss_news_json(data, source_name="토스인베스트")
    # source.name 없는 항목 → source_name 폴백
    assert items[2].source == "토스인베스트"


def test_parse_toss_news_json_handles_empty():
    assert parse_toss_news_json({}, source_name="토스") == []
    assert parse_toss_news_json({"result": {"body": []}}, source_name="토스") == []
    assert parse_toss_news_json(None) == []


def test_parse_toss_news_json_category_param():
    data = json.loads(Path("tests/fixtures/toss_news.json").read_text(encoding="utf-8"))
    items = parse_toss_news_json(data, source_name="토스", category=Category.DOMESTIC_FINANCE_AI)
    assert items and all(it.category == Category.DOMESTIC_FINANCE_AI for it in items)


def test_build_toss_collectors_from_config():
    cfg = {"sources": {
        "woori": {"type": "toss", "name": "우리금융", "toss_stock": "A316140", "category": "woori"},
        "shinhan": {"type": "toss", "name": "신한", "toss_stock": "A055550", "category": "domestic_finance_ai"},
        "mk": {"type": "rss", "name": "mk", "url": "http://x", "category": "domestic_finance_ai"},
        "bad": {"type": "toss", "name": "누락", "category": "woori"},  # toss_stock 없음 → 제외
    }}
    cols = build_toss_collectors(cfg)
    assert len(cols) == 2                                   # rss·누락 제외
    assert {c.stock_code for c in cols} == {"316140", "055550"}   # 'A' 제거
    cats = {c.stock_code: c.category for c in cols}
    assert cats["316140"] == "woori" and cats["055550"] == "domestic_finance_ai"


def test_to_iso_kst():
    assert _to_iso_kst("2026-06-01T06:30:00") == "2026-06-01T06:30:00+09:00"
    assert _to_iso_kst("2026-06-01T06:30:00+09:00") == "2026-06-01T06:30:00+09:00"
    assert _to_iso_kst("2026-06-01T06:30:00Z") == "2026-06-01T06:30:00Z"
    assert _to_iso_kst("") == ""
