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


# 토스 기사 페이지 URL 패턴(뉴스 id 기반). make_id(중복키)의 안정 키.
TOSS_NEWS_URL = "https://www.tossinvest.com/news/"
# 토스 상세 API(v1) — 응답의 linkUrl이 기사 원문(언론사) 주소다.
TOSS_DETAIL_API = "https://wts-info-api.tossinvest.com/api/v1/news/{nid}"


def fetch_link_url(client, nid: str, headers: dict | None = None) -> str | None:
    """토스 상세 API에서 기사 원문 URL(linkUrl)을 가져온다. 실패/없음이면 None.

    리스트 API에는 원문 링크가 없고 상세 API(v1)의 linkUrl에만 있다.
    """
    try:
        r = client.get(TOSS_DETAIL_API.format(nid=nid), headers=headers or {}, timeout=15)
        if r.status_code != 200:
            return None
        data = r.json()
        res = data.get("result") if isinstance(data, dict) else None
        if not isinstance(res, dict):
            res = data if isinstance(data, dict) else {}
        link = (res.get("linkUrl") or "").strip()
        return link or None
    except Exception:
        return None


def enrich_link_urls(items: list[NewsItem], resolver) -> list[NewsItem]:
    """각 토스 NewsItem의 url(토스 기사페이지)을 원문 url로 교체한다.

    **id(중복 제거 키)는 그대로 둔다** — 토스 기사페이지 기준으로 만든 안정 키를 유지해야
    기존 DB·재수집과 충돌하지 않는다. url 컬럼만 원문으로 바꾼다.
    resolver(nid) -> 원문 url 또는 None(없으면 기존 토스 url 유지).
    """
    for it in items:
        nid = (it.url or "").rsplit("/", 1)[-1]
        try:
            link = resolver(nid)
        except Exception:
            link = None
        if link:
            it.url = link
    return items


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
                 source_name: str = "토스인베스트", size: int = 30,
                 resolve_original: bool = True):
        self.stock_code = str(stock_code).lstrip("Aa") or stock_code
        self.category = category
        self.source_name = source_name
        self.size = size
        # 기사 url을 토스 페이지 대신 원문(linkUrl)으로 채울지 — 상세 API를 추가 호출한다.
        self.resolve_original = resolve_original

    def _link_map(self, client, nids: list[str], headers: dict) -> dict:
        """nid 목록의 원문 url을 병렬로 조회해 {nid: 원문url} 맵 생성(실패분은 제외)."""
        from concurrent.futures import ThreadPoolExecutor
        out: dict[str, str] = {}
        if not nids:
            return out
        with ThreadPoolExecutor(max_workers=min(6, len(nids))) as ex:
            for nid, link in zip(nids, ex.map(
                    lambda x: fetch_link_url(client, x, headers), nids)):
                if link:
                    out[nid] = link
        return out

    def collect(self) -> list[NewsItem]:
        import httpx
        url = self.API.format(code=self.stock_code, size=self.size)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": f"https://www.tossinvest.com/stocks/A{self.stock_code}/news",
            "Accept": "application/json",
        }
        with httpx.Client(timeout=20) as client:
            r = client.get(url, headers=headers)
            r.raise_for_status()
            items = parse_toss_news_json(r.json(), self.source_name, self.category)
            # url을 토스 페이지 → 원문 링크로 교체(id는 토스 기준 유지). 실패분은 토스 url 보존.
            if self.resolve_original and items:
                nids = [(it.url or "").rsplit("/", 1)[-1] for it in items]
                enrich_link_urls(items, self._link_map(client, nids, headers).get)
        return items


class WooriCollector(TossNewsCollector):
    """우리금융지주(A316140) 토스 수집기 — 하위호환 프리셋(category=woori)."""
    category = Category.WOORI

    def __init__(self, source_name: str = "토스인베스트", stock_code: str = "316140", size: int = 30):
        super().__init__(stock_code=stock_code, category=Category.WOORI,
                         source_name=source_name, size=size)
