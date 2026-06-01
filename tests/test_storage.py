from src.models import NewsItem, Category, make_id
from src.storage import Storage

def _item(url, score=None):
    return NewsItem(id=make_id(url), category=Category.DOMESTIC_FINANCE_AI,
                    title="t", url=url, source="토스", published_at="2026-05-29T00:00:00+09:00",
                    collected_at="2026-05-29T01:00:00+09:00", summary_raw="s",
                    importance_score=score)

def test_upsert_is_idempotent(tmp_path):
    st = Storage(tmp_path / "t.db")
    st.upsert([_item("https://t.com/1")])
    st.upsert([_item("https://t.com/1")])      # 같은 url → 같은 id
    assert len(st.query()) == 1

def test_query_filters_by_min_score(tmp_path):
    st = Storage(tmp_path / "t.db")
    st.upsert([_item("https://t.com/1", score=2.0), _item("https://t.com/2", score=9.0)])
    high = st.query(min_score=5.0)
    assert len(high) == 1 and high[0].url == "https://t.com/2"

def test_query_filters_by_category(tmp_path):
    from src.models import NewsItem, Category, make_id
    st = Storage(tmp_path / "t.db")
    dom = _item("https://t.com/1")  # domestic_finance_ai
    glob = NewsItem(id=make_id("https://t.com/2"), category=Category.GLOBAL_AI,
                    title="t", url="https://t.com/2", source="s",
                    published_at="2026-05-29T00:00:00+09:00", collected_at="2026-05-29T01:00:00+09:00",
                    summary_raw="s")
    st.upsert([dom, glob])
    res = st.query(category=Category.DOMESTIC_FINANCE_AI)
    assert len(res) == 1 and res[0].category == Category.DOMESTIC_FINANCE_AI

def _dated(url, published_at):
    return NewsItem(id=make_id(url), category=Category.GLOBAL_AI, title="t", url=url,
                    source="s", published_at=published_at, collected_at="", summary_raw="s")

def test_query_filters_by_max_age_days(tmp_path):
    from datetime import date
    st = Storage(tmp_path / "t.db")
    st.upsert([_dated("https://t.com/recent", "2026-05-28T00:00:00+09:00"),   # 4일 전
               _dated("https://t.com/old", "2026-05-01T00:00:00+09:00")])      # 31일 전
    today = date(2026, 6, 1)
    res = st.query(max_age_days=7, today=today)
    assert len(res) == 1 and res[0].url == "https://t.com/recent"
    assert len(st.query(max_age_days=0, today=today)) == 2     # 0 = 전체
    assert len(st.query(today=today)) == 2                      # 미지정 = 전체

def test_max_age_keeps_undated_items(tmp_path):
    from datetime import date
    st = Storage(tmp_path / "t.db")
    st.upsert([_dated("https://t.com/x", "")])                  # 날짜 불명
    assert len(st.query(max_age_days=7, today=date(2026, 6, 1))) == 1   # 숨기지 않음

def test_bool_fields_roundtrip_as_bool(tmp_path):
    from src.models import NewsItem, Category, make_id
    st = Storage(tmp_path / "t.db")
    it = NewsItem(id=make_id("https://t.com/9"), category=Category.DOMESTIC_FINANCE_AI,
                  title="t", url="https://t.com/9", source="s",
                  published_at="2026-05-29T00:00:00+09:00", collected_at="2026-05-29T01:00:00+09:00",
                  summary_raw="s", keyword_passed=True, send_recommended=True)
    st.upsert([it])
    got = st.query()[0]
    assert got.keyword_passed is True and got.send_recommended is True
    assert isinstance(got.keyword_passed, bool)   # 1이 아니라 bool로 복원
