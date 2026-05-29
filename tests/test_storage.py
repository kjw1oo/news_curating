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
