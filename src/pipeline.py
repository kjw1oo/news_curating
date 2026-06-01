from concurrent.futures import ThreadPoolExecutor
from src.filters.keyword import keyword_filter
from src.filters.scorer import score, default_caller
from src.filters.postprocess import apply_threshold, dedup
from src.filters.category_rules import apply_woori_priority


def run_pipeline(collectors, storage, config, caller=default_caller) -> dict:
    """collect → keyword → woori우선 → score → threshold → dedup → store. collectors는 collect()형 콜러블 리스트."""
    # 소스가 많고 피드별 네트워크 지연이 커서 순차 수집은 느리다 → I/O 병렬 수집.
    # 제출 순서대로 결과를 모아 dedup(greedy)의 결정성을 유지한다.
    collected = []
    with ThreadPoolExecutor(max_workers=min(24, max(1, len(collectors)))) as ex:
        futures = [ex.submit(c) for c in collectors]
        for f in futures:
            try:
                collected.extend(f.result())
            except Exception as e:
                print(f"수집 실패: {e}")
    passed = keyword_filter(collected, config.get("keyword_filters", []))
    # 우리금융 우선 적용: 우리금융그룹 관련 기사는 국내 금융 AI보다 woori를 우선 분류.
    passed = apply_woori_priority(passed, config.get("woori_entities"))
    scored = score(passed, caller=caller)
    gated = apply_threshold(scored, config.get("thresholds", {}))
    final = dedup(gated)
    # 재수집 보존: 이미 저장돼 채점된 항목은 이번 수집이 미채점이어도 기존 점수·발송
    # 상태를 덮어쓰지 않는다(키 없는 수집이 기존 채점/발송 이력을 지우는 것 방지).
    existing = {it.id: it for it in storage.query()}
    for it in final:
        prev = existing.get(it.id)
        if prev is None:
            continue
        if it.importance_score is None and prev.importance_score is not None:
            it.importance_score = prev.importance_score
            it.importance_reason = prev.importance_reason
            it.send_recommended = prev.send_recommended
        it.sent = prev.sent
        it.sent_at = prev.sent_at
    storage.upsert(final)
    # stored = 실제 영속화된 고유 항목 수. 서로 다른 피드가 동일 기사(같은 url→같은
    # id)를 반환하면 upsert가 1건으로 합치므로 len(final)이 아닌 distinct id로 센다.
    stored_ids = {i.id for i in final}
    return {
        "collected": len(collected),
        "kept": len(passed),
        "stored": len(stored_ids),
        "recommended": sum(1 for i in final if i.send_recommended),
    }
