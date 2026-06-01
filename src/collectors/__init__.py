"""수집기 패키지 + config 기반 수집기 팩토리.

소스 플러그인 구조: config.yaml의 sources 섹션에서 type=rss 항목을 읽어
RSSCollector 인스턴스 리스트를 만든다. 새 RSS 소스 추가 = config 항목 1개 추가로 끝.
(코드 변경 없이 소스 확장 — 확장성 요구 6.3)
"""

from __future__ import annotations

from src.collectors.rss import RSSCollector, parse_rss_feed
from src.collectors.base import Collector
from src.collectors.woori import TossNewsCollector

__all__ = ["RSSCollector", "parse_rss_feed", "Collector",
           "build_rss_collectors", "build_toss_collectors"]


def build_toss_collectors(config: dict) -> list[TossNewsCollector]:
    """config의 sources에서 type=toss 항목을 골라 TossNewsCollector 리스트 생성.

    국내 금융지주는 종목코드별 토스 뉴스피드로 수집(우리금융=woori, 나머지=국내 금융 AI).
    필요 키: toss_stock, category. name은 source_name(없으면 키 이름). 누락 시 건너뜀.
    """
    config = config or {}
    sources = config.get("sources", {}) or {}
    collectors: list[TossNewsCollector] = []
    for key, spec in sources.items():
        if not isinstance(spec, dict) or spec.get("type") != "toss":
            continue
        stock = str(spec.get("toss_stock") or "").strip()
        category = (spec.get("category") or "").strip()
        if not stock or not category:
            continue
        source_name = (spec.get("name") or key).strip()
        collectors.append(TossNewsCollector(stock_code=stock, category=category,
                                            source_name=source_name))
    return collectors


def build_rss_collectors(config: dict) -> list[RSSCollector]:
    """config의 sources에서 type=rss 항목만 골라 RSSCollector 리스트 생성.

    각 소스 dict 필요 키: url, category. name은 source_name으로 사용(없으면 키 이름).
    url 또는 category가 없으면 해당 소스는 건너뛴다(설정 오류로 전체가 죽지 않도록).
    """
    config = config or {}
    sources = config.get("sources", {}) or {}
    # 최신성 보호: 전역 max_feed_age_days(없으면 무제한). 소스별 max_age_days로 재정의 가능.
    global_max_age = config.get("max_feed_age_days")
    collectors: list[RSSCollector] = []
    for key, spec in sources.items():
        if not isinstance(spec, dict) or spec.get("type") != "rss":
            continue
        url = (spec.get("url") or "").strip()
        category = (spec.get("category") or "").strip()
        if not url or not category:
            continue
        source_name = (spec.get("name") or key).strip()
        max_age = spec.get("max_age_days", global_max_age)
        collectors.append(RSSCollector(url, category=category, source_name=source_name,
                                       max_age_days=max_age))
    return collectors
