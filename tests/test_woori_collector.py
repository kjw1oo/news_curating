from pathlib import Path
from src.collectors.woori import parse_woori_html
from src.models import Category


def test_parse_woori_html_normalizes_items():
    html = Path("tests/fixtures/woori_news.html").read_text(encoding="utf-8")
    items = parse_woori_html(html, source_name="토스인베스트")
    assert len(items) == 2
    first = items[0]
    assert first.category == Category.DOMESTIC_FINANCE_AI
    assert first.title == "우리금융, 생성형 AI 플랫폼 전 계열사 확대"
    assert first.url == "https://www.tossinvest.com/news/111"
    assert first.source == "한국경제"
    assert first.published_at == "2026-05-29T08:30:00+09:00"
    assert first.id == items[0].id and len(first.id) == 16
    assert first.summary_raw.startswith("우리금융지주가 생성형 AI")


def test_parse_handles_empty_html():
    assert parse_woori_html("<html></html>", source_name="토스") == []
