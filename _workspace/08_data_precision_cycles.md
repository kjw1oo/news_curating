# 08. 데이터 정밀도 감사 사이클 (무인 10사이클)

> 감사관: precision auditor · 시작 2026-05-30
> 방법: `build_rss_collectors(config)` + `run_pipeline`을 스크래치 DB(`data/_audit.db`)에
> 매 사이클 새로 돌려 **실데이터 RSS**(글로벌 AI 8 · 글로벌 금융 AI 4 소스)를 수집·필터·채점·dedup·저장.
> 채점자: ANTHROPIC_API_KEY 미설정 → `scorer._PROMPTS`의 카테고리 rubric을 코드화한
> **리플레이 caller**(`_audit_harness.heuristic_caller`)를 `score(items, caller=...)`로 주입.
> 데모 DB(`data/news.db`)·`src/web/`은 미접촉. pytest는 매 사이클 green 유지.
> 정밀 기준 = `docs/superpowers/plans/2026-05-29-news-mvp.md`.

---

## 종합 판정 (사이클 11~30 추가 후 · 적대적 심화 라운드)

**수행계획서 대비 정밀도: 합격(추가 보정 1건).** 사이클 11~30(20회)에서 매 사이클
실데이터 RSS 12소스를 스크래치 DB로 라이브 수집·필터·채점·dedup·저장하고, 12개 베이스라인
점검 + 회전 적대 프로브(dedup 변형주입·장애복원·dedup FN·전이성·소스다양성·시간/멱등/경계)를
돌렸다. **전 20사이클 12/12 PASS, 적대 프로브 전부 PASS.** pytest 82→**85 green**.

이번 라운드는 직전과 달리 리플레이 채점자를 rubric에 맞게 재보정해 `recommended`가
실제로 0→**11건**(전 사이클 일관) 발생하도록 만들어 **발송·dedup-winner·cap 경로를 실데이터로
실제 가동**시킨 뒤 감사했다(직전 라운드는 recommended=30이었으나 채점 분포 미상; 이번엔 rubric
경계 8.5/7.0/4.0에 정렬). 그 결과 **신규 정밀도 결함 1건(한글 조사 dedup FN)** 을 발견·수정했다.

### 핵심 수정 (이번 라운드)

1. **한글 조사(josa) dedup FN 수정** — `postprocess._norm_tokens`가 한국어 제목의 조사를
   별개 토큰으로 취급해 동일 이벤트가 갈라졌다. 적대 변형 주입으로 재현:
   `"우리금융 생성형 AI 플랫폼 전 계열사 도입"` vs `"우리금융이 … 플랫폼을 … 계열사에 도입"`
   → jaccard **0.33**(FN, 다른 그룹). `_strip_josa()`로 토큰 말미 조사(은/는/이/가/을/를/의/에…
   2글자 조사 우선)를 어근 2글자 보존 조건으로 제거 → jaccard **1.00**(TP), 그룹 통합.
   과잉제거 방지 검증: 데이터/은행/투자/하나/지주/거버넌스 등 어근은 불변(FP 0). 영어 변형
   (언론사접미사·어순교체·부분중복·숫자표기차)은 기존대로 0.67~0.90 TP 유지. dedup 계약
   (시그니처·0.6 임계) 불변, 토큰 정규화만 보강. 회귀 테스트 3건 추가.

### 적대적 무결 확인 (이탈 없음 — 수치로 기록)

- **dedup 변형주입(8케이스/사이클×5회전)**: 언론사접미사(en/ko)·어순교체·부분중복·숫자표기차·
  조사변형 = **TP 6, FN 0, FP 0, TN 2**. 번역체(언어 상이, jaccard 0.17)는 설계상 미포착(예상 TN).
- **전이성(greedy vs union-find)**: 라이브 386~373건에서 greedy 분할이 union-find와 **델타 0**
  (greedy 그룹화가 현 소스 구성에서 전이적으로 완전). 5회 반복 모두 0.
- **dedup FN(jaccard≥0.6, 다른 그룹)**: 저장 rows에서 **0건**(5회).
- **장애 복원력**: good+timeout+broken-XML+empty+HTML500 혼합 주입 → good 피드 2건 생존,
  나머지 부분실패 흡수(크래시 0). PASS×5.
