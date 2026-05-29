"""데모 시드: 라이브 크롤링(헤드리스 브라우저)·Anthropic API 자격이 없는 환경에서
실제 파이프라인(parse→keyword→threshold→dedup→store)을 fixture HTML과 결정적 스코어러로
통과시켜 대시보드에 카드가 보이도록 data/news.db를 채운다.

라이브 경로는 run.py(WooriCollector + 실제 LLM)가 담당하며, 이 스크립트는 데모 표면 검증용이다.
"""
import json
from pathlib import Path

import yaml

from src.collectors.woori import parse_woori_html
from src.pipeline import run_pipeline
from src.storage import Storage

CONFIG = yaml.safe_load(Path("config.yaml").read_text(encoding="utf-8"))


def _demo_caller(item) -> str:
    """API 키 없이 데모용 결정적 점수. 'AI/생성형'이 강하게 들어간 제목을 높게 본다."""
    text = f"{item.title} {item.summary_raw}"
    if "생성형" in text or "플랫폼" in text:
        return json.dumps({"score": 6.5, "reason": "전 계열사 확대로 의미 있는 AI 도입", "send": True})
    return json.dumps({"score": 4.2, "reason": "AI 관련 활동이나 영향도는 제한적", "send": True})


def main():
    html = Path("tests/fixtures/woori_news.html").read_text(encoding="utf-8")
    collect = lambda: parse_woori_html(html, source_name="토스인베스트")
    storage = Storage("data/news.db")
    result = run_pipeline(collectors=[collect], storage=storage, config=CONFIG, caller=_demo_caller)
    print("데모 시드 완료:", result)


if __name__ == "__main__":
    main()
