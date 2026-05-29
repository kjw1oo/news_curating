---
name: news-monitoring-orchestrator
description: "AI 뉴스 모니터링 시스템 개발 에이전트 팀을 조율하는 오케스트레이터. 뉴스 모니터링 시스템 구축/개발, 수집기·필터·대시보드 구현, 뉴스 큐레이션 시스템 작업 시 반드시 이 스킬을 사용. 후속 작업: 시스템 다시 빌드, 부분 재실행, 수집기/필터/대시보드만 다시, 소스 조사, 소스 결정, 임계값 튜닝, 피드백 반영, 오발송·누락 조정, 소스 추가, 알림 채널 추가, 결과 개선·업데이트·수정·보완 요청 시에도 반드시 이 스킬을 사용."
---

# News Monitoring Orchestrator

AI 뉴스 모니터링 시스템을 구축하는 개발 에이전트 팀을 조율하는 통합 스킬. 설계→병렬 구현→통합 검증으로 수집·필터링·대시보드를 갖춘 동작하는 시스템을 만든다.

## 실행 모드: 에이전트 팀

설계자↔구현자↔검증자 간 피드백 루프와, 빌드 에이전트들이 공유 데이터 스키마(계약)를 실시간으로 맞춰야 하므로 에이전트 팀이 최적이다. 아키텍처 패턴은 **파이프라인(설계) + 팬아웃(병렬 구현) + 생성-검증(점진 QA)** 복합형.

## 에이전트 구성

| 팀원 | 에이전트 타입 | 역할 | 스킬 | 출력 |
|------|-------------|------|------|------|
| architect | architect (커스텀) | 구조·표준 스키마 설계 | news-system-design | `_workspace/01_architect_*.md` |
| collector-dev | collector-dev (커스텀) | 수집 계층 | news-collector-dev | `src/collectors/` |
| filter-dev | filter-dev (커스텀) | 필터 파이프라인 | news-filter-dev | `src/filters/` |
| dashboard-dev | dashboard-dev (커스텀) | API·대시보드·알림 | news-dashboard-dev | `src/api/`, `src/web/` |
| qa-inspector | general-purpose | 통합 정합성 검증 | news-qa | `_workspace/05_qa_report.md` |
| source-researcher | general-purpose | 소스 실제 검증·선정 (단독, 팀 외) | news-source-research | `_workspace/00b_source_research.md` |
| threshold-tuner | general-purpose | 피드백→임계값 조정안 제안 (단독, 팀 외) | news-threshold-tuning | `_workspace/06_tuning_proposal.md` |

모든 Agent/TeamCreate 멤버는 `model: "opus"`를 명시한다.

> source-researcher와 threshold-tuner는 빌드 팀(위 5인)에 상주하지 않고, 각각 리서치·튜닝 모드에서 **단독 서브 에이전트(`Agent` 도구)** 로 호출된다. 하네스는 빌드 팀 + 단독 에이전트의 하이브리드 구조다.

## 워크플로우

### Phase 0: 컨텍스트 확인 (후속 작업 지원)

1. `_workspace/` 존재 여부 확인
2. 실행 모드 결정:
   - **미존재** → 초기 빌드. Phase 1로
   - **존재 + 부분 수정 요청**(예: "필터 임계값만 조정", "수집기에 소스 추가") → 부분 재실행. 해당 에이전트만 재호출, 프롬프트에 이전 산출물 경로 포함
   - **존재 + 새 요구사항** → 새 빌드. 기존 `_workspace/`를 `_workspace_{YYYYMMDD_HHMMSS}/`로 이동 후 Phase 1
3. 부분 재실행 시 단일 빌드 에이전트만 필요하면 팀을 만들지 않고 `Agent` 도구로 직접 호출해도 된다 (오버헤드 절감).

### Phase 0.5: 요청 분류 (3모드 라우팅)

Phase 0 직후, 요청 표현을 분류하여 다음 3개 모드 중 하나로 라우팅한다.

