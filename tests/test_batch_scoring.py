from src.batch_scoring import export_unscored, apply_scores, regate, prune_duplicates
from src.storage import Storage
from src.models import NewsItem, Category, make_id


def _item(url, title, category=Category.WOORI, score=None):
    return NewsItem(id=make_id(url), category=category, title=title, url=url,
                    source="토스", published_at="2026-06-01T00:00:00+09:00",
                    collected_at="2026-06-01T01:00:00+09:00", summary_raw="AI 도입",
                    keyword_passed=True, importance_score=score)


def test_export_unscored_includes_criteria(tmp_path):
    st = Storage(tmp_path / "b.db")
    st.upsert([_item("https://t/1", "우리금융 AI"),
               _item("https://t/2", "이미 채점됨", score=5.0)])
    out = export_unscored(st)
    assert len(out) == 1                       # 채점된 항목은 제외
    assert out[0]["title"] == "우리금융 AI"
    assert out[0]["category"] == Category.WOORI
    assert "criteria" in out[0] and out[0]["criteria"]   # 카테고리 평가기준 포함


def test_apply_scores_sets_fields_and_gates(tmp_path):
    st = Storage(tmp_path / "b.db")
    st.upsert([_item("https://t/1", "우리금융 AI 플랫폼"),
               _item("https://t/2", "약한 뉴스")])
    config = {"thresholds": {Category.WOORI: 4.0}}
    scores = {
        make_id("https://t/1"): {"score": 6.0, "reason": "의미 있음", "send": True},
        make_id("https://t/2"): {"score": 2.0, "reason": "약함", "send": True},
    }
    result = apply_scores(st, scores, config)
    assert result["scored"] == 2
    rows = {r.url: r for r in st.query()}
    assert rows["https://t/1"].importance_score == 6.0
    assert rows["https://t/1"].send_recommended is True       # 6.0 >= 4.0
    assert rows["https://t/2"].send_recommended is False      # 2.0 < 4.0 게이팅
    assert rows["https://t/2"].importance_reason == "약함"


def test_apply_scores_clamps_and_skips_unknown(tmp_path):
    st = Storage(tmp_path / "b.db")
    st.upsert([_item("https://t/1", "우리금융 AI")])
    config = {"thresholds": {Category.WOORI: 4.0}}
    scores = {
        make_id("https://t/1"): {"score": 99, "reason": "r", "send": True},
        "nonexistent_id": {"score": 5.0, "reason": "r", "send": True},
    }
    result = apply_scores(st, scores, config)
    assert result["scored"] == 1 and result["skipped"] == 1
    assert st.query()[0].importance_score == 10.0            # 99 → 10 클램프


def test_prune_duplicates_keeps_highest_score(tmp_path):
    st = Storage(tmp_path / "p.db")
    st.upsert([_item("https://t/1", "신한은행 생성형 AI 도입 발표", score=5.0),
               _item("https://t/2", "신한은행 생성형 AI 도입 발표 - 매일경제", score=8.0),
               _item("https://t/3", "전혀 다른 KB 마이데이터 신규 서비스", score=6.0)])
    res = prune_duplicates(st)
    assert res["removed"] == 1                       # 신한 2건 → 1건만 남김
    urls = {r.url for r in st.query()}
    assert "https://t/2" in urls                     # 높은 점수(8.0) 생존
    assert "https://t/1" not in urls                 # 낮은 점수(5.0) 삭제
    assert "https://t/3" in urls                     # 다른 뉴스는 보존


def test_prune_merges_divergent_korean_headlines(tmp_path):
    # 같은 사건(농협 애자일소다 투자)을 매체별로 제각각 헤드라인 — 같은 날짜·국내 카테고리.
    st = Storage(tmp_path / "k.db")
    titles = [
        "NH농협은행 애자일소다 AI 직접투자 결정",
        "농협은행 애자일소다 품으며 AI 내재화 가속",
        "농협銀 애자일소다 투자 에이전틱 AI뱅크 전환 - 전자신문",
    ]
    items = [NewsItem(id=make_id(f"https://x/{i}"), category=Category.DOMESTIC_FINANCE_AI,
                      title=t, url=f"https://x/{i}", source="s",
                      published_at="2026-05-28T08:00:00+09:00", collected_at="",
                      summary_raw="s", importance_score=6.0 + i, send_recommended=True)
             for i, t in enumerate(titles)]
    st.upsert(items)
    res = prune_duplicates(st)
    assert res["removed"] == 2            # 3건(같은 사건) → 최고점수 1건만
    assert len(st.query()) == 1
    assert st.query()[0].importance_score == 8.0   # 가장 높은 점수 생존


