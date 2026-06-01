# 00b. 소스 리서치 — 실측 검증 결과 (global_ai / global_finance_ai)

> 작성: source-researcher · 날짜: 2026-05-30
> 방법: 후보 RSS/Atom를 실제 fetch(`requests`) 후 `xml.etree`로 파싱하여 항목 수·최신성·발행빈도·카테고리 적합도를 **실측**. 추측값 없음.
> 검증 환경 주의: 이 환경엔 `feedparser`/`httpx` 미설치(Python 3.8). stdlib `xml.etree` + `requests`로 동등 측정함. 런타임 구현 시엔 `feedparser` 사용 권장(네임스페이스/인코딩 견고성).
> 적합도 측정 키워드: AI = `ai/llm/gpt/gemini/claude/openai/anthropic/deepmind/model/agent/nvidia/...` , 금융 = `bank/finance/fintech/trading/invest/market/fed/hedge fund/jpmorgan/...`. finance_ai는 **AI∩금융 동시 매칭 비율**(`ai_and_fin_ratio`)을 핵심 지표로 사용.

---

## 1. 채택 소스 (collector-dev 구현용)

### 1-A. global_ai

| 소스 | URL | 방식 | 발행빈도(items/wk) | 최신성 | 적합도 | 등급 |
|------|-----|------|------|--------|--------|------|
| **GoogleNews: AI 핵심** | `https://news.google.com/rss/search?q=(OpenAI+OR+Anthropic+OR+%22Google+DeepMind%22+OR+%22AI+model%22)+when:7d&hl=en-US&gl=US&ceid=US:en` | feedparser | ~103/wk | 0.2일 | **0.99** | 채택(주력) |
| **MIT Technology Review – AI** | `https://www.technologyreview.com/topic/artificial-intelligence/feed` | feedparser | ~7/wk | 0.9일 | **1.00** | 채택(고품질) |
| **TechCrunch – AI** | `https://techcrunch.com/category/artificial-intelligence/feed/` | feedparser | ~107/wk | 0.4일 | 0.85 | 채택 |
| **Ars Technica – AI** | `https://arstechnica.com/ai/feed/` | feedparser | ~14/wk | 0.6일 | 0.75 | 채택 |
| **Google AI Blog (blog.google)** | `https://blog.google/technology/ai/rss/` | feedparser | ~6/wk | 0.5일 | 0.80 | 채택(1차 출처) |
| **Google DeepMind Blog** | `https://deepmind.google/blog/rss.xml` | feedparser | ~2/wk | 8.5일 | 0.65 | 보조(1차 출처·저빈도) |
| **MarkTechPost** | `https://www.marktechpost.com/feed/` | feedparser | ~40/wk | 0.2일 | 0.80 | 보조(테크 매체, 중복 가능) |
| **Wired – AI** | `https://www.wired.com/feed/tag/ai/latest/rss` | feedparser | ~31/wk | 0.4일 | 0.70 | 보조 |

### 1-B. global_finance_ai

| 소스 | URL | 방식 | 발행빈도 | 최신성 | AI∩금융 적합도 | 등급 |
|------|-----|------|------|--------|--------|------|
| **GoogleNews: AI in finance** | `https://news.google.com/rss/search?q=AI+finance+OR+fintech+OR+bank&hl=en-US&gl=US&ceid=US:en` | feedparser | ~3.3/wk* | 0.1일 | **0.91** | 채택(주력) |
| **GoogleNews: Wall Street + AI** | `https://news.google.com/rss/search?q=(%22Wall+Street%22+OR+%22JPMorgan%22+OR+%22Goldman%22+OR+%22hedge+fund%22)+AI+when:30d&hl=en-US&gl=US&ceid=US:en` | feedparser | ~25/wk | 1.1일 | **0.80** | 채택(주력) |
| **GoogleNews: AI banking/trading** | `https://news.google.com/rss/search?q=%22artificial+intelligence%22+(bank+OR+%22hedge+fund%22+OR+trading+OR+fintech)+when:30d&hl=en-US&gl=US&ceid=US:en` | feedparser | ~16/wk | 0.4일 | **0.64** | 채택 |
| **Finextra – Headlines** | `https://www.finextra.com/rss/headlines.aspx` | feedparser | ~4.5/wk | (주의) | 0.18 | 보조(핀테크 1차, AI 필터 필수) |

