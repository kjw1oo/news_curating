from src.filters.keyword import keyword_filter
from src.filters.scorer import score, default_caller
from src.filters.postprocess import apply_threshold, dedup


def run_pipeline(collectors, storage, config, caller=default_caller) -> dict:
    """collect → keyword → score → threshold → dedup → store. collectors는 collect()형 콜러블 리스트."""
    collected = []
    for collect in collectors:
        try:
            collected.extend(collect())
        except Exception as e:
            print(f"수집 실패: {e}")
    passed = keyword_filter(collected, config.get("keyword_filters", []))
    scored = score(passed, caller=caller)
    gated = apply_threshold(scored, config.get("thresholds", {}))
    final = dedup(gated)
    storage.upsert(final)
    return {"collected": len(collected), "kept": len(passed), "stored": len(final)}
