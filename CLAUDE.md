# news_curating

## 하네스: AI 뉴스 모니터링 시스템 (개발형)

**목표:** AI 관련 뉴스를 카테고리별 중요도 기준으로 자동 수집·필터링하고, 의미 있는 뉴스가 발생했을 때만 알림하는 모니터링 시스템을 구축한다. 핵심 원칙은 "빈도 최소화, 관심도 최대화".

**트리거:** 뉴스 모니터링 시스템 구축/개발, 수집기·필터·대시보드 구현, 임계값 튜닝, 소스 추가, 알림 채널 추가, 부분 재실행 등 이 도메인 작업 요청 시 `news-monitoring-orchestrator` 스킬을 사용하라. 단순 질문은 직접 응답 가능.

**구성 요약:** 개발형 하네스(코드를 작성하는 팀). 실행 모드는 에이전트 팀(설계→병렬 구현→점진 QA). 1차 알림 표면은 웹 대시보드(데모 페이지). 글로벌 소스는 RSS + WebSearch 병행, 국내는 토스인베스트 크롤링. 기술 스택은 Python + FastAPI + SQLite.

**변경 이력:**
| 날짜 | 변경 내용 | 대상 | 사유 |
|------|----------|------|------|
| 2026-05-29 | 초기 구성 (architect/collector-dev/filter-dev/dashboard-dev/qa-inspector + 6개 스킬 + 오케스트레이터) | 전체 | - |
| 2026-05-29 | source-researcher·threshold-tuner 추가, 오케스트레이터 3모드 라우팅, Scrapling 크롤링 확정 | agents/, skills/, orchestrator | 소스 결정·학습 루프 갭 보완 |
| 2026-05-29 | web-designer 에이전트·news-web-design 스킬 추가, WebSearch 수집기·1차 실데이터 적재, 대시보드 다크 테마 리디자인 | agents/, skills/, src/collectors/, src/web/ | 시각 표면 품질·실데이터 검증 |