| 모드 | 트리거 표현 | 동작 |
|------|------------|------|
| **리서치** | 소스 조사, 소스 결정, 어떤 소스 쓸지, 글로벌 소스 확정 | source-researcher를 `Agent` 도구로 단독 실행 → `_workspace/00b_source_research.md` 산출 (collector-dev 입력). 빌드 팀 미생성. |
| **빌드** (기존) | 구축, 빌드, 구현, 시스템 만들기 | Phase 1~5 5인 팀 파이프라인. `00b_source_research.md`가 있으면 architect가 참조하고, 없으면 "소스를 먼저 확정할까요?"를 제안. |
| **튜닝** | 임계값 튜닝, 피드백 반영, 오발송·누락이 많다, 알림 빈도 조정 | threshold-tuner를 `Agent` 도구로 단독 실행 → `_workspace/06_tuning_proposal.md` 제안 → 운영자 승인 시 `config.yaml` 패치 → filter 재실행. 빌드 팀 미생성. |

리서치·튜닝 모드는 단독 서브 에이전트이므로 TeamCreate 없이 `Agent` 도구로 호출한다. 빌드 모드만 아래 Phase 1~5를 따른다.

### Phase 1: 준비
1. 사용자 요구사항 분석 — 카테고리·소스·알림 표면 확인
2. `_workspace/` 생성 (새 빌드면 기존 것 이동 후 재생성)
3. 요구사항을 `_workspace/00_input/requirements.md`에 저장

### Phase 2: 설계 (파이프라인 1단계 — 선행)

**설계가 먼저다.** 스키마 계약 없이 빌드 에이전트가 시작하면 경계면이 어긋난다.

architect를 먼저 실행하여 `_workspace/01_architect_schema.md`(표준 스키마)와 `01_architect_design.md`(구조)를 확정한다. 팀을 이 단계부터 구성하고, architect가 스키마 확정 시 `SendMessage({to:"all"})`로 브로드캐스트하면 빌드 에이전트들이 착수한다.

```
TeamCreate(
  team_name: "news-build-team",
  members: [
    {name:"architect",      agent_type:"architect",      model:"opus", prompt:"news-system-design 스킬로 시스템 구조와 표준 데이터 스키마를 설계. _workspace/00_input/requirements.md를 읽고 _workspace/01_architect_design.md, 01_architect_schema.md 작성. 완료 시 SendMessage로 전체에 스키마 확정 통지."},
    {name:"collector-dev",   agent_type:"collector-dev",  model:"opus", prompt:"news-collector-dev 스킬로 수집 계층 구현. architect의 스키마 확정 후 _workspace/01_architect_schema.md를 읽고 시작. 산출물 src/collectors/."},
    {name:"filter-dev",      agent_type:"filter-dev",     model:"opus", prompt:"news-filter-dev 스킬로 4단계 필터 파이프라인 구현. 스키마 확정 후 착수. 산출물 src/filters/."},
    {name:"dashboard-dev",   agent_type:"dashboard-dev",  model:"opus", prompt:"news-dashboard-dev 스킬로 FastAPI+대시보드 구현. 스키마 확정 후 착수. 산출물 src/api/, src/web/."},
    {name:"qa-inspector",    agent_type:"general-purpose",model:"opus", prompt:"news-qa 스킬로 통합 정합성 검증. 각 모듈 완성 직후 점진 검증. 경계면 이슈는 양쪽 에이전트에 수정 요청. 산출물 _workspace/05_qa_report.md."}
  ]
)
```

### Phase 3: 병렬 구현 (팬아웃)

**실행 방식:** 팀원 자체 조율

스키마 확정 후 collector-dev, filter-dev, dashboard-dev가 공유 작업 목록에서 작업을 claim하여 병렬 구현한다.

```
TaskCreate(tasks: [
  {title:"표준 스키마 설계",        assignee:"architect"},
  {title:"수집 계층 구현",          assignee:"collector-dev", depends_on:["표준 스키마 설계"]},
  {title:"필터 파이프라인 구현",     assignee:"filter-dev",    depends_on:["표준 스키마 설계"]},
  {title:"대시보드·API 구현",       assignee:"dashboard-dev", depends_on:["표준 스키마 설계"]},
  {title:"수집기 경계면 검증",       assignee:"qa-inspector",  depends_on:["수집 계층 구현"]},
  {title:"필터 경계면 검증",         assignee:"qa-inspector",  depends_on:["필터 파이프라인 구현"]},
  {title:"대시보드 경계면 검증",     assignee:"qa-inspector",  depends_on:["대시보드·API 구현"]},
])
```

