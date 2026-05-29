from src.models import NewsItem


def keyword_filter(items: list[NewsItem], keywords: list[str]) -> list[NewsItem]:
    """제목 또는 요약에 키워드가 하나라도 있으면 통과(keyword_passed=True)시키고 반환."""
    kept = []
    lowered = [k.lower() for k in keywords]
    for it in items:
        haystack = f"{it.title} {it.summary_raw}".lower()
        if any(k in haystack for k in lowered):
            it.keyword_passed = True
            kept.append(it)
    return kept
