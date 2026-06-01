# 뉴스 모니터링 하네스 확장 설계

작성일: 2026-05-29
대상: `news_curating` 프로젝트의 AI 뉴스 모니터링 하네스(개발형)

## 1. 배경

기존 하네스는 **빌드(코드 작성)** 에 집중되어, 시스템을 "만드는" 역할(architect, collector-dev, filter-dev, dashboard-dev, qa-inspector)은 충분하나 "결정하고 / 학습하는" 역할이 비어 있다. 본 확장은 두 가지 갭을 메운다.

- **소스 결정 갭**: 요구사항이 명시적으로 미결로 남긴 "글로벌 AI/금융 소스 최종 결정"을 수행하는 주체가 없다. collector-dev는 주어진 소스를 구현만 한다.
- **학습 루프 갭**: FP/FN 피드백을 모으는 `feedback` 테이블은 설계되어 있으나, 이를 분석해 임계값·평가 프롬프트를 재조정하는 주체가 없다.

추가로, 토스인베스트 크롤링의 기술 스택을 **Scrapling**으로 확정한다.

## 2. 신규 에이전트

두 에이전트 모두 빌트인 `general-purpose` 타입을 사용한다 (WebSearch·WebFetch·DB 읽기·파일 쓰기가 필요하여 읽기 전용 Explore는 부적합). 모든 호출에 `model: "opus"`를 명시한다. 빌드 팀(5명)에 상주하지 않고 **모드별 단독 실행(서브 에이전트)** 으로 동작하여 팀 오버헤드 없이 붙는다 → 하네스는 하이브리드 구조가 된다.

### 2-1. source-researcher (+ 스킬 news-source-research)

- **역할**: 미결 글로벌 소스를 **실제 검증**으로 확정한다. 후보 RSS/API/페이지를 직접 fetch하여 다음을 측정·점수화한다:
  - 파싱 성공 여부 (죽은/형식 깨진 피드 탈락)
  - 발행 빈도 및 최신성 (최근 항목 날짜, 일/주당 항목 수)
  - 카테고리 적합도 (global_ai / global_finance_ai 관련성)
  - 추정 중복률 (다른 소스와 동일 기사 비중)
- **검증 방법**: RSS 후보는 `feedparser`로, HTML/JS 렌더링 페이지 후보는 `Scrapling`으로 fetch한다.
- **출력**: `_workspace/00b_source_research.md` — 채택/탈락 소스 목록 + 근거 + 신뢰 출처 화이트리스트. collector-dev의 `references/sources.md` 입력으로 직결.
- **생애주기**: 빌드 전 1회 실행, 또는 "소스 조사" 요청으로 단독 실행.
- **안전성**: 코드를 강행하지 않는다. 크롤링 검증 시 robots.txt·이용약관을 확인하고, 차단 소스는 탈락 사유에 명시.

### 2-2. threshold-tuner (+ 스킬 news-threshold-tuning)

- **역할**: 운영 중 누적된 `feedback`(FP/FN)과 `send_history`를 분석하여 카테고리별 임계값·평가 프롬프트 조정안을 **제안만** 한다.
- **안전성**: 자동 반영하지 않는다. 운영자 승인 후에만 `config.yaml`을 패치한다 (요구사항 6.2 "운영자 조정 가능"과 정합).
- **오버피팅 방지**: 소수 피드백 항목에 맞춘 좁은 규칙을 만들지 않는다. "이 기사 1건" 수준이 아니라 "이런 유형이 과발송/누락되는 경향" 수준으로 **원리 일반화**하여 제안한다.
- **출력**: `_workspace/06_tuning_proposal.md` — 카테고리별 현재값 → 제안값 + 근거 + 예상 효과(발송 빈도 변화 추정). 승인 시 `config.yaml` 임계값/프롬프트 패치.
- **생애주기**: 운영 중 반복 실행. "임계값 튜닝", "피드백 반영", "오발송/누락이 많다" 등으로 트리거.