**통신 규칙:**
- collector-dev → filter-dev: NewsItem 출력 형식 통지
- filter-dev → dashboard-dev: 발송 대상 정의(send_recommended + 임계값) 통지
- 각 빌드 에이전트 → qa-inspector: 모듈 완성 시 검증 요청
- qa-inspector → 빌드 에이전트(들): 경계면 이슈 발견 시 양쪽 모두에 수정 요청

**리더 모니터링:** 유휴 알림 수신, 막힌 팀원에 SendMessage, TaskGet으로 진행률 확인.

### Phase 4: 통합 검증 & 동작 확인
1. 모든 작업 완료 대기 (TaskGet)
2. qa-inspector의 `_workspace/05_qa_report.md`에서 미해결 경계면 이슈 확인 → 있으면 해당 에이전트에 재수정 요청 (최대 2회)
3. 시스템을 실제 실행하여 동작 확인:
   - 의존성 설치(requirements.txt), `POST /api/collect`로 수집·평가 트리거, 대시보드에 알림 카드 렌더 확인
   - UI 동작은 type check/테스트가 아니라 실제 실행으로 확인. 불가하면 그 사실을 명시
4. 최종 산출물: 프로젝트 루트의 `src/`, `config.yaml`, 실행 안내

### Phase 5: 정리
1. 팀원 종료 (SendMessage) → TeamDelete
2. `_workspace/` 보존 (감사 추적)
3. 사용자에게 결과 요약 + 실행 방법 보고
4. **피드백 요청** (Phase 7 진화): "결과에서 개선할 부분이나 워크플로우에 바꾸고 싶은 점이 있나요?"

## 데이터 흐름

```
[리서치 모드]
  [source-researcher] → _workspace/00b_source_research.md  (채택 소스 + 화이트리스트)
                                   │ collector-dev 입력 / architect 참조
                                   ▼
[빌드 모드]
requirements.md (+ 00b 있으면 참조)
   → [architect] → 01_architect_schema.md (계약)
                      │ SendMessage(all): 스키마 확정
        ┌─────────────┼─────────────┐
   [collector-dev] [filter-dev] [dashboard-dev]   ← 병렬, 스키마 준수
   src/collectors/  src/filters/  src/api/+web/
        └─────────────┼─────────────┘
                 [qa-inspector] ← 각 모듈 완성 직후 경계면 교차 검증
                      ↓
                 동작하는 시스템

[튜닝 모드 — 운영 후]
  feedback + send_history (SQLite)
      → [threshold-tuner] → _workspace/06_tuning_proposal.md
      → (운영자 승인) → config.yaml 패치 → filter 재실행
```

## 에러 핸들링

| 상황 | 전략 |
|------|------|
| 빌드 에이전트 1명 실패/중지 | 리더 감지 → 상태 확인 → 재시작 또는 작업 재할당 |
| 스키마 미확정으로 빌드 지연 | architect 우선 완료 보장, 빌드 에이전트는 대기 |
| 경계면 이슈 반복(2회 초과) | 리더가 스키마 자체를 재검토(architect에 위임) |
| 크롤링 법적 제약 | 강행 금지, RSS/WebSearch 대체 경로로 전환하고 보고서에 명시 |
| LLM/네트워크 실패 | 1회 재시도 후 누락 명시하고 진행 |
| 상충 데이터 | 삭제하지 않고 출처 병기 |

## 테스트 시나리오

### 정상 흐름
1. 사용자가 요구사항 제공 → Phase 1에서 `_workspace/` 생성
2. Phase 2에서 architect가 스키마 확정 → 전체 브로드캐스트
3. Phase 3에서 3개 빌드 에이전트 병렬 구현, qa-inspector 점진 검증
4. Phase 4에서 경계면 이슈 해소 + `POST /api/collect`로 동작 확인
5. 예상 결과: `src/` 동작 코드 + 대시보드에 알림 카드 렌더

### 에러 흐름
1. Phase 3에서 dashboard-dev가 API 응답을 배열로 반환(래핑 누락)
2. qa-inspector가 "대시보드 경계면 검증"에서 `{items}` 래핑 불일치 발견
3. dashboard-dev와 (계약 주체) architect 양쪽에 수정 요청
4. dashboard-dev가 래핑 적용 → 재검증 통과
5. Phase 4 정상 진행, 보고서에 "API 래핑 불일치 1건 수정" 기록
