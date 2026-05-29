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