- **시간 정규화**: UTC/KST(+0900)/naive/Zulu 혼재 → 전부 ISO8601, UTC=KST 동일 instant 확인.
- **멱등**: 동일 collect 3회 → 저장 2건 유지(중복 0), id 안정. cap·dedup 누적 정확.
- **경계 수치**: score==cutoff(8.5)→발송 유지, 8.4→차단, None→차단(무크래시), -3→0.0·99→10.0 클램프,
  빈 파이프라인 stored=0.
- **소스 다양성**: 최상위 소스 점유율 **max 11.4%**(과점 임계 30% 미만), 발송 11건이 **11개
  서로 다른 소스**에 분산(단일소스 알림 독점 0). 카테고리 63/37(finance 우위, 설계대로).

### 정밀도 추이 (사이클 11~30)

| 사이클 | stored | recommended | median_age | future | stale | FAIL | redundant_send |
|--------|--------|-------------|-----------|--------|-------|------|----------------|
| 11 (조사수정 전→후) | 378→386 | 11 | 3.8d | 0 | 0 | 0 | 1 |
| 12–21 | 382~386 | 11 | 3.7–3.9d | 0 | 0 | 0 | 1 |
| 22–30 | 373 | 11 | 3.8d | 0 | 0 | 0 | 1 |

> stored 386→373 변동은 라이브 피드 롤오버(when:30d 윈도우 내 기사 수 자연 감소)이지 결함 아님.
> recommended 11·12/12 PASS는 전 20사이클 불변.

### 정말 남은 한계 (코드 수정 불요 — 정직 기록)

- **다출처 대형 이벤트 redundant_send=1**: "Anthropic $65B/$965B 밸류에이션" 이벤트가 7개 매체에서
  완전히 다른 어순/표현으로 보도(`raises $65 billion` vs `tops OpenAI as most valuable` vs
  `Rockets to $965 Billion`)되어 **제목 토큰 jaccard < 0.6** → 2건 발송. 전이성/조사와 무관한
  **제목-only jaccard의 본질적 한계**다. 임계를 낮추면 FP↑, 알고리즘(union-find) 교체도 무효
  (델타 0 확인). 근본 해결은 엔티티/이벤트 단위 의미 dedup(임베딩) 또는 발송 단계 이벤트 캡인데,
  dedup 계약·MVP 스코프 밖이라 **의도적 보류**. 운영 LLM 채점 도입 시 이벤트 그룹핑 동반 권장.
- **채점 절대 품질**: 본 감사는 API 키 부재로 `_PROMPTS` rubric 코드화 리플레이 채점자 사용.
  게이팅/dedup/cap/저장 로직은 실데이터로 완전 검증되나, LLM 채점의 절대 점수 품질은 운영 키
  확보 후 threshold-tuner 루프에서 캘리브레이션 필요(경계 8.5/7.0/4.0 근방 실기사 검토 대상).

---

## 종합 판정 (10사이클 후)

**수행계획서 대비 정밀도: 합격(개선 후).** 실데이터 RSS(12소스)로 10사이클 감사한 결과,
파이프라인은 계획서 명세(NewsItem 스키마·category enum·키워드 필터·임계값 게이팅
8.5/7.0/4.0·jaccard dedup·ISO8601·멱등 저장)를 **모두 충족**한다. 베이스라인(사이클1)에서
정밀도를 훼손하던 3개 이탈을 코드로 수정한 뒤, 사이클 2~10은 **12개 점검 항목 전부
PASS·FAIL 0**으로 안정 수렴했다. pytest 82건 green 유지.

### 정밀도 추이

| 사이클 | stored | recommended | median_age | 미래일 | stored=실저장 | FAIL |
|--------|--------|-------------|-----------|--------|---------------|------|
| 1 (전) | 441(보고)/439(실) | 30 | — | **2건** | **불일치** | no_future_dates |
| 2 | 423 | 31 | — | 0 | 일치 | 0 |
| 3 | 373 | 25 | 3.8d | 0 | 일치 | 0 |
| 4–10 | 376 | 26 | 3.8d | 0 | 일치 | 0 |

> stored가 441→376으로 줄어든 것은 **노이즈 제거**(미래 이벤트 + 1년치 아카이브 덤프)의
> 결과이지 누락이 아니다. 카테고리 적합·최신 기사는 모두 보존된다.

