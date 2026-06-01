"""전체 소스 수집 → 미채점으로 로컬 DB 저장.

프로젝트 루트를 CWD로 두고 실행한다(src/, config.yaml, data/ 참조).
config의 type=toss(국내 금융지주 종목 뉴스) + type=rss(글로벌/매경/우리금융) + WebSearch 시드를
모두 모아 run_pipeline에 넘긴다. 수집은 ThreadPool로 병렬화돼 있고(프록시 throttle 대응),
키워드 필터·우리금융 우선분류·중복 제거·재수집 점수보존·중복 물리제거(prune)까지 파이프라인이 처리한다.
ANTHROPIC_API_KEY가 없으면 채점은 즉시 스킵돼 항목이 '미채점'으로 저장된다(이후 배치 채점 단계가 채움).
"""
import time
import yaml
from pathlib import Path

from src.storage import Storage
from src.collectors.websearch import WebSearchCollector
from src.collectors import build_rss_collectors, build_toss_collectors
from src.models import Category
from src.pipeline import run_pipeline

CONFIG = yaml.safe_load(Path("config.yaml").read_text(encoding="utf-8"))
STORAGE = Storage("data/news.db")
_SEED = Path("data/websearch_seed.json")

collectors = [c.collect for c in build_toss_collectors(CONFIG)]
collectors += [c.collect for c in build_rss_collectors(CONFIG)]
if _SEED.exists():
    collectors += [
        WebSearchCollector(str(_SEED), category=cat, source_name="WebSearch").collect
        for cat in Category.ALL
    ]

t = time.time()
res = run_pipeline(collectors=collectors, storage=STORAGE, config=CONFIG)
unscored = len(STORAGE.unscored())
print(f"수집 완료 {time.time() - t:.1f}s: {res} | 미채점 {unscored}건")
