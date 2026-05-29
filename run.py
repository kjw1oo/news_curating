import yaml
from pathlib import Path
import uvicorn
from src.storage import Storage
from src.collectors.woori import WooriCollector
from src.pipeline import run_pipeline
from src.api.app import create_app

CONFIG = yaml.safe_load((Path(__file__).resolve().parent / "config.yaml").read_text(encoding="utf-8"))
STORAGE = Storage("data/news.db")


def do_collect():
    woori = WooriCollector(source_name="토스인베스트")
    return run_pipeline(collectors=[woori.collect], storage=STORAGE, config=CONFIG)


app = create_app(storage=STORAGE, config=CONFIG, run_collect=do_collect)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