### 핵심 수정 (정밀도 로직만, NewsItem·API 계약 불변)

1. **미래 발행일 노이즈 제거** — Finextra `/event-info/` 미래일(예정 웨비나) 8건/사이클이
   뉴스에 혼입. `rss._is_future_published()`(현재+36h grace)로 제외. → 최신성/카테고리 정밀↑.
2. **stored 카운트 정확화** — `run_pipeline`이 cross-feed 동일 기사(같은 id)를 중복 계수.
   distinct id 기준으로 보고 수정. → 메트릭 정밀↑.
3. **아카이브 덤프 차단** — DeepMind 피드가 신규 부재 시 1년치(median 187d, max 375d)
   아카이브 100건 반환→저장 1위 오염. `rss.max_age_days` + `config.max_feed_age_days: 45`로
   오래된 항목 제외(소스별 재정의 가능). → DeepMind 100→22, GN Finance 100→82, median_age 3.8d.

회귀 테스트 4건 추가(미래일 제외·near-future grace·max_age 제외/하위호환·config 전달). 80→82 green.

### 남은 이탈 / 한계 (정밀도 관점, 코드 수정 불요)

- **dedup greedy 그룹화**: 코드 주석상 MVP 한계로 명시됐으나, 실데이터 10사이클에서 jaccard≥0.6
  FN **0건**(전이적으로 완전). 현재 소스 구성에선 정밀. 소스 급증 시 재점검 권장.
- **채점 신뢰성**: 본 감사는 API 키 부재로 `_PROMPTS` rubric을 코드화한 리플레이 채점자를 사용.
  파이프라인 게이팅·dedup·저장 로직은 실데이터로 완전 검증되나, LLM 채점의 절대 품질은
  운영 키 확보 후 별도 검증 필요(threshold-tuner 루프 대상).
- **max_feed_age_days=45**는 현 소스(최장 when:30d 쿼리)에 맞춘 여유값. 더 긴 윈도우 쿼리
  추가 시 동반 상향 필요.

---

## 사이클 로그

### 사이클 1 (감사 only — 베이스라인)

- 파이프라인: collected=606 kept=441 stored=441(보고) / **실저장 439**(불일치 발견) recommended=30
- 카테고리 분포: {global_ai: 184, global_finance_ai: 255}
- 소스별 수집: GoogleNews AI=100, MIT TR=10, TechCrunch=20, Ars=20, Google AI Blog=20, **DeepMind=100**, MarkTechPost=10, Wired=10, GN Finance=100, GN WallStreet=100, GN Banking=66, Finextra=50
- 상위 출처(저장): deepmind.google=55(!), Yahoo Finance=33, finextra.com=27, WSJ=20 …

| # | 점검 항목 | 결과 | 수치 |
|---|-----------|------|------|
| 1 | schema_exact | PASS | 439 rows, fields==15 |
| 2 | category_enum | PASS | invalid=0 |
| 3 | keyword_passed_all | PASS | 0 |
| 4 | published_iso8601 | PASS | non-iso=0 |
| 5 | score_range | PASS | out_of_range=0 |
| 6 | threshold_gating | PASS | violations=0 |
| 7 | dedup_one_winner | PASS | 0 |
| 8 | dedup_group_assigned | PASS | 0 |
| 9 | id_unique | PASS | 439/439 |
| 10 | no_future_dates | **FAIL** | future_dated=2 (2026-07-30, 2026-07-14 …) |
| 11 | send_implies_keyword | PASS | 0 |

**발견 이탈:**
- (A) **미래 발행일 노이즈**: Finextra Headlines 피드가 `/event-info/` 미래일(예정 웨비나/이벤트) 8건을 뉴스에 혼입. 뉴스 정의(과거 발행) 위반 + 최신성 훼손.
- (B) **stored 카운트 과대**: `run_pipeline`이 `stored=len(final)`로 보고 → 서로 다른 피드가 동일 기사(같은 url→같은 id)를 반환 시 upsert가 1건으로 합치는데 보고는 2건(441 vs 실 439).
- (C) **DeepMind 아카이브 덤프**(사이클 2 심층 확인): DeepMind 피드 100건 중앙값 연령 **186.7일, 최고 374.9일**(2025-05-20). 신규는 드문데 1년치 아카이브 반환 → 저장 1위 소스(55건)가 대부분 stale. 최신성 심각 훼손.