\* Google News 검색 RSS는 최대 100건을 반환하나 정렬·날짜분포상 주간 환산이 낮게 잡힐 수 있음. 실제 신규 유입은 일 단위로 충분(최신 0.1일). 빈도보다 **적합도·최신성**이 우수.

---

## 2. 탈락 소스 (사유 명시)

| 소스 | URL | 사유 |
|------|-----|------|
| OpenAI News RSS | `https://openai.com/news/rss.xml` | **접속 불가** — SSL 핸드셰이크 오류 2회 재시도 모두 실패. 환경/CDN 차단 추정. (대안: GoogleNews AI 쿼리가 OpenAI 발표를 충분히 커버 — 샘플에 OpenAI/Anthropic 펀딩 기사 포착) |
| arXiv cs.AI | `http://export.arxiv.org/rss/cs.AI` | 파싱 시 **항목 0건**(RDF 변형 포맷, 표준 item/entry 미검출) + 학술 프리프린트라 **뉴스 모니터링 부적합**(노이즈 과다). |
| American Banker | `https://www.americanbanker.com/feed` | **파싱 실패** — XML not well-formed(line1 col4065, 비정상 토큰). 형식 깨진 피드. |
| The Banker | `https://www.thebanker.com/rss` | **404 Not Found** — 해당 RSS 경로 없음. |
| Hugging Face Blog | `https://huggingface.co/blog/feed.xml` | 파싱 OK이나 **적합도 0.37**(엔지니어링/튜토리얼 위주, 뉴스성 낮음) + 788건 전량 반환(노이즈). 모니터링용 부적합 → 탈락. |
| BAIR Berkeley Blog | `https://bair.berkeley.edu/blog/feed.xml` | **정체** — 최신 21.9일 전, ~0.2건/주. 발행빈도 극저 + 적합도 0.10(키워드 기준). 연구블로그라 갱신 드묾 → 탈락. |
| PYMNTS (메인/AI섹션) | `https://www.pymnts.com/feed/`, `.../artificial-intelligence-2/feed/` | 최신성 좋으나 **AI∩금융 적합도 0.0~0.2** — 결제/규제 일반 뉴스 위주로 카테고리 정밀도 부족 → 탈락(필요 시 추후 재평가). |
| The Verge – AI | `https://www.theverge.com/rss/ai-artificial-intelligence/index.xml` | 파싱 OK이나 **적합도 0.40** — 소비자 가젯/잡담성 혼입 다수. global_ai 정밀도 낮아 탈락(보조로도 약함). |
| VentureBeat – AI | `https://venturebeat.com/category/ai/feed/` | 적합도 0.86로 양호하나 **발행 ~0.4건/주**(피드에 과거 항목 정체, 최신 10.6일 전) — 갱신 빈약 → 탈락. |
| CNBC Finance/Technology RSS | `view.xml?...id=10000664 / id=19854910` | 파싱·최신성 우수하나 **AI∩금융 적합도 0.07~0.23** — 일반 증시/실적 뉴스 위주. GoogleNews 금융+AI 쿼리가 더 정밀 → 탈락(중복·저적합). |
| Finextra AI 채널 | `rss/channel.aspx?channel=artificial-intelligence` | `channel` 파라미터 무시되어 headlines와 **동일 내용 반환**(중복). headlines 1개만 보조 채택. |

