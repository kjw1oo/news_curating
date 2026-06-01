"""배치 채점 — API 키 없이 에이전트(Claude)가 직접 중요도를 매기는 경로.

웹의 '수집 실행' 버튼은 서버 프로세스라 에이전트를 호출할 수 없어 실시간 채점에
ANTHROPIC_API_KEY가 필요하다. 이 모듈은 채점만 떼어내 배치화한다:

  1) export_unscored: 미채점 항목 + 카테고리별 평가기준을 JSON으로 내보낸다.
  2) (에이전트가 그 JSON을 읽어 기준대로 {score, reason, send} 판정 → scores.json 작성)
  3) apply_scores: 판정을 적용하고 임계값 게이팅 + 중복제거 후 저장한다.

수집은 실시간(버튼) 그대로, 채점만 배치(news-batch-scoring 스킬)로 수행한다.
"""
import argparse
import json
from pathlib import Path

import yaml

from src.storage import Storage
from src.filters.scorer import _PROMPTS
from src.filters.postprocess import apply_threshold, dedup, group_similar, duplicate_drop_ids
from src.models import Category


def prune_duplicates(storage: Storage) -> dict:
    """DB의 중복 뉴스를 물리 제거 — 같은 사건은 최고 점수 1건만 남긴다."""
    items = storage.query(max_age_days=0)
    drop = duplicate_drop_ids(items)
    storage.delete(drop)
    return {"removed": len(drop), "remaining": len(items) - len(drop)}

_ROOT = Path(__file__).resolve().parent.parent


def export_unscored(storage: Storage) -> list[dict]:
    """미채점 항목을 에이전트 채점용 페이로드로 내보낸다.

    같은 뉴스(유사 제목)는 한 그룹으로 묶어 **그룹당 대표 1건만** 내보낸다 — 동일 이벤트를
    여러 번 채점하지 않도록(중복 배제). 대표 채점 결과는 apply에서 그룹 전체에 전파된다.
    """
    groups = group_similar(storage.unscored())
    out = []
    for g in groups:
        rep = g[0]
        out.append({
            "id": rep.id,
            "category": rep.category,
            "title": rep.title,
            "source": rep.source,
            "published_at": rep.published_at,
            "summary": rep.summary_raw,
            "criteria": _PROMPTS.get(rep.category, _PROMPTS[Category.DOMESTIC_FINANCE_AI]),
            "duplicates": len(g) - 1,   # 같은 뉴스로 묶인 추가 건수(참고용)
        })
    return out


def apply_scores(storage: Storage, scores: dict, config: dict) -> dict:
    """scores={대표id:{score,reason,send}}를 적용 → 그룹 전체 전파 → 게이팅·dedup → 저장.

    같은 뉴스 그룹은 대표 점수를 그룹 전 항목에 전파한 뒤, dedup이 그룹당 1건만
    send_recommended로 남긴다. 점수는 0~10 클램프.
    """
    groups = group_similar(storage.unscored())
    target = []
    matched = 0
    for g in groups:
        rep = g[0]
        s = scores.get(rep.id)
        if s is None:
            continue
        try:
            sv = max(0.0, min(10.0, float(s["score"])))
        except (KeyError, ValueError, TypeError):
            continue
        matched += 1
        reason = str(s.get("reason", ""))
        send = bool(s.get("send", False))
        for it in g:   # 같은 뉴스(그룹) 전체에 동일 점수 전파
            it.importance_score = sv
            it.importance_reason = reason
            it.send_recommended = send
            target.append(it)
    gated = apply_threshold(target, config.get("thresholds", {}))
    final = dedup(gated)
    storage.upsert(final)
    # 채점 후 중복 뉴스 물리 제거 — 같은 사건은 최고 점수 1건만 남긴다.
    pruned = prune_duplicates(storage)
    return {
        "scored": len(target),               # 점수가 적용된 총 항목 수(전파 포함)
        "unique": matched,                   # 실제 채점한 고유 뉴스 수
        "recommended": sum(1 for i in storage.query(max_age_days=0) if i.send_recommended),
        "skipped": len(scores) - matched,    # 어느 그룹 대표와도 매칭 안 된 점수 항목
        "removed_duplicates": pruned["removed"],
    }


def regate(storage: Storage, config: dict) -> dict:
    """저장된 항목의 send_recommended를 현재 임계값으로 재평가한다.

    임계값을 올린 뒤 기존 항목에 즉시 반영(초과분만 OFF — 재수집/재채점 불필요).
    임계값 상향은 단조 감소이므로 안전하게 끄기만 한다.
    """
    thresholds = config.get("thresholds", {})
    items = storage.query(max_age_days=0)
    changed = []
    for it in items:
        cutoff = thresholds.get(it.category, 5.0)
        if it.send_recommended and (it.importance_score is None or it.importance_score < cutoff):
            it.send_recommended = False
            changed.append(it)
    if changed:
        storage.upsert(changed)
    return {"turned_off": len(changed),
            "recommended_now": sum(1 for it in items if it.send_recommended)}


def _load_config() -> dict:
    return yaml.safe_load((_ROOT / "config.yaml").read_text(encoding="utf-8"))


def main(argv=None):
    ap = argparse.ArgumentParser(description="뉴스 배치 채점 (키 없이 에이전트가 채점)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    pe = sub.add_parser("export", help="미채점 항목을 JSON으로 내보내기")
    pe.add_argument("--db", default="data/news.db")
    pe.add_argument("--out", default="data/_unscored.json")

    pa = sub.add_parser("apply", help="에이전트 점수(JSON)를 적용·게이팅·저장")
    pa.add_argument("--db", default="data/news.db")
    pa.add_argument("--scores", default="data/_scores.json")

    pr = sub.add_parser("regate", help="현재 임계값으로 send_recommended 재평가")
    pr.add_argument("--db", default="data/news.db")

    pp = sub.add_parser("prune", help="중복 뉴스 물리 제거(최고 점수 1건만 남김)")
    pp.add_argument("--db", default="data/news.db")

    args = ap.parse_args(argv)
    st = Storage(args.db)

    if args.cmd == "export":
        data = export_unscored(st)
        Path(args.out).write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"미채점 {len(data)}건 → {args.out}")
    elif args.cmd == "apply":
        scores = json.loads(Path(args.scores).read_text(encoding="utf-8"))
        result = apply_scores(st, scores, _load_config())
        print(f"채점 적용: {result}")
    elif args.cmd == "regate":
        print(f"재평가: {regate(st, _load_config())}")
    elif args.cmd == "prune":
        print(f"중복 제거: {prune_duplicates(st)}")


if __name__ == "__main__":
    main()
