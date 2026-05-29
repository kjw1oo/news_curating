from src.models import NewsItem, Category, make_id

def test_make_id_is_stable_and_normalized():
    a = make_id("https://example.com/news/1?utm_source=x")
    b = make_id("https://example.com/news/1")
    assert a == b                      # 쿼리스트링 무시
    assert len(a) == 16

def test_newsitem_roundtrip_dict():
    item = NewsItem(
        id=make_id("https://t.com/1"), category=Category.DOMESTIC_FINANCE_AI,
        title="우리금융 AI 도입", url="https://t.com/1", source="토스인베스트",
        published_at="2026-05-29T08:00:00+09:00", collected_at="2026-05-29T09:00:00+09:00",
        summary_raw="요약",
    )
    d = item.to_dict()
    assert d["category"] == "domestic_finance_ai"
    assert NewsItem.from_dict(d).title == "우리금융 AI 도입"

def test_defaults_for_unscored_item():
    item = NewsItem(id="x", category=Category.GLOBAL_AI, title="t", url="u",
                    source="s", published_at="", collected_at="", summary_raw="")
    assert item.keyword_passed is False
    assert item.importance_score is None
    assert item.send_recommended is False
