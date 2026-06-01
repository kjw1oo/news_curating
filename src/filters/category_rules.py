"""카테고리 우선순위 규칙.

우리금융 우선 적용: 우리금융그룹 관련 뉴스는 포괄 카테고리인 '국내 금융 AI'
(domestic_finance_ai)보다 전용 카테고리 '우리금융그룹'(woori)을 우선 적용한다.
어떤 수집기/소스가 domestic_finance_ai로 태깅해 들여보내도, 본문이 우리금융그룹
엔티티를 가리키면 woori로 승격한다(다른 카테고리는 건드리지 않음).
"""
from src.models import NewsItem, Category

# 우리금융그룹 식별 엔티티. '우리'(=our) 단독은 너무 광범위하므로 복합 식별자만 사용.
WOORI_ENTITIES = (
    "우리금융", "우리금융지주", "우리금융그룹",
    "우리은행", "우리카드", "우리종합금융", "우리투자증권",
    "우리에프아이에스", "우리펀드서비스", "wooribank", "woori financial",
)

# 승격 대상 카테고리: 국내 금융 AI만. (글로벌 등은 사용자 규칙 범위 밖)
_PROMOTABLE = {Category.DOMESTIC_FINANCE_AI}


def apply_woori_priority(items: list[NewsItem], entities=None) -> list[NewsItem]:
    """우리금융그룹 엔티티를 가리키는 domestic_finance_ai 항목을 woori로 승격한다.

    제목 또는 요약에 엔티티가 하나라도 있으면 category를 woori로 바꾼다.
    이미 woori이거나 다른 카테고리인 항목은 그대로 둔다. 입력 리스트를 제자리 수정.
    """
    ents = [e.lower() for e in (entities or WOORI_ENTITIES) if e]
    for it in items:
        if it.category in _PROMOTABLE:
            haystack = f"{it.title} {it.summary_raw}".lower()
            if any(e in haystack for e in ents):
                it.category = Category.WOORI
    return items