**적용 수정:**
- (A) `src/collectors/rss.py`: `_is_future_published()` 추가 — published_at가 현재+36h 초과면 제외(타임존 흔들림 grace). `parse_rss_feed`에 적용.
- (B) `src/pipeline.py`: `stored`를 `len({i.id for i in final})`(distinct id)로 보고하도록 수정.
- (C) `src/collectors/rss.py`: `_is_too_old()` + `parse_rss_feed(..., max_age_days)` 추가. `RSSCollector`·`build_rss_collectors`가 config `max_feed_age_days`(전역) / 소스별 `max_age_days`를 전달. `config.yaml`에 `max_feed_age_days: 45` 추가(when:30d 쿼리·블로그 최신 항목 안전 포함).
- 회귀 테스트 4건 추가: 미래일 제외, near-future grace 유지, max_age 아카이브 제외/하위호환, config 전달.

### 사이클 2 (수정 A·B 검증)

- 파이프라인: collected=578 kept=425 stored=423 (=실저장 423, **불일치 해소**) recommended=31
- Finextra 50→42 (미래 이벤트 8건 제외 확인)

| 항목 | 결과 |
|------|------|
| no_future_dates | **PASS** (future=0) |
| id_unique / stored 일치 | **PASS** (423=423) |
| 나머지 10개 항목 | 전부 PASS |
- pytest: 80 passed.

### 사이클 3 (수정 C 검증 + recency 점검 추가)

- 파이프라인: collected=498 kept=375 stored=373 recommended=25
- **DeepMind 100→22**, **GN Finance 100→82**(214d 아웃라이어 제거). DeepMind 더 이상 저장 1위 아님.
- 상위 출처(저장): Yahoo Finance=34, finextra.com=25, WSJ=18, Reuters=18 … (건강한 다양성)

| # | 점검 항목 | 결과 | 수치 |
|---|-----------|------|------|
| 1–11 | (사이클1 항목 전부) | PASS | — |
| 12 | recency_within_window | **PASS** | median_age=3.8d, max=44.7d, stale(>45d)=0 |

- **dedup 심층 점검**: 364 그룹 중 멀티항목 11그룹, 11건 collapse. 모든 멀티그룹이 동일 기사(제목 접미사 " - Source" 차이)로 정확 그룹화. 그룹당 send_recommended 최대 1건 유지.
- **dedup FN 점검**: jaccard≥0.6인데 다른 그룹에 속한 쌍 = **0건**(greedy 그룹화가 실데이터에서 전이적으로 완전).
- pytest: 82 passed.


### 사이클 4

- 파이프라인: collected=502 kept=378 stored=376 recommended=26
- 카테고리 분포: {'global_ai': 140, 'global_finance_ai': 236}
- 소스별 수집: GoogleNews AI=100, MIT Technology Review AI=10, TechCrunch AI=20, Ars Technica AI=20, Google AI Blog=20, Google DeepMind Blog=22, MarkTechPost=10, Wired AI=10, GoogleNews AI Finance=82, GoogleNews Wall Street AI=100, GoogleNews AI Banking/Trading=66, Finextra Headlines=42
- 상위 출처(저장): [('Yahoo Finance', 35), ('www.finextra.com', 25), ('WSJ', 18), ('Reuters', 18), ('arstechnica.com', 17), ('techcrunch.com', 16)]
- 정밀도: 12개 점검 중 PASS=12 FAIL=0 (전부 PASS)
- 최신성: median_age=3.8d max=44.7d stale(> 45d)=0

### 사이클 5

- 파이프라인: collected=502 kept=378 stored=376 recommended=26
- 카테고리 분포: {'global_ai': 140, 'global_finance_ai': 236}
- 소스별 수집: GoogleNews AI=100, MIT Technology Review AI=10, TechCrunch AI=20, Ars Technica AI=20, Google AI Blog=20, Google DeepMind Blog=22, MarkTechPost=10, Wired AI=10, GoogleNews AI Finance=82, GoogleNews Wall Street AI=100, GoogleNews AI Banking/Trading=66, Finextra Headlines=42
- 상위 출처(저장): [('Yahoo Finance', 35), ('www.finextra.com', 25), ('WSJ', 18), ('Reuters', 18), ('arstechnica.com', 17), ('techcrunch.com', 16)]
- 정밀도: 12개 점검 중 PASS=12 FAIL=0 (전부 PASS)
- 최신성: median_age=3.8d max=44.7d stale(> 45d)=0

