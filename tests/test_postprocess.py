from src.filters.postprocess import apply_threshold, dedup
from src.models import NewsItem, Category, make_id

def _item(url, score, title="우리금융 AI 발표", send=True):
    return NewsItem(id=make_id(url), category=Category.DOMESTIC_FINANCE_AI, title=title, url=url,
                    source="s", published_at="2026-05-29T00:00:00+09:00", collected_at="",
                    summary_raw="", importance_score=score, send_recommended=send)

def test_apply_threshold_clears_below_cutoff():
    items = [_item("u1", 3.0), _item("u2", 5.0)]
    out = apply_threshold(items, thresholds={Category.DOMESTIC_FINANCE_AI: 4.0})
    assert out[0].send_recommended is False     # 3.0 < 4.0
    assert out[1].send_recommended is True       # 5.0 >= 4.0

def test_dedup_keeps_one_per_group():
    items = [_item("u1", 5.0, title="우리금융 생성형 AI 도입"),
             _item("u2", 6.0, title="우리금융 생성형 AI 도입 발표")]
    out = dedup(items)
    groups = {it.dedup_group for it in out}
    assert len(groups) == 1                       # 유사 제목 → 같은 그룹
    recommended = [it for it in out if it.send_recommended]
    assert len(recommended) == 1                  # 그룹 내 1건만 유지

def test_dedup_winner_prefers_recommended():
    # A: 높은 점수지만 임계값 미달로 send=False, B: 낮은 점수지만 send=True
    items = [_item("u1", 8.0, title="우리금융 생성형 AI 도입", send=False),
             _item("u2", 5.0, title="우리금융 생성형 AI 도입 발표", send=True)]
    out = dedup(items)
    groups = {it.dedup_group for it in out}
    assert len(groups) == 1                       # 유사 제목 → 같은 그룹
    recommended = [it for it in out if it.send_recommended]
    assert len(recommended) == 1                  # 그룹 내 정확히 1건 발송
    assert recommended[0].url == "u2"             # 살아있는(B) 항목이 winner

def test_dedup_keeps_dissimilar_titles_separate():
    items = [_item("u1", 5.0, title="우리금융 생성형 AI 도입"),
             _item("u2", 6.0, title="삼성전자 반도체 신규 투자")]
    out = dedup(items)
    groups = {it.dedup_group for it in out}
    assert len(groups) == 2                       # 서로 다른 주제 → 별개 그룹
    assert all(it.send_recommended for it in out) # 각자 그룹 winner이므로 유지

def test_dedup_empty_list_returns_empty():
    assert dedup([]) == []
    assert apply_threshold([], {}) == []

def test_apply_threshold_uses_default_cutoff_for_unlisted_category():
    items = [_item("u1", 4.0), _item("u2", 6.0)]
    out = apply_threshold(items, thresholds={})   # 카테고리 미등록 → 기본 5.0
    assert out[0].send_recommended is False        # 4.0 < 5.0
    assert out[1].send_recommended is True         # 6.0 >= 5.0
