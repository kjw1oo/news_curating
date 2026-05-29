---
name: news-web-design
description: "뉴스 모니터링 대시보드의 시각 리디자인 가이드. 디자인 토큰(컬러/타이포/간격), 중요도·카테고리 시각 위계, 알림 카드 레이아웃, 빈/로딩/에러 상태, 반응형·접근성을 정의. 기능·API 계약은 건드리지 않고 src/web/ 프레젠테이션만 개선할 때 사용. 리디자인/스타일링/테마/UI 다듬기 시 반드시 이 스킬을 사용."
---

# News Web Design — 대시보드 시각 리디자인

동작하는 대시보드를 **읽기 쉽고 보기 좋은** 화면으로 다듬는 스킬. 핵심 목표는 "빈도 최소화, 관심도 최대화"라는 제품 철학을 화면에 반영하는 것 — 정말 중요한 알림이 시각적으로 가장 먼저 눈에 들어와야 한다.

## 절대 규칙 (계약 보존)

`src/web/`만 수정한다. 백엔드/모델은 건드리지 않는다. 프론트가 읽는 필드는 고정:

- 목록 응답: `/api/news`, `/api/alerts` → `{ "items": [...], "total": N }`
- 항목 필드: `importance_score`(number|null), `category_label`(string), `url`, `title`, `importance_reason`, `source`, `published_at`
- 설정: `/api/config` → `{ thresholds: { global_ai, global_finance_ai, domestic_finance_ai }, ... }`

키 이름을 바꾸면 QA 경계면 검증에서 막힌다. 새 데이터가 필요하면 dashboard-dev에 요청한다.

## 디자인 토큰 (CSS 변수로 선언)

```css
:root{
  /* 컬러 */
  --bg: #0f1419;            /* 다크 베이스 (또는 라이트면 #f7f8fa) */
  --surface: #1a2029;       /* 카드 배경 */
  --surface-2: #222b36;
  --text: #e6e9ee;
  --text-dim: #9aa4b2;
  --border: #2a3340;
  --accent: #4c8dff;        /* 브랜드 액센트 */
  /* 카테고리 액센트 */
  --c-global-ai: #8b5cf6;
  --c-global-finance: #22c55e;
  --c-domestic-finance: #f59e0b;
  /* 점수 시그널 */
  --score-high: #ef4444;    /* 임계값 초과/발송 */
  --score-mid: #f59e0b;
  --score-low: #6b7280;
  /* 간격·형태 */
  --r: 14px; --gap: 16px;
  --shadow: 0 4px 20px rgba(0,0,0,.25);
}
```

라이트/다크 중 하나를 일관되게. 한글 가독성 좋은 시스템 폰트 스택 + (선택) Pretendard/Noto Sans KR 웹폰트 1종.

## 정보 위계

1. **발송 대상 알림** = 최상위. 더 큰 카드, 카테고리 액센트 좌측 보더 또는 상단 바, 점수 배지 강조.
2. **전체 뉴스 피드** = 보조. 더 작고 차분하게.
3. 점수 배지는 값에 따라 색을 달리한다(고/중/저). `null`이면 중립 회색 "–".
4. 카테고리는 pill 라벨 + 고유 액센트 컬러로 즉시 구분되게.

## 카드 구조 (필수 요소)

각 카드는 다음을 모두 표시: 카테고리 pill, 제목(원문 링크 `target=_blank rel=noopener`), 중요도 점수 배지, 판단 근거(`importance_reason`), 출처 + 발행일시. 알림 카드는 여기에 "발송 대상" 표식을 더한다.

## 상태 처리

- **빈 상태**: 아이콘/일러스트 + "표시할 뉴스가 없습니다" + 수집 실행 유도. `items` 항상 배열 가드.
- **로딩**: 수집 실행 시 버튼 비활성 + 스피너/스켈레톤.
- **에러**: fetch 실패 시 카드 대신 친절한 에러 배너.

## 레이아웃·반응형

- 컨테이너 max-width(예: 960px) 중앙 정렬, 넉넉한 여백.
- 카드 그리드: 데스크톱 멀티 컬럼(`grid-template-columns: repeat(auto-fill, minmax(320px,1fr))`), 모바일 1열.
- 헤더는 sticky 고려, 수집 버튼·상태 텍스트·설정 요약 배치.

## 접근성

- 본문 명도 대비 4.5:1 이상. 액센트 위 텍스트도 확인.
- 링크/버튼에 보이는 focus-visible 스타일. 시맨틱 태그(header/main/section/article).
- 점수/카테고리는 색에만 의존하지 말고 텍스트도 함께.

## 코드 구성

- 작으면 단일 `index.html`(인라인 CSS/JS) 유지 가능. 커지면 `styles.css` + `app.js`로 분리하고 `index.html`에서 링크.
- 무프레임워크·무빌드 — 바닐라 유지. 외부 CSS 프레임워크 금지(웹폰트 link 1종은 허용).

## 검증

서빙 후 실제 렌더 확인(빈 상태 + 데이터 있는 상태 + 모바일 폭). 픽셀 렌더 확인이 불가한 환경이면 그 사실을 명시하고, 최소한 HTML/JS가 올바른 필드를 읽는지 정적으로 확인한다.
