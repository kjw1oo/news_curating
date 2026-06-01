from src.filters.category_rules import apply_woori_priority
from src.models import NewsItem, Category, make_id


def _item(title, category=Category.DOMESTIC_FINANCE_AI, summary=""):
    return NewsItem(id=make_id(title), category=category, title=title,
                    url="u/" + title, source="s", published_at="", collected_at="",
                    summary_raw=summary)


def test_promotes_domestic_woori_article_to_woori():
    items = apply_woori_priority([_item("우리금융 생성형 AI 플랫폼 확대")])
    assert items[0].category == Category.WOORI


def test_matches_entity_in_summary():
    items = apply_woori_priority([_item("AI 금융 신규 서비스", summary="우리은행이 도입한다")])
    assert items[0].category == Category.WOORI


def test_non_woori_domestic_stays_domestic():
    items = apply_woori_priority([_item("KB금융 AI 도입")])
    assert items[0].category == Category.DOMESTIC_FINANCE_AI


def test_does_not_touch_other_categories():
    # 글로벌 카테고리는 우리금융을 언급해도 승격하지 않는다(규칙 범위: 국내만).
    items = apply_woori_priority([_item("우리금융 글로벌 진출", category=Category.GLOBAL_FINANCE_AI)])
    assert items[0].category == Category.GLOBAL_FINANCE_AI


def test_already_woori_stays_woori():
    items = apply_woori_priority([_item("우리은행 AI", category=Category.WOORI)])
    assert items[0].category == Category.WOORI


def test_bare_uri_word_does_not_falsely_promote():
    # '우리'(=our) 단독은 승격 트리거가 아니다.
    items = apply_woori_priority([_item("우리 동네 은행 디지털 전환")])
    assert items[0].category == Category.DOMESTIC_FINANCE_AI


def test_custom_entities_override():
    items = apply_woori_priority([_item("신한 AI 발표")], entities=["신한"])
    assert items[0].category == Category.WOORI
