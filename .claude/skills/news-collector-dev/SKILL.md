---
name: news-collector-dev
description: "뉴스 수집 계층을 구현. RSS 피드 파싱, WebSearch 기반 수집, 토스인베스트 종목 뉴스 크롤링을 통해 글로벌 AI·글로벌 금융 AI·국내 금융지주 뉴스를 표준 NewsItem으로 정규화. 수집기/크롤러/RSS/소스 플러그인 구현·수정·소스 추가 시 반드시 이 스킬을 사용."
---

# News Collector Dev — 수집 계층 구현

3개 카테고리의 뉴스를 이질적 소스에서 가져와 표준 NewsItem으로 정규화하는 수집 계층을 구현하는 스킬.

## 시작 전 필수

작업 시작 전 `_workspace/01_architect_schema.md`(없으면 `references/data-schema.md`를 본 스킬과 같은 패키지의 news-system-design에서)를 Read하여 NewsItem 필드명·타입·id 생성 규칙을 정확히 따른다. 필드명을 임의로 바꾸면 filter-dev가 깨진다.

## 소스 플러그인 구조

모든 수집기는 동일 인터페이스를 구현하여 소스 추가가 파일 1개로 끝나게 한다. 이것이 확장성 요구(6.3)의 핵심이다.

```python
class Collector:
    category: str
    def collect(self) -> list[NewsItem]: ...

COLLECTORS = [RssCollector(...), WebSearchCollector(...), TossCollector(...)]
def collect_all() -> list[NewsItem]:
    items = []
    for c in COLLECTORS:
        try:
            items += _with_retry(c.collect, retries=cfg.retry_max)
        except Exception as e:
            log.error(f"{c.__class__.__name__} 수집 실패: {e}")  # 건너뛰고 계속
    return items
```

## 카테고리별 소스 전략

| 카테고리 | 1차 소스 | 보완 | 구현 |
|----------|---------|------|------|
| global_ai | 공개 RSS (TechCrunch, The Verge, VentureBeat 등) + 공식 블로그 RSS | WebSearch | `rss.py` + `websearch.py` |
| global_finance_ai | 금융사 뉴스룸/Reuters·FT 헤드라인 RSS | WebSearch (대상 기업 키워드) | `websearch.py` 주력 |
| domestic_finance_ai | 토스인베스트 종목 뉴스 크롤링 | - | `toss.py` |

구체적 RSS URL, WebSearch 쿼리 패턴, 토스인베스트 크롤링 상세는 `references/sources.md`를 Read한다.

## 정규화 원칙

- **id**: `sha256(url)[:16]`. URL 정규화(쿼리스트링 제거, 소문자화) 후 해시하여 같은 기사의 변형 URL을 통합한다.
- **published_at / collected_at**: ISO 8601 + 타임존. 소스가 상대시간("3시간 전")이면 수집 시각 기준으로 환산.
- **category**: 수집기마다 고정 (RSS 글로벌 AI 수집기는 항상 `global_ai`).
- **summary_raw**: LLM 평가 입력용. 본문 전체가 크면 앞부분 1000자 정도로 자른다.
- collector 단계에서는 keyword_passed/importance_* 필드를 기본값으로 둔다 (filter가 채움).

## 신뢰성 요구

- **재시도**: 네트워크 실패 시 최소 3회 (지수 백오프). 최종 실패 시 운영자 알림 훅 호출 + 로그.
- **화이트리스트**: 허위·루머 출처 차단을 위해 신뢰 출처 목록을 config 또는 수집기 상수로 관리. 화이트리스트 외 출처는 수집하지 않거나 낮은 신뢰도 플래그.
- **법적 검토**: 토스인베스트 크롤링 전 robots.txt와 이용약관을 확인한다. 차단/제약이 있으면 강행하지 않고 RSS/WebSearch 대체 경로로 전환하며 그 사유를 코드 주석에 남긴다.

## 미확정 항목 처리

NH농협금융은 비상장 계열사로 토스인베스트 종목 페이지가 없을 수 있다. 플러그인 스텁(`NhCollector(Collector)`)만 만들어 두고 `collect()`는 빈 리스트 + TODO 주석으로 남긴다. 미리 구현하지 않는다.

## 후속/재실행

이전 산출물(`_workspace/02_collector/` 또는 `src/collectors/`)이 존재하면 Read하여 기존 구현을 파악하고 피드백 부분만 수정한다. 소스 추가 요청 시 새 Collector 파일 1개 + COLLECTORS 등록 1줄만 추가한다.
