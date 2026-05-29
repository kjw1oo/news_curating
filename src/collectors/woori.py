from datetime import datetime, timezone
from lxml import html as lxml_html
from src.collectors.base import Collector
from src.models import NewsItem, Category, make_id


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def parse_woori_html(html: str, source_name: str) -> list[NewsItem]:
    """순수 파싱 함수 — 네트워크 의존 없음."""
    tree = lxml_html.fromstring(html)
    items: list[NewsItem] = []
    for node in tree.cssselect("li.news-item"):
        a = node.cssselect("a")
        if not a:
            continue
        url = a[0].get("href", "").strip()
        title = (a[0].text_content() or "").strip()
        if not url or not title:
            continue
        time_nodes = node.cssselect("time")
        published = time_nodes[0].get("datetime", "").strip() if time_nodes else ""
        src_nodes = node.cssselect(".source")
        src = src_nodes[0].text_content().strip() if src_nodes else source_name
        desc_nodes = node.cssselect(".desc")
        desc = (desc_nodes[0].text_content().strip() if desc_nodes else "")[:1000]
        items.append(NewsItem(
            id=make_id(url), category=Category.DOMESTIC_FINANCE_AI, title=title,
            url=url, source=src, published_at=published, collected_at=_now_iso(),
            summary_raw=desc,
        ))
    return items


class WooriCollector(Collector):
    category = Category.DOMESTIC_FINANCE_AI
    URL = "https://www.tossinvest.com/stocks/A316140/news"

    # robots.txt/이용약관 미확인 시 강행 금지. 토스인베스트가 크롤링을 차단하면
    # 이 collect() 경로 대신 RSS/WebSearch 대체 수집기로 전환할 것 (Task 10에서 검증).
    def __init__(self, source_name: str = "토스인베스트"):
        self.source_name = source_name

    def collect(self) -> list[NewsItem]:
        from scrapling.fetchers import StealthyFetcher
        page = StealthyFetcher.fetch(self.URL, headless=True, network_idle=True)
        # scrapling 0.4.8: 렌더된 HTML은 Selector.html_content 속성으로 노출됨
        # (.venv 패키지에서 scrapling.Selector dir 검사로 확인. .body도 존재).
        return parse_woori_html(page.html_content, self.source_name)