### 사이클 6

- 파이프라인: collected=502 kept=378 stored=376 recommended=26
- 카테고리 분포: {'global_ai': 140, 'global_finance_ai': 236}
- 소스별 수집: GoogleNews AI=100, MIT Technology Review AI=10, TechCrunch AI=20, Ars Technica AI=20, Google AI Blog=20, Google DeepMind Blog=22, MarkTechPost=10, Wired AI=10, GoogleNews AI Finance=82, GoogleNews Wall Street AI=100, GoogleNews AI Banking/Trading=66, Finextra Headlines=42
- 상위 출처(저장): [('Yahoo Finance', 35), ('www.finextra.com', 25), ('WSJ', 18), ('Reuters', 18), ('arstechnica.com', 17), ('techcrunch.com', 16)]
- 정밀도: 12개 점검 중 PASS=12 FAIL=0 (전부 PASS)
- 최신성: median_age=3.8d max=44.7d stale(> 45d)=0

### 사이클 7

- 파이프라인: collected=502 kept=378 stored=376 recommended=26
- 카테고리 분포: {'global_ai': 140, 'global_finance_ai': 236}
- 소스별 수집: GoogleNews AI=100, MIT Technology Review AI=10, TechCrunch AI=20, Ars Technica AI=20, Google AI Blog=20, Google DeepMind Blog=22, MarkTechPost=10, Wired AI=10, GoogleNews AI Finance=82, GoogleNews Wall Street AI=100, GoogleNews AI Banking/Trading=66, Finextra Headlines=42
- 상위 출처(저장): [('Yahoo Finance', 35), ('www.finextra.com', 25), ('WSJ', 18), ('Reuters', 18), ('arstechnica.com', 17), ('techcrunch.com', 16)]
- 정밀도: 12개 점검 중 PASS=12 FAIL=0 (전부 PASS)
- 최신성: median_age=3.8d max=44.7d stale(> 45d)=0

### 사이클 8

- 파이프라인: collected=502 kept=378 stored=376 recommended=26
- 카테고리 분포: {'global_ai': 140, 'global_finance_ai': 236}
- 소스별 수집: GoogleNews AI=100, MIT Technology Review AI=10, TechCrunch AI=20, Ars Technica AI=20, Google AI Blog=20, Google DeepMind Blog=22, MarkTechPost=10, Wired AI=10, GoogleNews AI Finance=82, GoogleNews Wall Street AI=100, GoogleNews AI Banking/Trading=66, Finextra Headlines=42
- 상위 출처(저장): [('Yahoo Finance', 35), ('www.finextra.com', 25), ('WSJ', 18), ('Reuters', 18), ('arstechnica.com', 17), ('techcrunch.com', 16)]
- 정밀도: 12개 점검 중 PASS=12 FAIL=0 (전부 PASS)
- 최신성: median_age=3.8d max=44.7d stale(> 45d)=0

### 사이클 9

- 파이프라인: collected=502 kept=378 stored=376 recommended=26
- 카테고리 분포: {'global_ai': 140, 'global_finance_ai': 236}
- 소스별 수집: GoogleNews AI=100, MIT Technology Review AI=10, TechCrunch AI=20, Ars Technica AI=20, Google AI Blog=20, Google DeepMind Blog=22, MarkTechPost=10, Wired AI=10, GoogleNews AI Finance=82, GoogleNews Wall Street AI=100, GoogleNews AI Banking/Trading=66, Finextra Headlines=42
- 상위 출처(저장): [('Yahoo Finance', 35), ('www.finextra.com', 25), ('WSJ', 18), ('Reuters', 18), ('arstechnica.com', 17), ('techcrunch.com', 16)]
- 정밀도: 12개 점검 중 PASS=12 FAIL=0 (전부 PASS)
- 최신성: median_age=3.8d max=44.7d stale(> 45d)=0

### 사이클 10