def test_prune_keeps_different_events_separate(tmp_path):
    # 같은 날짜·카테고리라도 다른 사건(공유 엔티티 부족)은 합치지 않는다.
    st = Storage(tmp_path / "k2.db")
    st.upsert([
        NewsItem(id=make_id("https://x/1"), category=Category.DOMESTIC_FINANCE_AI,
                 title="신한은행 생성형 AI 콜센터 도입", url="https://x/1", source="s",
                 published_at="2026-05-28T00:00:00+09:00", collected_at="", summary_raw="s",
                 importance_score=7.0),
        NewsItem(id=make_id("https://x/2"), category=Category.DOMESTIC_FINANCE_AI,
                 title="KB금융 마이데이터 자산관리 플랫폼 출시", url="https://x/2", source="s",
                 published_at="2026-05-28T00:00:00+09:00", collected_at="", summary_raw="s",
                 importance_score=7.0),
    ])
    assert prune_duplicates(st)["removed"] == 0      # 다른 사건 → 보존
    assert len(st.query()) == 2


def test_storage_delete_removes_items(tmp_path):
    st = Storage(tmp_path / "d.db")
    st.upsert([_item("https://t/1", "A"), _item("https://t/2", "B")])
    n = st.delete([make_id("https://t/1")])
    assert n == 1
    urls = {r.url for r in st.query()}
    assert urls == {"https://t/2"}


def test_regate_turns_off_below_raised_threshold(tmp_path):
    st = Storage(tmp_path / "b.db")
    st.upsert([_item("https://t/1", "AA"), _item("https://t/2", "BB")])   # 미채점
    # 채점으로 둘 다 발송추천 상태(초기 임계값 4.0 통과)
    apply_scores(st, {make_id("https://t/1"): {"score": 5.0, "reason": "r", "send": True},
                      make_id("https://t/2"): {"score": 7.0, "reason": "r", "send": True}},
                 {"thresholds": {Category.WOORI: 4.0}})
    assert sum(1 for r in st.query() if r.send_recommended) == 2
    # 임계값을 6.0으로 올려 재평가 → 5.0짜리만 OFF
    result = regate(st, {"thresholds": {Category.WOORI: 6.0}})
    assert result["turned_off"] == 1
    rows = {r.url: r for r in st.query()}
    assert rows["https://t/1"].send_recommended is False   # 5.0 < 6.0
    assert rows["https://t/2"].send_recommended is True     # 7.0 >= 6.0


def test_export_excludes_duplicate_news(tmp_path):
    st = Storage(tmp_path / "b.db")
    # 같은 이벤트를 두 매체가 보도(유사 제목, 다른 url) + 무관 기사 1건
    st.upsert([_item("https://t/1", "우리금융 생성형 AI 플랫폼 전 계열사 확대"),
               _item("https://t/2", "우리금융 생성형 AI 플랫폼 전 계열사 확대 발표"),
               _item("https://t/3", "KB금융 마이데이터 신규 서비스")])
    out = export_unscored(st)
    assert len(out) == 2                       # 같은 뉴스는 대표 1건으로 묶임(3→2)
    dup = [o for o in out if o["duplicates"] > 0]
    assert len(dup) == 1 and dup[0]["duplicates"] == 1


def test_apply_propagates_score_to_duplicate_group(tmp_path):
    st = Storage(tmp_path / "b.db")
    st.upsert([_item("https://t/1", "우리금융 생성형 AI 플랫폼 확대"),
               _item("https://t/2", "우리금융 생성형 AI 플랫폼 확대 공식 발표")])
    rep = export_unscored(st)[0]["id"]         # 대표만 채점
    config = {"thresholds": {Category.WOORI: 4.0}}
    apply_scores(st, {rep: {"score": 6.0, "reason": "의미", "send": True}}, config)
    rows = st.query()
    assert all(r.importance_score == 6.0 for r in rows)       # 그룹 전체에 전파
    assert sum(1 for r in rows if r.send_recommended) == 1    # 발송추천은 1건만


def test_apply_scores_dedup_keeps_one(tmp_path):
    st = Storage(tmp_path / "b.db")
    st.upsert([_item("https://t/1", "우리금융 생성형 AI 도입 발표"),
               _item("https://t/2", "우리금융 생성형 AI 도입 공식 발표")])
    config = {"thresholds": {Category.WOORI: 4.0}}
    scores = {
        make_id("https://t/1"): {"score": 6.0, "reason": "r", "send": True},
        make_id("https://t/2"): {"score": 7.0, "reason": "r", "send": True},
    }
    apply_scores(st, scores, config)
    recommended = [r for r in st.query() if r.send_recommended]
    assert len(recommended) == 1                              # 유사 제목 → 그룹당 1건
