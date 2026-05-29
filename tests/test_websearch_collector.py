import json
from pathlib import Path

from src.collectors.websearch import parse_search_results, WebSearchCollector
from src.models import Category


def _sample():
    return [
        {
            "title": "OpenAI unveils new reasoning model",
            "url": "https://example.com/ai/openai-reasoning?utm=x",
            "source": "Reuters",
            "published_at": "2026-05-28",
            "summary": "OpenAI announced a new model that improves reasoning.",
        },
        {
            "title": "Banks adopt generative AI for risk",
            "url": "https://news.bank.com/genai-risk",
            "snippet": "Several banks rolled out genAI tools.",
        },
    ]


def test_parse_normalizes_items():
    items = parse_search_results(_sample(), category=Category.GLOBAL_AI)
    assert len(items) == 2
    first = items[0]
    assert first.category == Category.GLOBAL_AI
    assert first.title == "OpenAI unveils new reasoning model"
    assert first.url == "https://example.com/ai/openai-reasoning?utm=x"
    assert first.source == "Reuters"
    assert first.published_at == "2026-05-28"
    assert first.summary_raw.startswith("OpenAI announced")
    assert len(first.id) == 16


def test_parse_uses_snippet_when_no_summary():
    items = parse_search_results(_sample(), category=Category.GLOBAL_FINANCE_AI)
    assert items[1].summary_raw == "Several banks rolled out genAI tools."


def test_parse_source_falls_back_to_domain():
    items = parse_search_results(_sample(), category=Category.GLOBAL_AI)
    # 두 번째 항목은 source 키가 없으므로 도메인에서 유도
    assert items[1].source == "news.bank.com"


def test_parse_skips_missing_title_or_url():
    results = [
        {"url": "https://x.com/a"},          # title 없음
        {"title": "No URL"},                  # url 없음
        {"title": "ok", "url": "https://x.com/b"},
    ]
    items = parse_search_results(results, category=Category.GLOBAL_AI)
    assert len(items) == 1
    assert items[0].title == "ok"


def test_parse_truncates_long_summary():
    results = [{"title": "t", "url": "https://x.com/c", "summary": "가" * 2000}]
    items = parse_search_results(results, category=Category.GLOBAL_AI)
    assert len(items[0].summary_raw) == 1000


def test_collector_loads_seed_file(tmp_path):
    seed = {
        Category.GLOBAL_AI: _sample(),
        Category.DOMESTIC_FINANCE_AI: [
            {"title": "국내 은행 AI 도입", "url": "https://kr.bank.com/ai"}
        ],
    }
    seed_file = tmp_path / "seed.json"
    seed_file.write_text(json.dumps(seed, ensure_ascii=False), encoding="utf-8")

    collector = WebSearchCollector(str(seed_file), category=Category.DOMESTIC_FINANCE_AI)
    items = collector.collect()
    assert len(items) == 1
    assert items[0].category == Category.DOMESTIC_FINANCE_AI
    assert items[0].title == "국내 은행 AI 도입"


def test_collector_missing_category_returns_empty(tmp_path):
    seed_file = tmp_path / "seed.json"
    seed_file.write_text(json.dumps({Category.GLOBAL_AI: []}, ensure_ascii=False), encoding="utf-8")
    collector = WebSearchCollector(str(seed_file), category=Category.GLOBAL_FINANCE_AI)
    assert collector.collect() == []