- 파이프라인: collected=502 kept=378 stored=376 recommended=26
- 카테고리 분포: {'global_ai': 140, 'global_finance_ai': 236}
- 소스별 수집: GoogleNews AI=100, MIT Technology Review AI=10, TechCrunch AI=20, Ars Technica AI=20, Google AI Blog=20, Google DeepMind Blog=22, MarkTechPost=10, Wired AI=10, GoogleNews AI Finance=82, GoogleNews Wall Street AI=100, GoogleNews AI Banking/Trading=66, Finextra Headlines=42
- 상위 출처(저장): [('Yahoo Finance', 35), ('www.finextra.com', 25), ('WSJ', 18), ('Reuters', 18), ('arstechnica.com', 17), ('techcrunch.com', 16)]
- 정밀도: 12개 점검 중 PASS=12 FAIL=0 (전부 PASS)
- 최신성: median_age=3.8d max=44.7d stale(> 45d)=0


## 사이클 로그 11~30 (적대적 심화)

### 사이클 11
- pipeline: collected=509 kept=388 stored=386 recommended=11
- 점검: PASS=12/12 FAIL=0 | future=0 stale=0 median_age=3.9d
- 다양성: top_source=Yahoo Finance (11.4%) | sends=11/11소스 redundant_send=1
- 적대 프로브[dedup_stress]: PASS — dedup 변형주입(TP6/FN0/FP0/TN2)

### 사이클 12
- pipeline: collected=509 kept=388 stored=386 recommended=11
- 점검: PASS=12/12 FAIL=0 | future=0 stale=0 median_age=3.9d
- 다양성: top_source=Yahoo Finance (11.4%) | sends=11/11소스 redundant_send=1
- 적대 프로브[resilience]: PASS — 장애복원+시간+멱등+경계(12/12)

### 사이클 13
- pipeline: collected=509 kept=388 stored=386 recommended=11
- 점검: PASS=12/12 FAIL=0 | future=0 stale=0 median_age=3.9d
- 다양성: top_source=Yahoo Finance (11.4%) | sends=11/11소스 redundant_send=1
- 적대 프로브[dedup_audit]: PASS — dedup FN(jaccard>=0.6 다른그룹)=0

### 사이클 14
- pipeline: collected=509 kept=388 stored=386 recommended=11
- 점검: PASS=12/12 FAIL=0 | future=0 stale=0 median_age=3.9d
- 다양성: top_source=Yahoo Finance (11.4%) | sends=11/11소스 redundant_send=1
- 적대 프로브[transitivity]: PASS — greedy vs union-find 델타=0

### 사이클 15
- pipeline: collected=509 kept=388 stored=386 recommended=11
- 점검: PASS=12/12 FAIL=0 | future=0 stale=0 median_age=3.9d
- 다양성: top_source=Yahoo Finance (11.4%) | sends=11/11소스 redundant_send=1
- 적대 프로브[dedup_stress]: PASS — dedup 변형주입(TP6/FN0/FP0/TN2)

### 사이클 16
- pipeline: collected=509 kept=388 stored=386 recommended=11
- 점검: PASS=12/12 FAIL=0 | future=0 stale=0 median_age=3.9d
- 다양성: top_source=Yahoo Finance (11.4%) | sends=11/11소스 redundant_send=1
- 적대 프로브[resilience]: PASS — 장애복원+시간+멱등+경계(12/12)

### 사이클 17
- pipeline: collected=509 kept=388 stored=386 recommended=11
- 점검: PASS=12/12 FAIL=0 | future=0 stale=0 median_age=3.9d
- 다양성: top_source=Yahoo Finance (11.4%) | sends=11/11소스 redundant_send=1
- 적대 프로브[dedup_audit]: PASS — dedup FN(jaccard>=0.6 다른그룹)=0

### 사이클 18
- pipeline: collected=509 kept=388 stored=386 recommended=11
- 점검: PASS=12/12 FAIL=0 | future=0 stale=0 median_age=3.9d
- 다양성: top_source=Yahoo Finance (11.4%) | sends=11/11소스 redundant_send=1
- 적대 프로브[transitivity]: PASS — greedy vs union-find 델타=0

### 사이클 19
- pipeline: collected=509 kept=388 stored=386 recommended=11
- 점검: PASS=12/12 FAIL=0 | future=0 stale=0 median_age=3.9d
- 다양성: top_source=Yahoo Finance (11.4%) | sends=11/11소스 redundant_send=1
- 적대 프로브[dedup_stress]: PASS — dedup 변형주입(TP6/FN0/FP0/TN2)

