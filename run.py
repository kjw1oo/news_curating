import yaml
from pathlib import Path
import uvicorn
from src.storage import Storage
from src.collectors.websearch import WebSearchCollector
from src.collectors import build_rss_collectors, build_toss_collectors
from src.models import Category
from src.pipeline import run_pipeline
from src.api.app import create_app

_ROOT = Path(__file__).resolve().parent
CONFIG = yaml.safe_load((_ROOT / "config.yaml").read_text(encoding="utf-8"))
STORAGE = Storage("data/news.db")
_SEED = _ROOT / "data" / "websearch_seed.json"


def do_collect():
    # config의 type=toss 소스(국내 금융지주 종목 뉴스피드) 전부 연결.
    collectors = [c.collect for c in build_toss_collectors(CONFIG)]
    # config의 type=rss 소스(글로벌 AI/금융 + 매경 + 우리금융 RSS) 전부 연결.
    collectors += [c.collect for c in build_rss_collectors(CONFIG)]
    # WebSearch 시드가 있으면 글로벌·국내 카테고리 수집기를 함께 돌린다.
    # (시드는 오케스트레이팅 에이전트가 collect_websearch 경로로 생성)
    if _SEED.exists():
        collectors += [
            WebSearchCollector(str(_SEED), category=cat, source_name="WebSearch").collect
            for cat in Category.ALL
        ]
    return run_pipeline(collectors=collectors, storage=STORAGE, config=CONFIG)


app = create_app(storage=STORAGE, config=CONFIG, run_collect=do_collect)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
