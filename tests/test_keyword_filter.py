from src.filters.keyword import keyword_filter
from src.models import NewsItem, Category, make_id

def _item(title, summary=""):
    return NewsItem(id=make_id(title), category=Category.DOMESTIC_FINANCE_AI, title=title,
                    url="u/"+title, source="s", published_at="", collected_at="", summary_raw=summary)

def test_keeps_items_with_keyword():
    items = [_item("우리금융 AI 도입"), _item("우리은행 점포 오픈")]
    kept = keyword_filter(items, ["AI", "인공지능"])
    assert len(kept) == 1 and kept[0].keyword_passed is True

def test_matches_in_summary_too():
    kept = keyword_filter([_item("우리금융 신규 발표", summary="마이데이터 기반 서비스")], ["마이데이터"])
    assert len(kept) == 1