## 3. 오케스트레이터 모드 라우팅

`news-monitoring-orchestrator`는 기존 단일 빌드 모드에서 **3개 모드**로 확장된다. Phase 0(컨텍스트 확인) 직후 요청을 분류하여 라우팅한다.

| 모드 | 트리거 표현 | 동작 |
|------|------------|------|
| **리서치** | 소스 조사, 소스 결정, 어떤 소스 쓸지 | source-researcher 단독 실행 → `00b_source_research.md` 산출 (collector-dev 입력) |
| **빌드** (기존) | 구축, 빌드, 구현, 시스템 만들기 | 5인 팀 파이프라인. `00b_source_research.md`가 있으면 architect가 참조, 없으면 "소스 먼저 확정할까요?" 제안 |
| **튜닝** | 임계값 튜닝, 피드백 반영, 오발송/누락 많음 | threshold-tuner 단독 실행 → 제안 → 승인 시 config 반영 → filter 재실행 |

빌드 팀 구성(architect/collector-dev/filter-dev/dashboard-dev/qa-inspector)은 변경 없다. 신규 2종은 팀에 추가되지 않고 모드별 단독 호출된다.

## 4. 데이터 흐름

```
[리서치 모드]
  source-researcher → _workspace/00b_source_research.md ┐
                      (채택 소스 + 화이트리스트)          │
                                                          ▼
[빌드 모드]  architect (00b 참조) → 01_architect_schema.md
             → collector-dev / filter-dev / dashboard-dev (병렬)
             → qa-inspector (점진 검증) → 동작하는 시스템

[운영 후 / 튜닝 모드]
  feedback + send_history (SQLite)
      → threshold-tuner → _workspace/06_tuning_proposal.md
      → (운영자 승인) → config.yaml 패치 → filter 재실행
```

## 5. 기술 스택 확정 (크롤링)

| 소스 유형 | 라이브러리 | 사유 |
|-----------|-----------|------|
| 정적 RSS (글로벌 AI 등) | `feedparser` | RSS는 정적이라 브라우저 오버헤드 불필요 |
| 내부 JSON API (토스 등) | `httpx` | API가 있으면 가장 안정적 |
| JS 렌더링 페이지 (토스 등) | `Scrapling` (StealthyFetcher) | 안티봇 회피 + 적응형 셀렉터로 사이트 구조 변경에 강함 |

기존 `news-collector-dev/references/sources.md`의 토스 크롤링 섹션을 Scrapling 기준으로 갱신 완료.

## 6. 산출물 (이 확장으로 생성/수정될 파일)

생성:
- `.claude/agents/source-researcher.md`
- `.claude/agents/threshold-tuner.md`
- `.claude/skills/news-source-research/SKILL.md`
- `.claude/skills/news-threshold-tuning/SKILL.md`

수정:
- `.claude/skills/news-monitoring-orchestrator/SKILL.md` — 3모드 라우팅 + 데이터 흐름에 신규 에이전트 반영, description에 "소스 조사"·"임계값 튜닝"·"피드백 반영" 트리거 키워드 추가
- `.claude/skills/news-collector-dev/references/sources.md` — Scrapling 반영 (완료)
- `.claude/skills/news-system-design/SKILL.md` — architect가 빌드 모드 시작 시 `00b_source_research.md`(존재할 경우)를 읽어 소스 목록을 설계에 반영하도록 한 줄 추가
- `CLAUDE.md` — 변경 이력에 본 확장 기록

## 7. 비목표 (YAGNI)

- 스코어러 평가 전용 eval 에이전트 — filter-dev에 흡수
- 법무 체크 전용 에이전트 — collector-dev/source-researcher 원칙에 내재
- 운영/스케줄러 전용 에이전트 — 이번 확장 범위 제외 (추후 필요 시 별도 확장)
- threshold-tuner의 자동 반영 — 제안만으로 한정 (안전성)