### robots.txt / 약관 검토
- **Google News RSS**: `robots.txt`의 `User-agent: *`는 `Disallow: /` + 화이트리스트(`/topics/`,`/stories/` 등)로 `/rss/`를 **명시 허용하지 않음**. 단, Google News RSS는 공개·무인증·피드리더 소비용으로 발행되는 **기계 소비 전용 엔드포인트**다. → **채택하되 크롤러가 아닌 피드 구독 방식**으로만 사용, 요청 간격 준수(폴링 주기 수십 분 이상), 페이지 본문 크롤링 금지. 약관상 회색지대이므로 운영 시 트래픽 최소화 원칙 적용.
- **techcrunch / arstechnica / blog.google / deepmind / MIT TR**: `User-agent: *`에서 RSS 경로(`/feed/`, `/rss/`) 차단 없음. wp-admin·검색 등만 Disallow. → **RSS 구독 문제 없음**.
- **Finextra**: 공식 RSS 제공 페이지 존재. 표준 피드 구독 허용 범위.

---

## 3. WebSearch 대안 쿼리 (RSS 보완/장애 대비)

기존 `src/collectors/websearch.py`(시드 JSON → NewsItem)와 직결. 에이전트가 아래 쿼리로 검색 후 카테고리별 결과를 시드에 적재.

**global_ai**
- `OpenAI OR Anthropic OR Google DeepMind 신규 모델 발표 최근 7일`
- `LLM frontier model release benchmark this week`
- `AI regulation OR funding round major announcement`

**global_finance_ai**
- `AI banking JPMorgan OR Goldman Sachs OR hedge fund deployment`
- `생성형 AI 금융 트레이딩 도입 사례 최근`
- `fintech AI fraud detection OR risk model launch`
- `central bank OR regulator AI financial stability`

> 운영 권장: GoogleNews RSS(주력) + RSS 정밀 피드(MIT TR/TechCrunch/Ars/blog.google) + WebSearch(주 1~2회 보강·1차 출처 누락 메움)의 3중 구성.

---

## 4. 신뢰 출처 화이트리스트 (source 정규화용)

dedup·신뢰도 가중 시 도메인 기준 화이트리스트:

```
# global_ai (1차/고신뢰)
openai.com, blog.google, deepmind.google, anthropic.com,
technologyreview.com, arstechnica.com, techcrunch.com, wired.com
# global_finance_ai (1차/고신뢰)
reuters.com, bloomberg.com, ft.com, wsj.com, cnbc.com,
finextra.com, americanbanker.com, jpmorgan.com, goldmansachs.com
```
(GoogleNews RSS 항목은 원기사 도메인이 title 접미사 " - Source"로 들어오므로, source는 원기사 도메인으로 재정규화 권장.)

---

## 5. TODO / 확장 포인트
- **OpenAI 공식 RSS**: 이 환경 SSL 실패. 운영 환경에서 재검증 권장(성공 시 1차 출처로 승격, GoogleNews 의존 완화).
- **American Banker**: 피드 형식 깨짐 — `feedparser`(관대한 파서)로 재시도 시 부분 파싱 가능 여부 재평가 가치 있음.
- **arXiv**: 연구 트렌드 별도 추적 필요 시 Atom API(`http://export.arxiv.org/api/query`) + 전용 파서로 분리 구현(뉴스 파이프라인과 격리).
- **국내(domestic_finance_ai)**: 기존 토스인베스트 크롤러 담당 — 본 리서치 범위 외(요청대로 제외).

---

## 부록: 핵심 실측 수치 (요약)

| 등급 | 카테고리 | 채택 | 보조 | 탈락 |
|------|----------|------|------|------|
| global_ai | 5 | 3 | — | 5 |
| global_finance_ai | 3 | 1 | — | 4(+중복1) |

- 검증 후보 총 24개, 실측 fetch 성공 19개, 파싱 성공 17개.
- 주력 채택(적합도≥0.8 & 최신≤2일): GoogleNews-AI(0.99), MIT TR(1.00), TechCrunch(0.85), blog.google(0.80) / GoogleNews-finance(0.91), GoogleNews-WallStreet(0.80).
