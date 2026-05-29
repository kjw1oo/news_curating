---
name: news-system-design
description: "뉴스 모니터링 시스템의 아키텍처와 표준 데이터 스키마를 설계. 시스템 구조 설계, NewsItem 스키마 정의, 모듈 경계 명세, DB 테이블 설계, 소스 플러그인 구조 설계 시 반드시 이 스킬을 사용. 설계를 다시 하거나 스키마를 수정·확장할 때도 사용."
---

# News System Design — 아키텍처 & 표준 스키마 설계

뉴스 수집·필터링·알림 시스템의 구조와, 모든 빌드 에이전트가 공유하는 **표준 데이터 스키마(계약)** 를 설계하는 스킬. 스키마의 모호함이 곧 경계면 버그이므로, 필드명·타입·예시값을 모두 못박는다.

## 산출물

1. `_workspace/01_architect_design.md` — 시스템 구조
2. `_workspace/01_architect_schema.md` — 표준 데이터 스키마 (런타임 계약, 빌드 에이전트 필독)

## 권장 시스템 구조

```
news_curating/
├── config.yaml              # 임계값·주기·캡 (운영자 조정)
├── src/
│   ├── collectors/          # 소스별 수집기 (플러그인)
│   │   ├── base.py          # Collector 인터페이스
│   │   ├── rss.py           # 글로벌 AI RSS
│   │   ├── websearch.py     # 글로벌 금융 AI (보완)
│   │   └── toss.py          # 국내 금융지주 크롤링
│   ├── filters/             # 4단계 파이프라인
│   │   ├── keyword.py
│   │   ├── scorer.py        # LLM 중요도 평가
│   │   ├── threshold.py
│   │   └── dedup.py
│   ├── storage/             # SQLite (news_items, send_history, feedback)
│   ├── notifiers/           # 알림 채널 플러그인 (dashboard 기본 + email 스텁)
│   ├── api/                 # FastAPI
│   └── web/                 # 대시보드 정적 파일
├── data/                    # SQLite DB, 로그(30일 보관)
└── tests/
```

## 모듈 책임 분담

| 모듈 | 책임 | 담당 |
|------|------|------|
| collectors | 소스→NewsItem 정규화 | collector-dev |
| filters | 키워드→점수→임계값→중복제거 | filter-dev |
| api + web + notifiers | 대시보드, 알림 발송, 이력/설정/피드백 | dashboard-dev |
| storage | NewsItem·발송이력·피드백 영속화 | architect가 스키마 정의, 각 dev가 사용 |

## 설계 원칙

- **단일 진실 공급원(SSOT)**: NewsItem 스키마는 한 곳(`01_architect_schema.md`)에만 정의하고 모든 모듈이 참조한다. 모듈마다 다르게 정의하면 경계면 버그가 난다.
- **소스 플러그인**: 모든 수집기는 동일한 `Collector` 인터페이스(`collect() -> list[NewsItem]`)를 구현한다. 새 소스 추가 = 새 파일 1개 + 레지스트리 등록 1줄.
- **카테고리 enum 고정**: `global_ai`, `global_finance_ai`, `domestic_finance_ai` 3개. 문자열 오타가 분기 누락을 만들므로 상수로 관리.
- **확장 포인트 명시**: 미확정 항목(NH농협 소스, 추가 알림 채널)은 스텁/TODO로 자리만 만들어 둔다. 과설계로 미리 구현하지 않는다.
- **운영 요구 반영**: 임계값은 `config.yaml`에서 조정 가능, 로그·발송이력 30일 보관, FP/FN 피드백 저장 테이블 포함.

## 표준 데이터 스키마

스키마 전문(NewsItem 필드 정의, config.yaml 형식, DB 테이블 DDL, 카테고리 enum, 기본 임계값)은 `references/data-schema.md`를 Read하여 `_workspace/01_architect_schema.md`에 구체화한다. 빌드 에이전트가 이 산출물을 계약으로 사용하므로, 모든 필드의 이름·타입·예시값을 빠짐없이 채운다.

## 소스 목록 반영

- 빌드 모드 시작 시 `_workspace/00b_source_research.md`가 존재하면 Read하여 source-researcher가 채택한 소스 목록을 설계(수집기 플러그인·카테고리 매핑)에 반영한다.

## 후속/재실행

- `_workspace/01_architect_*.md`가 이미 존재하면 Read하여 기존 설계를 파악하고, 사용자 피드백 부분만 수정한다.
- 스키마 변경 시 영향받는 빌드 에이전트에게 `SendMessage`로 변경점을 통지한다 (필드 추가/이름 변경은 경계면 재검증이 필요).
