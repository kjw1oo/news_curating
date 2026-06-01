from datetime import datetime, timezone
from urllib.parse import urljoin
from lxml import html as lxml_html
from src.collectors.base import Collector
from src.models import NewsItem, Category, make_id


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def parse_woori_html(html: str, source_name: str, base_url: str = "") -> list[NewsItem]:
    """순수 파싱 함수 — 네트워크 의존 없음.

    base_url이 주어지면 상대 href를 절대 URL로 해석한 뒤 make_id/저장한다.
    (실제 토스 DOM이 상대경로를 내보낼 때 id 불일치/링크 깨짐 방지)
    """
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
        if base_url:
            url = urljoin(base_url, url)
        time_nodes = node.cssselect("time")
        published = time_nodes[0].get("datetime", "").strip() if time_nodes else ""
        src_nodes = node.cssselect(".source")
        src = (src_nodes[0].text_content() or "").strip() if src_nodes else source_name
        desc_nodes = node.cssselect(".desc")
        desc = (desc_nodes[0].text_content().strip() if desc_nodes else "")[:1000]
        items.append(NewsItem(
            id=make_id(url), category=Category.WOORI, title=title,
            url=url, source=src, published_at=published, collected_at=_now_iso(),
            summary_raw=desc,
        ))
    return items


def _to_iso_kst(dt: str) -> str:
    """토스 createdAt('2026-06-01T06:30:00', KST naive)을 ISO8601(+09:00)로.

    이미 타임존(Z 또는 ±HH:MM)이 붙어 있으면 그대로 둔다.
    """
    s = (dt or "").strip()
    if not s:
        return ""
    tail = s[10:]  # 'T...' 이후 — 날짜부의 '-'와 구분
    if s.endswith("Z") or "+" in tail or "-" in tail:
        return s
    return s + "+09:00"


# 토스 기사 상세 URL 패턴(뉴스 id 기반). make_id의 안정 키이자 원문 링크.
TOSS_NEWS_URL = "https://www.tossinvest.com/news/"


def parse_toss_news_json(data: dict, source_name: str = "토스인베스트",
                         category: str = Category.WOORI) -> list[NewsItem]:
    """토스 내부 뉴스 API 응답(JSON)을 표준 NewsItem으로 정규화하는 순수 함수.

    구조: data['result']['body'] = [{id, title, summary, source:{name}, createdAt, ...}]
    난독화된 DOM 셀렉터 대신 공식 JSON API를 사용 — 배포에 영향받지 않고 안정적.
    category로 종목별 카테고리(woori / domestic_finance_ai 등)를 지정한다.
    """
    result = (data or {}).get("result") or {}
    body = result.get("body") if isinstance(result, dict) else None
    if not isinstance(body, list):
        return []
    items: list[NewsItem] = []
    for n in body:
        if not isinstance(n, dict):
            continue
        nid = str(n.get("id") or "").strip()
        title = (n.get("title") or "").strip()
        if not nid or not title:
            continue
        url = TOSS_NEWS_URL + nid
        src_obj = n.get("source") or {}
        src = (src_obj.get("name") if isinstance(src_obj, dict) else None) or source_name
        published = _to_iso_kst(n.get("createdAt") or n.get("updatedAt") or "")
        summary = (n.get("summary") or n.get("contentText") or "")[:1000]
        items.append(NewsItem(
            id=make_id(url), category=category, title=title, url=url,
            source=str(src).strip(), published_at=published, collected_at=_now_iso(),
            summary_raw=summary,
        ))
    return items


class TossNewsCollector(Collector):
    """토스 종목 뉴스피드 수집기(브라우저 불필요, httpx로 내부 JSON API 호출).

    국내 금융지주는 종목코드별로 이 수집기를 만들어 수집한다. code는 'A316140'에서 'A' 제거.
    """
    API = "https://wts-info-api.tossinvest.com/api/v2/news/companies/{code}?size={size}&orderBy=latest"

    def __init__(self, stock_code: str, category: str = Category.DOMESTIC_FINANCE_AI,
                 source_name: str = "토스인베스트", size: int = 30):
        self.stock_code = str(stock_code).lstrip("Aa") or stock_code
        self.category = category
        self.source_name = source_name
        self.size = size

    def collect(self) -> list[NewsItem]:
        import httpx
        url = self.API.format(code=self.stock_code, size=self.size)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": f"https://www.tossinvest.com/stocks/A{self.stock_code}/news",
            "Accept": "application/json",
        }
        r = httpx.get(url, headers=headers, timeout=20)
        r.raise_for_status()
        return parse_toss_news_json(r.json(), self.source_name, self.category)


class WooriCollector(TossNewsCollector):
    """우리금융지주(A316140) 토스 수집기 — 하위호환 프리셋(category=woori)."""
    category = Category.WOORI

    def __init__(self, source_name: str = "토스인베스트", stock_code: str = "316140", size: int = 30):
        super().__init__(stock_code=stock_code, category=Category.WOORI,
                         source_name=source_name, size=size)
