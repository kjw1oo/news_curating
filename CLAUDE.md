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
| 2026-05-30 | venv 3.12 재생성, 플러그인형 발송 채널(console/email)+발송 이력, FP/FN 피드백 루프, 범용 RSS 수집기(글로벌 AI 8·금융 AI 4 소스) 추가. QA 경계면 0건 | src/notifiers/, src/api/, src/web/, src/collectors/rss.py, config.yaml | 운영 루프(발송·피드백) 가동·글로벌 실데이터 소스 확장 |
| 2026-06-01 | UI 데스크톱(99)·모바일(96) 디자인 루프, 파이프라인 정밀도 감사(josa dedup 등), 전용 'woori'(우리금융그룹) 카테고리 신설(모델·채점·수집기·UI·임계값4.0·GoogleNews 한국어 RSS) | src/models.py, src/filters/scorer.py, src/collectors/woori.py, config.yaml, src/web/index.html, tests/ | UI 품질 수렴·정밀도 강화·우리금융 전용 트랙 분리 |
| 2026-06-01 | 탭 기반 4뷰 대시보드(개요/중요뉴스/전체뉴스/카테고리별, ARIA tablist+해시 라우팅) 신설 후 웹(97)·모바일(96) 10사이클씩, 우리금융 우선 분류 규칙(우리금융그룹 기사는 국내 금융 AI보다 woori 우선) | src/web/index.html, src/filters/category_rules.py, src/pipeline.py, config.yaml, tests/ | 정보 탐색성 향상·우리금융 트랙 우선순위 |
| 2026-06-01 | UI '발송 대상'→'중요뉴스' 문구 통일, 토스 수집기를 난독 DOM 크롤링→내부 JSON API(httpx, 브라우저 불필요)로 재작성. 라이브 30건 실수집 확인 | src/web/index.html, src/collectors/woori.py, tests/ | 용어 명확화·토스 수집 안정화(배포 무관) |
| 2026-06-01 | 배치 채점(news-batch-scoring 스킬) 추가 — API 키 없이 에이전트가 export→채점→apply(게이팅·dedup). 수집은 실시간 유지, 채점만 배치. 엔드투엔드 시연 | src/batch_scoring.py, src/storage.py(unscored), .claude/skills/news-batch-scoring/, tests/ | 키 없는 채점 경로 확보 |
| 2026-06-01 | 수행계획서 정렬: 국내 금융지주를 토스 종목 뉴스피드로 일반화(TossNewsCollector, 신한·KB·하나·기업은행·카뱅·JB·BNK·DGB), 농협 등 비상장은 매경 RSS. 글로벌 채점 강화(임계값 9.5/9.0+프롬프트 '판도전환급만'). 수집 병렬화(ThreadPool)+RSS httpx 타임아웃. 표시 합치기(중복 대표 1건+N표식)·7일창·최근2일 점수정렬·재평가(regate)·스탯카드 클릭·계층(국내⊇우리금융) | src/collectors/woori.py, src/collectors/__init__.py, src/pipeline.py, src/collectors/rss.py, src/api/app.py, src/web/index.html, config.yaml, tests/ | 원안(금융지주=토스) 복원·글로벌 빈도 최소화·프록시 환경 수집 안정화 |
| 2026-06-01 | 중복 물리제거(prune: 같은 사건 최고점수 1건만, apply에 자동 연결)·전이적 이벤트 그룹화(조직명 정규화+날짜게이팅, 한국 금융 한정). 카테고리별 탭 오늘자/중요뉴스 접이식 분리. news-pipeline-run 스킬 신설(수집→병렬채점→저장 전 사이클 + 번들 스크립트 collect/split/merge) | src/filters/postprocess.py, src/batch_scoring.py, src/storage.py, src/web/index.html, .claude/skills/news-pipeline-run/ | 중복 근절·운영 사이클 재현화 |
