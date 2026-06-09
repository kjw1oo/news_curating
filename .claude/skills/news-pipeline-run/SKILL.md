---
name: news-pipeline-run
description: "AI 뉴스 모니터링의 전체 배치 사이클(데이터 수집 → 에이전트 병렬 채점 → 로컬 SQLite 저장)을 한 번에 실행. API 키 없이 에이전트가 채점하고, 수집 병렬화·중복 제거·미채점 0까지 보장한다. '수집 돌려', '배치 돌려', '데이터 수집하고 점수매겨', '뉴스 수집·채점', '파이프라인 돌려', '뉴스 갱신' 등 수집과 채점을 함께(또는 둘 중 하나라도) 요청할 때 반드시 이 스킬을 사용. 단순 채점만(이미 수집된 미채점 항목 채점)이면 수집 단계를 건너뛰고 2단계부터 진행."
---

# News Pipeline Run — 수집 → 채점 → 로컬 DB 저장

AI 뉴스 모니터링 시스템의 운영 사이클을 통째로 돈다. 핵심은 **수집은 실시간 코드가, 채점은
에이전트(Claude)가** 맡는 분업이다 — 웹 서버 프로세스는 에이전트를 호출할 수 없어 실시간 LLM
채점에 `ANTHROPIC_API_KEY`가 필요하지만, 이 스킬에서는 **네가 직접 채점자가 되어** 키 없이 채점한다.

전체 흐름: **수집(병렬) → 미채점 export(중복 대표만) → 청크 분할 → 병렬 채점 에이전트 → 병합 →
적용(점수 전파·임계값 게이팅·중복 물리제거) → 검증·정리.** 결과는 `data/news.db`(SQLite)에 저장된다.

## 전제

- **CWD는 프로젝트 루트** (`config.yaml`, `src/`, `data/`가 있는 곳).
- 파이썬: `.venv\Scripts\python.exe` (Windows). 콘솔 한글 깨짐 방지로 `$env:PYTHONIOENCODING='utf-8'`.
- 이 스킬 디렉터리: `.claude/skills/news-pipeline-run/` (아래 `scripts/`를 그대로 호출).
- 수집은 이 환경의 TLS 프록시가 동시연결을 throttle해 **~3분** 걸린다(소스 23개). 정상이다 —
  반드시 **백그라운드로 돌리고** 완료 알림을 기다려라. 절대 포그라운드에서 막혀 기다리지 마라.

## 1) 수집 (백그라운드)

소스(토스 금융지주 종목 + 글로벌/매경/우리금융 RSS + WebSearch 시드)를 병렬 수집해 미채점으로 저장한다.

```
.venv\Scripts\python.exe .claude\skills\news-pipeline-run\scripts\collect.py
```

- **백그라운드로 실행**하고 완료 알림을 기다린다. 출력 예: `수집 완료 163s: {collected, kept, stored, recommended} | 미채점 N건`.
- 재수집이라도 **기존 채점·발송 상태는 보존**된다(키 없는 수집이 점수를 지우지 않음). 새 기사만 미채점으로 들어온다.
- "이미 수집됐고 채점만" 요청이면 이 단계를 건너뛴다.

## 2) 미채점 export (중복 대표만)

```
.venv\Scripts\python.exe -m src.batch_scoring export --db data/news.db --out data/_unscored.json
```

같은 사건(유사 제목)은 **그룹당 대표 1건만** 나온다(같은 뉴스를 여러 번 채점하지 않음 — 점수는 apply에서
그룹 전체에 전파됨). `미채점 N건 → data/_unscored.json` 출력. **0건이면 채점할 게 없으니 6단계로.**

## 3) 청크 분할

```
.venv\Scripts\python.exe .claude\skills\news-pipeline-run\scripts\split_chunks.py 6
```

`data/_chunk_0.json .. _chunk_5.json` 생성(대표 ~20건당 1청크면 적당, 기본 6). 미채점이 적으면 청크 수를 줄여도 된다.

## 4) 병렬 채점 (이 스킬의 핵심)

생성된 청크 수만큼 **병렬 서브에이전트**(general-purpose, model sonnet)를 **한 메시지에서 동시에** 띄운다.
각 에이전트는 자기 청크(`data/_chunk_i.json`)를 읽어 각 항목을 그 항목의 `criteria`에 따라 채점하고
`data/_scores_i.json`에 **엄격한 JSON만** 쓴다. 에이전트 프롬프트에 아래 채점 기준을 그대로 넣어라:

