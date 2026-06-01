"""범용 RSS/Atom 수집기.

source-researcher가 `_workspace/00b_source_research.md`에서 실측·채택한 글로벌
AI / 글로벌 금융 AI 피드를 표준 NewsItem 리스트로 정규화한다.

설계:
  - parse_rss_feed(raw_or_entries, category, source_name): **순수 함수**.
    네트워크 의존 없음 → 고정 fixture로 단위 테스트(woori.py 패턴).
  - RSSCollector(feed_url, category, source_name): fetch(네트워크) + parse 결합.
    fetch는 단위 테스트하지 않는다(불변 계약).

법적/robots 주의 (00b_source_research.md §2 robots.txt 검토 인용):
  - Google News RSS(`news.google.com/rss/search?...`)는 robots.txt가 `/rss/`를
    명시 허용하지 않는 **회색지대**다. 단 공개·무인증 피드 구독 엔드포인트이므로
    **크롤러가 아닌 피드 구독 방식**으로만 사용하고, 페이지 본문 크롤링 금지,
    폴링 주기를 수십 분 이상(config.collect_interval_hours=6h 권장)으로 유지해
    트래픽을 최소화한다. 본문 스크래핑은 하지 않고 피드 메타데이터만 읽는다.
  - techcrunch/arstechnica/blog.google/deepmind/MIT TR/wired/finextra:
    RSS 경로(/feed/, /rss/) robots 차단 없음 — 구독 문제 없음.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit

import feedparser

from src.collectors.base import Collector
from src.models import NewsItem, make_id


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _source_from_url(url: str) -> str:
    return urlsplit(url).netloc


def _struct_time_to_iso(st: time.struct_time) -> str:
    """feedparser가 파싱한 *_parsed(UTC struct_time) → ISO8601(UTC)."""
    dt = datetime(*st[:6], tzinfo=timezone.utc)
    return dt.isoformat(timespec="seconds")


def _normalize_published(entry: dict) -> str:
    """피드별 날짜 포맷 차이를 견고하게 흡수해 ISO8601 문자열로 반환.

    우선순위:
      1) feedparser의 published_parsed / updated_parsed (struct_time, UTC) — 가장 견고
      2) 원문 published / updated 문자열을 RFC822(email.utils)로 재파싱
      3) ISO8601 문자열(datetime.fromisoformat, 'Z' 보정) 시도
      4) 전부 실패 시 원문 문자열을 그대로 둔다(빈 문자열일 수도 있음).
    """
    for key in ("published_parsed", "updated_parsed"):
        st = entry.get(key)
        if st:
            try:
                return _struct_time_to_iso(st)
            except (TypeError, ValueError):
                pass

    for key in ("published", "updated", "pubDate", "date"):
        raw = (entry.get(key) or "").strip()
        if not raw:
            continue
        # RFC822 (RSS 표준: "Wed, 28 May 2026 08:30:00 GMT")
        try:
            dt = parsedate_to_datetime(raw)
            if dt is not None:
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.isoformat(timespec="seconds")
        except (TypeError, ValueError):
            pass
        # ISO8601 (Atom: "2026-05-28T08:30:00Z")
        try:
            iso = raw.replace("Z", "+00:00")
            dt = datetime.fromisoformat(iso)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.isoformat(timespec="seconds")
        except ValueError:
            pass
        return raw  # 알 수 없는 포맷이라도 정보 보존
    return ""


def _is_future_published(iso_published: str, *, grace_hours: int = 36) -> bool:
    """published_at가 현재보다 grace_hours 이상 미래면 True.

    뉴스 항목은 정의상 과거(이미 발행됨)다. 미래 발행일을 가진 항목은 실제
    기사가 아니라 **예정된 이벤트/웨비나 공지**(예: Finextra `/event-info/`)일
    가능성이 높다. 이런 항목은 뉴스 모니터링의 최신성/카테고리 정밀도를
    훼손하므로 수집 단계에서 제외한다. 타임존 흔들림·게시 직후 시차를
    grace_hours로 흡수해 정상 기사를 잘못 버리지 않는다.
    """
    if not iso_published:
        return False
    try:
        dt = datetime.fromisoformat(iso_published.replace("Z", "+00:00"))
    except ValueError:
        return False
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt > datetime.now(timezone.utc) + timedelta(hours=grace_hours)


def _entry_summary(entry: dict) -> str:
    """summary_raw용 본문 발췌. summary→content→subtitle 순, 1000자 컷."""
    text = (entry.get("summary") or "").strip()
    if not text:
        content = entry.get("content")
        if isinstance(content, list) and content:
            text = (content[0].get("value") or "").strip()
    if not text:
        text = (entry.get("subtitle") or "").strip()
    return text[:1000]


def _entry_source(entry: dict, url: str, source_name: str) -> str:
    """source 정규화.

    Google News RSS는 항목 source가 원기사 발행처를 담는다(entry.source.title).
    있으면 우선 사용하고, 없으면 URL 도메인 → 수집기 source_name 순으로 폴백.
    (00b §4: GoogleNews 항목은 원기사 도메인으로 재정규화 권장)
    """
    src = entry.get("source")
    if isinstance(src, dict):
        title = (src.get("title") or "").strip()
        if title:
            return title
    return _source_from_url(url) or source_name


def _is_too_old(iso_published: str, max_age_days) -> bool:
    """published_at가 max_age_days보다 오래되면 True.

    일부 피드(예: DeepMind 블로그)는 신규 항목이 드물 때 전체 아카이브(수개월~
    1년 전 항목 100건)를 반환해 모니터링 피드의 최신성을 훼손한다. 본 시스템은
    `collect_interval_hours`(6h) 주기의 **최신 뉴스 모니터**이므로, 너무 오래된
    아카이브 항목을 수집 단계에서 제외해 신선도/노이즈를 개선한다.

    max_age_days=None이면 비활성(하위호환). 날짜 파싱 실패 항목은 보존(False).
    """
    if not max_age_days:
        return False
    if not iso_published:
        return False
    try:
        dt = datetime.fromisoformat(iso_published.replace("Z", "+00:00"))
    except ValueError:
        return False
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt < datetime.now(timezone.utc) - timedelta(days=max_age_days)


def parse_rss_feed(raw_or_entries, category: str, source_name: str,
                   max_age_days=None) -> list[NewsItem]:
    """RSS/Atom 피드를 표준 NewsItem 리스트로 정규화하는 **순수 함수**.

    raw_or_entries:
      - str/bytes: 원시 피드 XML (feedparser.parse로 파싱)
      - list[dict]: 이미 파싱된 entries (테스트/사전파싱 경로)
    title 또는 link가 없는 항목은 스킵한다. id는 make_id(url)로 URL 정규화 후 생성.
    max_age_days: 지정 시 그보다 오래된 항목 제외(아카이브 덤프 노이즈 제거). None=무제한.
    """
    if isinstance(raw_or_entries, (str, bytes)):
        entries = feedparser.parse(raw_or_entries).entries
    else:
        entries = raw_or_entries

    items: list[NewsItem] = []
    for entry in entries:
        title = (entry.get("title") or "").strip()
        url = (entry.get("link") or "").strip()
        if not title or not url:
            continue
        published_at = _normalize_published(entry)
        # 미래 발행일 = 예정된 이벤트/웨비나 공지(뉴스 아님) → 정밀도 위해 제외.
        if _is_future_published(published_at):
            continue
        # 너무 오래된 아카이브 항목 제외(최신성 보호). max_age_days=None이면 무동작.
        if _is_too_old(published_at, max_age_days):
            continue
        items.append(NewsItem(
            id=make_id(url),
            category=category,
            title=title,
            url=url,
            source=_entry_source(entry, url, source_name),
            published_at=published_at,
            collected_at=_now_iso(),
            summary_raw=_entry_summary(entry),
        ))
    return items


class RSSCollector(Collector):
    """단일 RSS/Atom 피드 수집기.

    Google News 검색 RSS(쿼리형)도 URL만 다를 뿐 동일하게 처리한다.
    fetch는 feedparser에 위임(HTTP+파싱). 다수 피드는 build_rss_collectors로 묶는다.
    """

    def __init__(self, feed_url: str, category: str, source_name: str = "RSS",
                 max_age_days=None):
        self.feed_url = feed_url
        self.category = category
        self.source_name = source_name
        self.max_age_days = max_age_days

    def collect(self) -> list[NewsItem]:
        # httpx로 타임아웃(15s)을 걸어 fetch한 뒤 feedparser로 파싱한다.
        # feedparser.parse(url)은 자체 fetch에 타임아웃이 없어 느린 피드 하나가 전체
        # 수집을 막으므로, 명시적 타임아웃 + 피드별 graceful 실패로 분리한다.
        # (본문 크롤링 아님 — 피드 메타데이터만 소비)
        import httpx
        try:
            resp = httpx.get(
                self.feed_url, timeout=15.0, follow_redirects=True,
                headers={"User-Agent": "news_curating/1.0 (+RSS feed reader; contact via repo)"},
            )
            resp.raise_for_status()
            content = resp.content
        except Exception as e:
            print(f"RSS fetch 실패 {self.source_name}: {e}")
            return []
        parsed = feedparser.parse(content)
        return parse_rss_feed(parsed.entries, self.category, self.source_name,
                              max_age_days=self.max_age_days)
