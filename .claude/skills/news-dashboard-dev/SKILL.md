---
name: news-dashboard-dev
description: "뉴스 모니터링 대시보드(데모 페이지)와 알림 표면을 구현. FastAPI 백엔드 + 웹 대시보드로 카테고리별 뉴스 피드, 발송된 알림 카드, 발송 이력, 임계값 설정 UI, FP/FN 피드백, 플러그인형 알림 채널(이메일 등)을 제공. 대시보드/데모페이지/API/알림발송/UI/이력/설정 구현·수정 시 반드시 이 스킬을 사용."
---

# News Dashboard Dev — 대시보드 & 알림 표면 구현

모니터링 결과를 사람이 보는 표면으로 만드는 스킬. 사용자가 선택한 1차 알림 표면은 **웹 대시보드(데모 페이지)** 이며, 알림 채널은 플러그인으로 확장 가능하다.

## 시작 전 필수

`_workspace/01_architect_schema.md`를 Read하여 NewsItem·send_history·config 형식을 확인한다. **API 응답 shape을 스키마와 일치**시키고, 리스트 응답은 `{"items":[...], "total":N}`로 래핑한 뒤 프론트가 `.items`를 꺼내 쓰게 한다 (경계면 버그 방지 — QA가 교차 검증함).

## FastAPI 백엔드

```python
GET  /api/news?category=&min_score=     # NewsItem 목록 (래핑)
GET  /api/alerts                        # send_recommended=true 발송 카드
GET  /api/history                       # send_history 목록
GET  /api/config                        # 현재 임계값/주기/캡
POST /api/config                        # 임계값 등 수정 (운영자 조정)
POST /api/feedback                       # {news_id, kind, note} FP/FN 피드백
POST /api/collect                        # 수동 수집·평가 트리거 (데모용)
```

API는 storage 계층을 통해 SQLite를 읽고 쓴다. snake_case 필드명을 응답에서 유지한다 (프론트 타입과 일치).

## 웹 대시보드 (정적)

FastAPI가 `src/web/index.html`을 서빙한다. 과한 프레임워크 금지 — 바닐라 JS + 최소 CSS로 명료하게. 데모 품질이면 충분하다.

구성:
- **상단**: "수집 실행" 버튼(`POST /api/collect`), 카테고리 필터 탭
- **알림 카드 영역**: 발송 대상 뉴스를 카드로. 각 카드는 요구사항 5.3 필수 요소를 모두 표시
- **뉴스 피드**: 전체 수집 뉴스 + 점수, 필터 통과 여부
- **발송 이력**: 발송 일시·카테고리·제목
- **설정 패널**: 카테고리별 임계값 슬라이더/입력 → `POST /api/config`
- **피드백 버튼**: 각 항목에 "오발송(FP)"/"누락(FN)" 버튼 → `POST /api/feedback`

## 알림 메시지 구성 (요구사항 5.3)

발송/카드 표시 시 필수 포함:
- 카테고리 레이블 (글로벌 AI / 글로벌 금융 AI / 국내 금융 AI)
- 뉴스 제목 (원문)
- AI 생성 요약 3~5줄 (없으면 summary_raw 축약)
- 중요도 판단 근거 (importance_reason)
- 원문 링크
- 출처 매체명 + 발행 일시

제목 형식: `[카테고리명] 뉴스 알림 — {주요 키워드}`. 묶음 발송 시: 건별 요약을 순서대로 나열 + 총 건수 명시.

## 알림 발송 로직 (이벤트 기반)

- 정기 스케줄 없음. send_recommended=true이고 아직 미발송인 항목 발생 시에만 발송.
- **24시간 재발송 차단**: send_history에 동일 news_id가 최근 24h 내 있으면 발송하지 않음.
- **묶음 발송**: batch_window_minutes(기본 90분) 내 복수 후보를 batch_id로 묶어 1회 발송 (특히 국내 뉴스).

## 플러그인형 알림 채널

```python
class Notifier:
    def send(self, items, batch_id) -> bool: ...

class DashboardNotifier(Notifier):   # 기본 — DB에 발송 기록, 대시보드가 표시
    ...
class EmailNotifier(Notifier):       # 확장 스텁 — 추후 Gmail 등 연동
    ...
```

config의 `notifiers` 목록으로 활성 채널을 결정한다. 기본은 `["dashboard"]`. 새 채널 추가 = Notifier 구현 1개 + config 등록. (요구사항: 최소 1채널 필수, 복수 병행은 추후 결정)

## 에러 핸들링

- 채널 발송 실패: 1회 재시도 → 재실패 시 발송 실패 상태로 기록, 대시보드에 표시
- 데이터 없음: 빈 상태(empty state) 정상 렌더 (`filter is not a function` 류 방지 — 항상 배열 보장)

## 후속/재실행

이전 구현이 존재하면 Read하여 파악하고 피드백 부분만 수정한다. "이메일도 보내고 싶다"는 요청은 EmailNotifier를 구현하고 config notifiers에 추가하는 것으로 처리한다 (대시보드 코드 변경 최소).
