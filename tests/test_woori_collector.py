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
