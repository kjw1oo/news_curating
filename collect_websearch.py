"""WebSearch 1차 수집 러너.

WebSearch는 런타임 Python API가 아니라 오케스트레이팅 에이전트(Claude)의 도구다.
에이전트가 3개 카테고리로 실제 검색을 수행해 data/websearch_seed.json(카테고리별 결과)을
저장하면, 이 스크립트가 WebSearchCollector로 정규화 → 파이프라인을 통과시켜 data/news.db에 적재한다.

ANTHROPIC_API_KEY가 있으면 실제 LLM 스코어러(default_caller)를, 없으면 키워드 신호 기반
결정적 휴리스틱 caller를 사용한다(1차 표면 검증용). 라이브 점수는 run.py 경로가 담당한다.
"""
import json
import os
from pathlib import Path

import yaml

from src.collectors.websearch import WebSearchCollector
from src.filters.scorer import default_caller
from src.models import Category
from src.pipeline import run_pipeline
from src.storage import Storage

_ROOT = Path(__file__).resolve().parent
CONFIG = yaml.safe_load((_ROOT / "config.yaml").read_text(encoding="utf-8"))
SEED = _ROOT / "data" / "websearch_seed.json"

_BASE = {
    Category.GLOBAL_AI: 6.5,
    Category.GLOBAL_FINANCE_AI: 6.0,
    Category.DOMESTIC_FINANCE_AI: 4.8,
}
_SIGNALS = [
    (["valuation", "funding round", "billion", "$30", "투자", "억 원", "억원", "협약", "파트너십"], 1.5, "대규모 투자·협력 신호"),
    (["생성형", "platform", "플랫폼", "agent", "에이전트", "에이전틱"], 1.0, "생성형·에이전트 플랫폼"),
    (["strategy", "전략", " ax", "전환", "도입", "구축"], 0.6, "공식 전략·도입"),
    (["fed", "guidance", "regulat", "규제", "감독"], 0.5, "규제·감독 변화"),
]


def _heuristic_caller(item) -> str:
    """API 키 없는 1차 점수. 키워드 신호로 가중. 라이브는 default_caller가 대체."""
    text = f"{item.title} {item.summary_raw}".lower()
    score = _BASE.get(item.category, 5.0)
    hits = []
    for kws, weight, label in _SIGNALS:
        if any(k in text for k in kws):
            score += weight
            hits.append(label)
    score = max(0.0, min(10.0, round(score, 1)))
    reason = "휴리스틱 1차 평가 — " + (", ".join(hits) if hits else "일반 AI 관련 동향")
    return json.dumps({"score": score, "reason": reason, "send": True}, ensure_ascii=False)


def main():
    if not SEED.exists():
        raise SystemExit(f"시드 없음: {SEED} — 먼저 WebSearch 결과를 저장하세요.")
    caller = default_caller if os.environ.get("ANTHROPIC_API_KEY") else _heuristic_caller
    collectors = [
        WebSearchCollector(str(SEED), category=cat, source_name="WebSearch").collect
        for cat in Category.ALL
    ]
    storage = Storage("data/news.db")
    result = run_pipeline(collectors=collectors, storage=storage, config=CONFIG, caller=caller)
    mode = "LLM" if caller is default_caller else "휴리스틱"
    print(f"WebSearch 1차 수집 완료 ({mode} 점수): {result}")


if __name__ == "__main__":
    main()
