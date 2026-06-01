---
name: news-batch-scoring
description: "API 키 없이 에이전트(Claude)가 직접 뉴스 중요도를 매기는 배치 채점. ANTHROPIC_API_KEY가 없어 수집된 뉴스가 미채점으로 남을 때, 또는 '뉴스 채점해줘/스코어 매겨줘/배치 채점/키 없이 채점' 작업 시 반드시 이 스킬을 사용. 후속 작업: 재채점, 새로 수집한 뉴스 채점, 채점 후 발송까지 시에도 사용."
---

# News Batch Scoring — 키 없이 에이전트 배치 채점

수집은 실시간(웹 '수집 실행' 버튼·`run.py`)으로 두고, **채점만** 떼어내 배치로 수행한다.
웹 서버 프로세스는 에이전트를 호출할 수 없어 실시간 채점에 `ANTHROPIC_API_KEY`가 필요하지만,
이 스킬에서는 **에이전트 자신(Claude)이 LLM 채점자 역할**을 하므로 키가 필요 없다.

핵심 원칙: **채점 기준은 코드의 `src/filters/scorer.py:_PROMPTS`와 동일**해야 한다(실시간 경로와
일관성 유지). export 결과의 각 항목에 그 카테고리 `criteria`가 포함돼 있으니 그대로 적용한다.

## 절차 (3단계)

가상환경 파이썬: `.venv\Scripts\python.exe`. DB 기본값: `data/news.db`.

### 1) 미채점 항목 내보내기
```
.venv\Scripts\python.exe -m src.batch_scoring export --db data/news.db --out data/_unscored.json
```
→ `data/_unscored.json` = `[{id, category, title, source, published_at, summary, criteria, duplicates}, ...]`
미채점(`importance_score IS NULL`) 항목만 나온다. 0건이면 채점할 게 없으니 종료.

**같은 뉴스 배제(중복 채점 방지):** export는 유사 제목을 한 그룹으로 묶어 **그룹당 대표 1건만**
내보낸다(같은 이벤트를 여러 매체가 보도해도 한 번만 채점). `duplicates`는 그 뉴스로 묶인 추가
건수다. apply 단계에서 대표 점수가 **그룹 전체에 자동 전파**되므로, 너는 대표만 채점하면 된다.
(필요하면 먼저 수집: 웹 '수집 실행' 또는 `.venv\Scripts\python.exe run.py`로 서버 띄운 뒤 수집.)

### 2) 에이전트가 채점 (이 스킬의 핵심)
`data/_unscored.json`을 읽고, **각 항목을 그 항목의 `criteria`(카테고리 평가기준)에 따라** 0~10점으로
판정한다. 제목·출처·발행·요약을 근거로:
- `score`: 0.0~10.0 (기준의 컷오프 단서를 그대로 적용. 예: 글로벌 AI는 파운데이션 모델/수십억 M&A/규제 판도/패러다임 연구 8.5+, 제품·마케팅·루머 3↓)
- `reason`: 1~2문장 한국어 근거
- `send`: 발송 추천 여부(기준상 의미 있으면 true)

결과를 **엄격한 JSON**으로 `data/_scores.json`에 쓴다(다른 텍스트 없이):
```json
{
  "<id>": {"score": 6.5, "reason": "전 계열사 확대로 의미 있음", "send": true},
  "<id>": {"score": 2.0, "reason": "단순 홍보성", "send": false}
}
```
- 항목 수가 많으면(수십~수백) 나눠 읽고 채점해도 되지만, 최종 `_scores.json`은 하나로 합친다.
- 과대·과소 채점 금지: 기준의 경계 단서를 기계적으로 적용해 실시간 LLM과 재현 가능하게.

### 3) 점수 적용 (게이팅·중복제거·저장)
```
.venv\Scripts\python.exe -m src.batch_scoring apply --db data/news.db --scores data/_scores.json
```
→ 대표 점수를 **같은 뉴스 그룹 전체에 전파** → 0~10 클램프 → 카테고리별 임계값 게이팅 → dedup(그룹당 1건만 발송추천) → upsert.
출력: `{scored(전파 포함 총 항목), unique(고유 뉴스 수), recommended, skipped}`. 이로써 미채점이던 항목이 점수·발송추천·중요뉴스로 채워진다.

## 검증·보고
- 적용 후 대시보드(전체뉴스·중요뉴스 탭)에 점수·중요뉴스가 반영됐는지 확인(서버 떠 있으면 리로드).
- 임시 파일(`data/_unscored.json`, `data/_scores.json`)은 정리하되, 필요 시 감사용으로 남겨도 된다.
- 보고: 채점 건수·중요뉴스 선정 수·카테고리별 분포.

## 경계
- **계약 불변**: NewsItem 필드·점수 범위(0~10)·임계값 형식·`{items,total}` API를 바꾸지 않는다.
- **수집 버튼은 유지**: 이 스킬은 채점만 담당한다. 키가 생기면 실시간 경로(`default_caller`)가 그대로 동작하므로 배치는 보조 경로다.
- 발송까지 원하면 채점 적용 후 `POST /api/send`(또는 대시보드 발송 버튼) — 월 캡·24h 중복차단이 적용된다.
