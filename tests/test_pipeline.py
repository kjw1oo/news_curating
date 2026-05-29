from src.pipeline import run_pipeline
from src.storage import Storage
from src.models import NewsItem, Category, make_id


def _raw(url, title, summary="생성형 AI 도입"):
    return NewsItem(id=make_id(url), category=Category.DOMESTIC_FINANCE_AI, title=title, url=url,
                    source="토스", published_at="2026-05-29T00:00:00+09:00", collected_at="2026-05-29T01:00:00+09:00",
                    summary_raw=summary)


def test_run_pipeline_collects_filters_scores_stores(tmp_path):
    st = Storage(tmp_path / "p.db")
    collected = [_raw("https://t/1", "우리금융 AI 플랫폼 확대"),
                 _raw("https://t/2", "우리은행 점포 오픈", summary="신규 영업점 개설")]
    fake_collect = lambda: collected
    fake_caller = lambda item: '{"score": 6.0, "reason": "의미 있음", "send": true}'
    config = {"keyword_filters": ["AI"], "thresholds": {Category.DOMESTIC_FINANCE_AI: 4.0}}

    result = run_pipeline(collectors=[fake_collect], storage=st, config=config, caller=fake_caller)

    stored = st.query()
    assert len(stored) == 1                         # "점포 오픈"은 키워드 미통과로 제외
    assert stored[0].importance_score == 6.0
    assert stored[0].send_recommended is True
    assert result["collected"] == 2 and result["stored"] == 1
