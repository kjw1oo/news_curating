import json
from datetime import datetime, timezone
from urllib.parse import urlsplit

from src.collectors.base import Collector
from src.models import NewsItem, make_id


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _source_from_url(url: str) -> str:
    return urlsplit(url).netloc


def parse_search_results(
    results: list[dict], category: str, source_fallback: str = "WebSearch"
) -> list[NewsItem]:
    """WebSearch 결과 dict 리스트를 표준 NewsItem으로 정규화하는 순수 함수.

    각 dict 허용 키: title, url(필수), source, published_at, summary 또는 snippet.
    title/url이 없으면 스킵. source 없으면 URL 도메인 → source_fallback 순 폴백.
    """
    items: list[NewsItem] = []
    for r in results:
        title = (r.get("title") or "").strip()
        url = (r.get("url") or "").strip()
        if not title or not url:
            continue
        source = (r.get("source") or "").strip() or _source_from_url(url) or source_fallback
        published = (r.get("published_at") or "").strip()
        summary = (r.get("summary") or r.get("snippet") or "").strip()[:1000]
        items.append(NewsItem(
            id=make_id(url), category=category, title=title, url=url,
            source=source, published_at=published, collected_at=_now_iso(),
            summary_raw=summary,
        ))
    return items


class WebSearchCollector(Collector):
    """WebSearch는 런타임 Python API가 아니라 오케스트레이팅 에이전트의 도구다.
    에이전트가 검색 결과를 JSON 시드(카테고리별 dict)로 저장하면 이 수집기가
    해당 카테고리 섹션을 읽어 NewsItem으로 정규화한다.
    """

    def __init__(self, seed_path: str, category: str, source_name: str = "WebSearch"):
        self.seed_path = seed_path
        self.category = category
        self.source_name = source_name

    def collect(self) -> list[NewsItem]:
        with open(self.seed_path, encoding="utf-8") as f:
            data = json.load(f)
        results = data.get(self.category, [])
        return parse_search_results(results, self.category, self.source_name)
