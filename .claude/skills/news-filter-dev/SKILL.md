---
name: news-filter-dev
description: "뉴스 필터링·중요도 평가 파이프라인을 구현. 키워드 필터, LLM 기반 중요도 점수화(0~10점)와 판단 근거 생성, 카테고리별 임계값 적용, 동일 이벤트 중복 제거, 월 1건 캡을 담당. 필터/스코어링/중요도평가/임계값/중복제거/dedup 구현·수정·임계값 튜닝 시 반드시 이 스킬을 사용."
---

# News Filter Dev — 필터링 파이프라인 구현

요구사항의 핵심 가치("빈도 최소화, 관심도 최대화")를 실현하는 4단계 필터링 파이프라인을 구현하는 스킬.

## 시작 전 필수

`_workspace/01_architect_schema.md`를 Read하여 NewsItem의 입력 필드와 당신이 채울 필드(keyword_passed, importance_score, importance_reason, send_recommended, dedup_group)를 확인한다.

## 4단계 파이프라인

```
NewsItem[] (collector 출력)
  → keyword_filter   : keyword_passed 설정, 미통과 제외
  → score            : importance_score(0~10) + importance_reason 채움 (LLM)
  → apply_threshold  : 카테고리별 임계값 + 월 캡 → send_recommended 확정
  → dedup            : dedup_group 설정, 동일 이벤트 대표 1건만 발송 후보
  → 발송 후보 NewsItem[]
```

### 1단계 키워드 필터

config의 `keyword_filters`(AI, 인공지능, LLM, 머신러닝, 데이터 등) 중 하나라도 title 또는 summary_raw에 포함되면 통과. 국내 카테고리는 누락 방지를 위해 키워드 매칭을 느슨하게(부분일치) 적용한다. LLM 호출 비용을 줄이는 사전 스크리닝이 목적이다.

### 2단계 LLM 중요도 평가

Anthropic API로 카테고리별 기준에 따라 평가한다. **판단 근거 출력은 필수**(설명 가능성, 요구사항 6.1) — 이 텍스트가 알림 메시지에 그대로 들어간다.

- 입력: title, summary_raw, source, published_at, category
- 출력: `{ "score": 0.0~10.0, "reason": "1~2문장", "send": true/false }`
- 비용 효율: 대량 평가는 claude-haiku, 경계 점수(±1.0)만 상위 모델 재평가 고려
- 카테고리별 평가 기준 프롬프트는 `references/scoring-prompts.md`를 Read

### 3단계 임계값 적용

config의 `thresholds`로 send_recommended를 확정한다. 방향성:
- **global_ai**: 높게(8.5) — 산업 판도를 바꿀 최상위만. 연 수회 빈도 목표
- **global_finance_ai**: 중간(7.0) + **월 1건 캡** — 해당 월 최고 중요도 1건 원칙. 월 캡 초과 시 점수 상위 1건만 send_recommended 유지
- **domestic_finance_ai**: 낮게(4.0) — 누락 최소화. 가벼운 내용도 통과

임계값은 반드시 config.yaml에서 읽는다 (운영자 조정 가능 요구 6.2). 하드코딩 금지.

### 4단계 중복 제거

동일 이벤트를 여러 매체가 보도한 경우 원문·최초 1건만 발송 후보로 남긴다.
- dedup_group 키: 제목·핵심 엔티티의 유사도로 그룹핑 (간단히는 제목 정규화 후 토큰 자카드 유사도 임계, 정교하게는 임베딩). 같은 그룹은 published_at이 가장 이른 것을 대표로.
- 24시간 내 동일 id 재발송 차단은 발송 단계(dashboard)에서 send_history로 처리하되, dedup_group은 필터가 설정한다.

## 설명 가능성 & 피드백

- 모든 발송 후보는 importance_reason이 비어있지 않아야 한다 (QA 검증 항목).
- FP/FN 피드백(feedback 테이블)은 향후 임계값 튜닝 입력이다. 필터는 피드백을 직접 읽지 않지만, 튜닝 재실행 시 사용자 피드백을 반영하여 임계값/프롬프트를 조정한다.

## 에러 핸들링

- LLM API 실패: 1회 재시도 → 재실패 시 score=null, send_recommended=false로 보류, 로그 기록. 전체 파이프라인은 계속.
- config에 임계값 누락: `references/scoring-prompts.md`의 기본값(8.5/7.0/4.0) 사용.

## 후속/재실행

이전 구현이 존재하면 Read하여 파악하고 피드백 부분만 수정한다. "너무 많이/적게 발송된다" 피드백은 임계값 또는 평가 프롬프트의 기준 강도를 일반화하여 조정한다 (특정 기사 1건에 오버피팅하지 않는다).