> 입력 `data/_chunk_<i>.json` = `[{id, category, title, source, published_at, summary, criteria}]`.
> 각 항목을 그 `criteria`로 0~10 채점. **아주 엄격하게(빈도 최소화 — 진짜 가치 있는 것만 높게):**
> - **global_ai**: 판도 전환급만 9.5+ (신규 프런티어 파운데이션 모델·100억$+ 딜·업계 바꾸는 규제 확정·새 아키텍처급 연구). 그 외 제품·점진연구·벤치마크·파트너십·소규모펀딩·전망/오피니언 6↓, 마케팅·루머·요약 2↓.
> - **global_finance_ai**: 금융권을 실제로 흔드는 대형 AI 사건만 9+ (대형기관 대규모 공식 AI전략·전사도입·시장구조 변화·중대 규제). 일상 도입·파일럿·벤더발표·단순언급 5↓.
> - **domestic_finance_ai / woori**: 금융사의 실제 AI·데이터 활동(서비스·조직·투자·마이데이터) 4+. **금융과 무관한 기사(반도체·일반경제·정치 등)는 2↓.**
> 제목·출처·요약 근거로만 판단하고 지어내지 마라.
> **`reason`은 영어 기사라도 반드시 한국어로 작성한다(대시보드 카드 설명에 그대로 노출됨 — 영어 근거 금지).**
> 출력: `data/_scores_<i>.json`에 `{"<id>": {"score": 6.5, "reason": "1~2문장 한국어", "send": true}, ...}` — 모든 입력 id 포함, score는 0~10 숫자, send는 카테고리 임계값(global_ai 9.5 / global_finance 9.0 / domestic 6.5 / woori 5.5) 이상이면 true 경향.

채점 기준은 `src/filters/scorer.py`의 `_PROMPTS`(카테고리별 평가 프롬프트)와 일치해야 한다 — export가
각 항목에 그 `criteria`를 이미 담아 보내므로, 에이전트는 그걸 우선 따른다. 모든 에이전트가 끝날 때까지 기다린다.

## 5) 병합 + 적용 (점수 전파·게이팅·중복 물리제거)

```
.venv\Scripts\python.exe .claude\skills\news-pipeline-run\scripts\merge_scores.py
.venv\Scripts\python.exe -m src.batch_scoring apply --db data/news.db --scores data/_scores.json
```

- `merge_scores.py`: 에이전트별 점수를 `data/_scores.json`으로 합치고 **커버리지 검증**(누락 0 확인).
  누락이 있으면 그 id만 다시 채점해 채워라.
- `apply`: 대표 점수를 **같은 뉴스 그룹 전체에 전파** → 0~10 클램프 → 카테고리 임계값 게이팅 → dedup →
  upsert → **중복 뉴스 물리 제거(최고 점수 1건만 남김)**. 출력 예: `{scored, unique, recommended, skipped, removed_duplicates}`.

## 6) 검증 + 정리

```
.venv\Scripts\python.exe -c "from src.storage import Storage; from datetime import date; from collections import Counter; st=Storage('data/news.db'); al=[r for r in st.query(max_age_days=7,today=date.today()) if r.send_recommended]; print('7일 중요뉴스', len(al), dict(Counter(r.category for r in al)), '| 미채점', len(st.unscored()))"
```

- **미채점 0**이어야 한다(아니면 5단계 재채점). 7일 중요뉴스가 카테고리별로 합리적인지(국내 위주, 글로벌 소수) 확인.
- 임시 파일 정리: `data/_unscored.json`, `data/_scores.json`, `data/_chunk_*.json`, `data/_scores_*.json` 삭제.
- 대시보드 서버가 떠 있으면(`.claude/launch.json`의 `news-demo`, 포트 8000) 브라우저 새로고침으로 반영된다.
  서버가 죽어 502가 나면 재시작(preview_start 또는 `.venv\Scripts\python.exe run.py`).
- 사용자에게 보고: 수집 건수 · 채점 고유 수 · 제거된 중복 수 · 7일 중요뉴스(카테고리별).

## 경계·참고

- **계약 불변**: NewsItem 필드·점수 0~10·임계값 형식·API `{items,total}`을 바꾸지 않는다. 이 스킬은 데이터만 채운다.
- **키가 생기면**: 실시간 채점 경로(`scorer.default_caller`)가 동작하므로 배치는 보조가 된다. 키 없을 땐 이 스킬이 정식 채점 경로다.
- **임계값/소스 조정**은 별도다 — 임계값 튜닝은 `news-threshold-tuning`(또는 `regate` 명령), 소스 추가는 `news-collector-dev`/`config.yaml`.
- 단계가 길어 보여도 2·3·5·6은 즉시 끝난다. 시간이 걸리는 건 1(수집 ~3분)과 4(병렬 채점 ~1분)뿐이다.
