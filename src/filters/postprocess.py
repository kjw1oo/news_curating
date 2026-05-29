import re
from src.models import NewsItem


def apply_threshold(items: list[NewsItem], thresholds: dict) -> list[NewsItem]:
    """카테고리별 임계값 미만이면 send_recommended를 False로 끈다."""
    for it in items:
        cutoff = thresholds.get(it.category, 5.0)
        if it.importance_score is None or it.importance_score < cutoff:
            it.send_recommended = False
    return items


def _norm_tokens(title: str) -> set[str]:
    cleaned = re.sub(r"[^0-9a-z가-힣 ]", " ", title.lower())
    return {t for t in cleaned.split() if len(t) > 1}


def _similar(a: set[str], b: set[str], threshold: float = 0.6) -> bool:
    if not a or not b:
        return False
    jaccard = len(a & b) / len(a | b)
    return jaccard >= threshold


def dedup(items: list[NewsItem]) -> list[NewsItem]:
    """유사 제목을 같은 dedup_group으로 묶고, 그룹 내 점수 최고 1건만 send_recommended 유지."""
    # 그룹화는 greedy first-match: 각 그룹의 대표(첫 항목)와만 비교하므로 입력 순서에 의존 — MVP에서는 허용.
    groups: list[list[NewsItem]] = []
    for it in items:
        tokens = _norm_tokens(it.title)
        placed = False
        for g in groups:
            if _similar(tokens, _norm_tokens(g[0].title)):
                g.append(it); placed = True; break
        if not placed:
            groups.append([it])
    for gi, g in enumerate(groups):
        gid = f"g{gi}"
        winner = max(g, key=lambda x: (x.send_recommended, x.importance_score or -1))
        for it in g:
            it.dedup_group = gid
            if it is not winner:
                it.send_recommended = False
    return items