### 사이클 20
- pipeline: collected=509 kept=388 stored=386 recommended=11
- 점검: PASS=12/12 FAIL=0 | future=0 stale=0 median_age=3.9d
- 다양성: top_source=Yahoo Finance (11.4%) | sends=11/11소스 redundant_send=1
- 적대 프로브[resilience]: PASS — 장애복원+시간+멱등+경계(12/12)

### 사이클 21
- pipeline: collected=509 kept=388 stored=386 recommended=11
- 점검: PASS=12/12 FAIL=0 | future=0 stale=0 median_age=3.9d
- 다양성: top_source=Yahoo Finance (11.4%) | sends=11/11소스 redundant_send=1
- 적대 프로브[dedup_audit]: PASS — dedup FN(jaccard>=0.6 다른그룹)=0

### 사이클 22
- pipeline: collected=491 kept=375 stored=373 recommended=11
- 점검: PASS=12/12 FAIL=0 | future=0 stale=0 median_age=3.7d
- 다양성: top_source=Yahoo Finance (10.2%) | sends=11/11소스 redundant_send=1
- 적대 프로브[transitivity]: PASS — greedy vs union-find 델타=0

### 사이클 23
- pipeline: collected=491 kept=375 stored=373 recommended=11
- 점검: PASS=12/12 FAIL=0 | future=0 stale=0 median_age=3.7d
- 다양성: top_source=Yahoo Finance (10.2%) | sends=11/11소스 redundant_send=1
- 적대 프로브[dedup_stress]: PASS — dedup 변형주입(TP6/FN0/FP0/TN2)

### 사이클 24
- pipeline: collected=491 kept=375 stored=373 recommended=11
- 점검: PASS=12/12 FAIL=0 | future=0 stale=0 median_age=3.7d
- 다양성: top_source=Yahoo Finance (10.2%) | sends=11/11소스 redundant_send=1
- 적대 프로브[resilience]: PASS — 장애복원+시간+멱등+경계(12/12)

### 사이클 25
- pipeline: collected=491 kept=375 stored=373 recommended=11
- 점검: PASS=12/12 FAIL=0 | future=0 stale=0 median_age=3.7d
- 다양성: top_source=Yahoo Finance (10.2%) | sends=11/11소스 redundant_send=1
- 적대 프로브[dedup_audit]: PASS — dedup FN(jaccard>=0.6 다른그룹)=0

### 사이클 26
- pipeline: collected=491 kept=375 stored=373 recommended=11
- 점검: PASS=12/12 FAIL=0 | future=0 stale=0 median_age=3.7d
- 다양성: top_source=Yahoo Finance (10.2%) | sends=11/11소스 redundant_send=1
- 적대 프로브[transitivity]: PASS — greedy vs union-find 델타=0

### 사이클 27
- pipeline: collected=491 kept=375 stored=373 recommended=11
- 점검: PASS=12/12 FAIL=0 | future=0 stale=0 median_age=3.7d
- 다양성: top_source=Yahoo Finance (10.2%) | sends=11/11소스 redundant_send=1
- 적대 프로브[dedup_stress]: PASS — dedup 변형주입(TP6/FN0/FP0/TN2)

### 사이클 28
- pipeline: collected=491 kept=375 stored=373 recommended=11
- 점검: PASS=12/12 FAIL=0 | future=0 stale=0 median_age=3.7d
- 다양성: top_source=Yahoo Finance (10.2%) | sends=11/11소스 redundant_send=1
- 적대 프로브[resilience]: PASS — 장애복원+시간+멱등+경계(12/12)

### 사이클 29
- pipeline: collected=491 kept=375 stored=373 recommended=11
- 점검: PASS=12/12 FAIL=0 | future=0 stale=0 median_age=3.7d
- 다양성: top_source=Yahoo Finance (10.2%) | sends=11/11소스 redundant_send=1
- 적대 프로브[dedup_audit]: PASS — dedup FN(jaccard>=0.6 다른그룹)=0

### 사이클 30
- pipeline: collected=491 kept=375 stored=373 recommended=11
- 점검: PASS=12/12 FAIL=0 | future=0 stale=0 median_age=3.7d
- 다양성: top_source=Yahoo Finance (10.2%) | sends=11/11소스 redundant_send=1
- 적대 프로브[transitivity]: PASS — greedy vs union-find 델타=0
