# 수집 소스 상세

카테고리별 구체적 소스 정의. RSS URL은 변경될 수 있으므로 구현 시 응답을 확인하고, 죽은 피드는 화이트리스트에서 교체한다.

## 목차
1. 글로벌 AI — RSS
2. 글로벌 AI / 글로벌 금융 — WebSearch 보완
3. 국내 금융지주 — 토스인베스트 크롤링

---

## 1. 글로벌 AI — RSS

공개 RSS와 공식 블로그를 1차 소스로 사용한다 (무료·안정적). 후보:

```python
GLOBAL_AI_FEEDS = [
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://www.theverge.com/rss/index.xml",
    "https://venturebeat.com/category/ai/feed/",
    "https://www.wired.com/feed/tag/ai/latest/rss",
    "https://openai.com/blog/rss.xml",            # 공식 블로그
    "https://deepmind.google/blog/rss.xml",       # 변경 가능, 확인 필요
]
```

`feedparser`로 파싱한다. 각 엔트리에서 title, link, published(또는 updated), summary를 추출하여 NewsItem으로 정규화한다.

```python
import feedparser
d = feedparser.parse(feed_url)
for e in d.entries:
    item = NewsItem(
        id=make_id(e.link),
        category=Category.GLOBAL_AI,
        title=e.title,
        url=e.link,
        source=d.feed.get("title", feed_url),
        published_at=to_iso(e.get("published") or e.get("updated")),
        collected_at=now_iso(),
        summary_raw=strip_html(e.get("summary", ""))[:1000],
    )
```

빅테크 대상(Google DeepMind, Microsoft, OpenAI, Anthropic, Meta AI, AWS AI, Apple, NVIDIA)은 LLM 평가 단계에서 중요도로 걸러지므로, 수집 단계에서는 폭넓게 가져온다.

## 2. WebSearch 보완

RSS가 놓치는 헤드라인과 글로벌 금융사 AI 뉴스를 WebSearch로 보완한다. Claude의 WebSearch 도구를 사용한다 (ToolSearch로 `select:WebSearch` 로드 후 호출).

쿼리 패턴 (대상 기업 + AI 키워드 + 최신성):
```
"OpenAI" OR "Google DeepMind" OR "Anthropic" AI model launch 2026
"JP Morgan" OR "Goldman Sachs" OR "BlackRock" AI adoption strategy
```

WebSearch 결과는 RSS보다 일관성이 낮으므로, 결과의 출처가 화이트리스트(Reuters, FT, Bloomberg, WSJ, 각 기업 뉴스룸)에 있는지 확인하고 정규화한다. 중복은 url 기반 id로 자연 제거된다.

## 3. 국내 금융지주 — 토스인베스트 크롤링

**법적 검토 선행 필수**: robots.txt와 이용약관을 확인한다. 차단 시 강행하지 않는다.

종목 뉴스 페이지 (계열사 뉴스가 자동 포함되는 특성 활용):

```python
TOSS_STOCKS = {
    "우리금융지주": "https://www.tossinvest.com/stocks/A316140/news",
    "하나금융지주": "https://www.tossinvest.com/stocks/A086790/news",
    "KB금융":      "https://www.tossinvest.com/stocks/A105560/news",
    "신한지주":    "https://www.tossinvest.com/stocks/A055550/news",
    # NH농협금융: 비상장 — 별도 스텁(NhCollector)에서 처리
}
```

**크롤링 라이브러리: Scrapling**. 토스인베스트는 JS 렌더링 + 레이아웃 변경이 잦은 페이지라 Scrapling이 적합하다 (StealthyFetcher로 안티봇 회피, 적응형 셀렉터로 사이트 구조가 바뀌어도 유사도 기반 요소 재추적 → UI 개편 시 크롤러가 덜 깨짐).

수집 우선순위:
1. **내부 JSON API 우선 탐색** (네트워크 탭에서 뉴스 목록 API 확인). API가 있으면 가장 안정적이므로 `httpx`로 직접 호출한다.
2. API가 없으면 **Scrapling의 StealthyFetcher**로 렌더된 DOM을 가져와 적응형 셀렉터로 뉴스 항목을 추출한다.

```python
from scrapling.fetchers import StealthyFetcher

page = StealthyFetcher.fetch(url, headless=True, network_idle=True)
# 적응형 셀렉터: 구조 변경에 강하도록 auto_match 활용
items = page.css("article.news-item", auto_match=True)
for el in items:
    title = el.css_first("a::text")
    link = el.css_first("a::attr(href)")
    # → NewsItem 정규화
```

정적 RSS(글로벌 AI 등)는 Scrapling이 아니라 `feedparser`를 쓴다 — 브라우저 오버헤드가 불필요하기 때문이다.

정규화 시 category는 항상 `domestic_finance_ai`. 요구사항상 이 카테고리는 누락 방지 우선이므로 가벼운 내용도 수집하고, 필터 단계의 낮은 임계값으로 거른다.

NH농협금융은 비상장이라 종목 페이지가 없다. `NhCollector` 스텁만 만들고 빈 리스트 반환 + TODO. (대안: 농협금융 뉴스룸 RSS/검색을 추후 플러그인으로 추가)
