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

def test_dedup_groups_korean_josa_variants():
    # 동일 이벤트, 한글 조사만 다른 변형 → 같은 그룹으로 묶여야 한다(조사 정규화).
    items = [_item("u1", 5.0, title="우리금융 생성형 AI 플랫폼 전 계열사 도입"),
             _item("u2", 6.0, title="우리금융이 생성형 AI 플랫폼을 전 계열사에 도입")]
    out = dedup(items)
    assert len({it.dedup_group for it in out}) == 1
    assert sum(1 for it in out if it.send_recommended) == 1


def test_strip_josa_does_not_over_normalize_roots():
    # 조사처럼 끝나도 어근이 짧아지면 보존(은행/투자/데이터 등 과잉제거 금지).
    from src.filters.postprocess import _strip_josa
    for root in ("데이터", "은행", "투자", "하나", "지주", "거버넌스"):
        assert _strip_josa(root) == root
    # 실제 조사 부착형은 정규화
    assert _strip_josa("우리금융이") == "우리금융"
    assert _strip_josa("플랫폼을") == "플랫폼"
    assert _strip_josa("계열사에서") == "계열사"


def test_dedup_keeps_korean_distinct_topics_separate():
    # 조사 정규화가 서로 다른 주제를 잘못 합치지 않는지(FP 방지).
    items = [_item("u1", 5.0, title="우리금융 마이데이터 서비스 출시"),
             _item("u2", 6.0, title="삼성전자 반도체 신규 투자 발표")]
    out = dedup(items)
    assert len({it.dedup_group for it in out}) == 2


def test_dedup_empty_list_returns_empty():
    assert dedup([]) == []
    assert apply_threshold([], {}) == []

def test_apply_threshold_uses_default_cutoff_for_unlisted_category():
    items = [_item("u1", 4.0), _item("u2", 6.0)]
    out = apply_threshold(items, thresholds={})   # 카테고리 미등록 → 기본 5.0
    assert out[0].send_recommended is False        # 4.0 < 5.0
    assert out[1].send_recommended is True         # 6.0 >= 5.0
