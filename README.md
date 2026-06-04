# 뉴스 모니터링 시스템 (news_curating)

AI·금융 뉴스를 **카테고리별 중요도 기준으로 자동 수집·채점·중복제거**하고, 의미 있는
뉴스만 골라 대시보드에 보여주는 모니터링 시스템.

> **핵심 원칙: "빈도 최소화, 관심도 최대화"** — 글로벌은 판도 전환급만, 국내·우리금융은
> 전용 트랙으로 촘촘히.

🔗 **라이브 대시보드: https://news-curating.vercel.app**

---

## 한눈에 보는 구조

```
                     ┌─────────────── 로컬(이 PC) 또는 배치/cron ────────────────┐
   소스                 수집           필터·채점 파이프라인 (src/pipeline.py)
 ┌─────────┐        ┌──────────┐   ┌──────────────────────────────────────────┐
 │ RSS 16+ │──┐     │ RSS      │   │ keyword → woori우선 → score → threshold  │
 │ Toss API│──┼───▶ │ Toss JSON│──▶│   → dedup → upsert                        │
 │ (종목)  │  │     │ (httpx)  │   └──────────────────────────────────────────┘
 └─────────┘  │     └──────────┘                      │ 저장
              │     ※ I/O 병렬(ThreadPool)            ▼
              │                          ┌─────────────────────────────┐
              │                          │  Storage (src/storage.py)   │
              │                          │  드라이버 무관:              │
              │                          │  · 로컬 = sqlite3 (data/)   │
              │                          │  · 클라우드 = Turso/libSQL  │
              │                          │    (src/turso_http.py)      │
              │                          └─────────────────────────────┘
              │                                  ▲ 읽기         ▲ 읽기/쓰기
              │                                  │              │
   ┌──────────┘                    ┌─────────────┴───┐   ┌──────┴────────────┐
   │ 채점은 API 키 없이              │ 로컬 서버        │   │ Vercel 서버리스    │
   │ 에이전트 배치로                │ run.py (uvicorn) │   │ api/index.py       │
   │ (src/batch_scoring.py)        │ :8000           │   │ (@vercel/python)   │
   └───────────────────────        └─────────────────┘   └───────────────────┘
                                          │                       │
                                          ▼                       ▼
                              FastAPI (src/api/app.py) + 대시보드(src/web/index.html)
```

---

## 기술 스택

| 레이어 | 사용 기술 |
|---|---|
| **프론트엔드** | **바닐라 HTML/CSS/JS 단일 파일** (`src/web/index.html`). 프레임워크·빌드 없음. CSS 커스텀 프로퍼티 다크 테마, ARIA tablist + 해시 라우팅, `fetch` API, Noto Sans KR |
| **백엔드 API** | **FastAPI** (`create_app`) + **Pydantic**. 로컬은 **uvicorn**(`run.py`), 클라우드는 **Vercel 서버리스**(`api/index.py`, `@vercel/python`) |
| **저장소** | 드라이버 무관 `Storage`. 로컬 **SQLite**(`sqlite3`), 클라우드 **Turso/libSQL**(순수 httpx HTTP API, `src/turso_http.py`) |
| **수집** | **RSS**(`feedparser`/`httpx`/`lxml`) + **토스인베스트 내부 JSON API**(`httpx`). 소스는 `config.yaml`로 플러그인식 등록 |
| **채점** | 카테고리별 평가 프롬프트. ANTHROPIC_API_KEY가 있으면 실시간, 없으면 **Claude 에이전트 배치 채점** |
| **배포** | GitHub → Vercel(프론트+API) + Turso(DB). 영구 URL |
| **테스트** | `pytest` (117 테스트) |

---

## 디렉터리 구조

```
news_curating/
├── api/
│   └── index.py            # Vercel 서버리스 진입점(표시 전용: 수집 비활성)
├── run.py                  # 로컬 서버 진입점(uvicorn :8000, 수집 활성)
├── vercel.json             # Vercel 빌드/라우팅(@vercel/python)
├── config.yaml             # 소스·임계값·키워드·채널 등 모든 운영 설정
├── requirements.txt        # 런타임 의존성(로컬·Vercel 공용)
├── requirements-dev.txt    # + pytest
│
├── src/
│   ├── models.py           # NewsItem(dataclass), Category, LABELS, make_id
│   ├── pipeline.py         # run_pipeline: 수집→필터→채점→게이팅→dedup→저장
│   ├── storage.py          # Storage: sqlite/Turso 자동 분기, 스키마, 쿼리/이력/피드백
│   ├── turso_http.py       # Turso(libSQL) HTTP API 클라이언트(순수 httpx)
│   ├── batch_scoring.py    # 키 없는 배치 채점(export_unscored / apply_scores / prune)
│   │
│   ├── collectors/         # 수집 계층
│   │   ├── __init__.py     #   build_rss_collectors / build_toss_collectors (config 팩토리)
│   │   ├── rss.py          #   RSSCollector (feedparser, 최신성 필터)
│   │   ├── woori.py        #   TossNewsCollector (토스 종목 뉴스 JSON API)
│   │   ├── websearch.py    #   WebSearch 기반 수집(보조)
│   │   └── base.py         #   Collector 프로토콜
│   │
│   ├── filters/            # 필터·채점·후처리
│   │   ├── keyword.py      #   키워드 1차 필터
│   │   ├── category_rules.py #  우리금융 우선 분류(woori_entities)
│   │   ├── scorer.py       #   카테고리별 중요도 채점(프롬프트·caller)
│   │   └── postprocess.py  #   임계값 게이팅, 중복 그룹화/물리제거(transitive)
│   │
│   ├── notifiers/          # 플러그인형 발송 채널
│   │   ├── registry.py     #   채널 레지스트리
│   │   ├── console.py / email.py  # 채널 구현
│   │   └── service.py      #   run_send(월 캡·24h 재발송 차단·이력 기록)
│   │
│   ├── api/app.py          # FastAPI create_app(라우트 정의)
│   └── web/index.html      # 대시보드(바닐라 JS 단일 파일)
│
├── tests/                  # pytest (117)
└── .claude/                # 에이전트·스킬(개발용 하네스)
```

---

## 데이터 모델 & 카테고리

`NewsItem` (src/models.py) — id(URL sha256 16자), category, title, url, source,
published_at, collected_at, summary_raw, **importance_score**(0~10), importance_reason,
**send_recommended**, dedup_group, sent/sent_at.

| 카테고리 | 라벨 | 임계값 | 주 소스 |
|---|---|---|---|
| `global_ai` | 글로벌 AI | **9.5** | GoogleNews·MIT TR·TechCrunch·Ars·Google/DeepMind 블로그 등 RSS |
| `global_finance_ai` | 글로벌 금융 AI | **9.0** | GoogleNews(금융 AI)·Finextra |
| `domestic_finance_ai` | 국내 금융 AI | **6.5** | 토스 종목 뉴스(신한·KB·하나·기업·카뱅·JB·BNK·DGB)·매경 RSS |
| `woori` | 우리금융그룹 | **5.5** | 토스(우리금융지주 A316140)·GoogleNews 한국어 |

> 임계값이 높을수록 통과가 어려움 → 글로벌은 "진짜 큰 뉴스"만, 우리금융은 전용 트랙으로 더 많이.
> 계층: 국내 금융 AI ⊇ 우리금융(우리금융 기사는 woori로 **우선** 분류).

---

## 파이프라인 (src/pipeline.py)

```
collect (ThreadPool 병렬)
  → keyword_filter        (config.keyword_filters)
  → apply_woori_priority  (우리금융 엔티티 → woori 우선)
  → score                 (카테고리별 프롬프트, 0~10)
  → apply_threshold       (카테고리 임계값 이상만 send_recommended)
  → dedup                 (유사 기사 묶기)
  → storage.upsert        (재수집 시 기존 점수·발송상태 보존)
```

**채점은 두 경로**
- **실시간**: `ANTHROPIC_API_KEY`가 있으면 수집과 동시에 채점.
- **배치(키 없음)**: `src/batch_scoring.py` — ① `export_unscored`(미채점 항목+기준 JSON 추출)
  → ② Claude 에이전트가 기준대로 `{score, reason, send}` 판정 → ③ `apply_scores`(게이팅+dedup
  +저장). 같은 사건은 대표 1건만 채점해 그룹 전체에 전파(중복 배제).

**중복 제거**(src/filters/postprocess.py): 유사 제목 그룹화 + 한국 금융은 조직명 정규화·날짜
게이팅으로 전이적(connected-components) 묶음, 영어는 Jaccard 유사도. `prune_duplicates`로
같은 사건 최고점수 1건만 물리 보존.

---

## 저장소 — 로컬/클라우드 동일 코드 (src/storage.py)

`Storage`는 환경변수로 드라이버를 자동 분기한다 (SQL·`?` 플레이스홀더 동일):

- **`TURSO_DATABASE_URL`이 있으면** → Turso(libSQL) HTTP API (`src/turso_http.py`, 순수 httpx).
  로컬 `.env` 또는 Vercel 환경변수로 주입. `is_remote = True`.
- **없으면** → 로컬 `data/news.db` (sqlite3). `is_remote = False`.

→ 로컬 배치·로컬 서버·Vercel이 **같은 Turso DB 한 곳**을 공유한다.

테이블: `news_items`, `send_history`, `feedback`.

---

## API 엔드포인트 (src/api/app.py)

| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | `/` | 대시보드(index.html) |
| GET | `/api/news` | 뉴스 목록(`?category`, `?min_score`, `?days`, `?collapse`) |
| GET | `/api/alerts` | 중요뉴스(send_recommended=true) |
| GET | `/api/config` | 설정 + `is_remote`(원격이면 프론트가 수집 버튼 숨김) |
| GET | `/api/status` | **마지막 수집 시각**(`last_collected_at`) + 전체 건수 |
| GET | `/api/history` | 발송 이력 |
| GET/POST | `/api/feedback` | 기사별 평가(FP/FN/good) — Turso `feedback`에 저장 |
| POST | `/api/collect` | 수집 실행(**로컬만**, 클라우드는 비활성) |
| POST | `/api/send` | 발송(채널 플러그인) |

대시보드 4뷰(탭): **개요 / 중요뉴스 / 전체뉴스 / 카테고리별** (ARIA tablist + 해시 라우팅).

---

## 로컬 실행

```bash
# 1) 가상환경 + 의존성 (Python 3.12)
python -m venv .venv
.venv\Scripts\activate           # Windows  (mac/Linux: source .venv/bin/activate)
pip install -r requirements-dev.txt

# 2) (선택) Turso 공유 DB를 쓰려면 .env 작성 — 없으면 로컬 data/news.db 사용
#    .env (gitignore됨):
#    TURSO_DATABASE_URL=libsql://<your-db>.turso.io
#    TURSO_AUTH_TOKEN=<db-token>

# 3) 서버 실행 → http://127.0.0.1:8000
python run.py

# 4) 테스트
pytest -q
```

수집·채점은 보통 배치/cron로 돌린다(아래). 로컬 서버의 "수집 실행" 버튼으로도 가능
(단, 실시간 채점은 API 키 필요. 키가 없으면 배치 채점 스킬 사용).

---

## 배포 (Vercel + Turso)

- **GitHub**: `kjw1oo/news_curating` → Vercel이 빌드.
- **Vercel**: `vercel.json`이 `api/index.py`(`@vercel/python`)를 ASGI로 서빙.
  프로젝트 환경변수에 `TURSO_DATABASE_URL`·`TURSO_AUTH_TOKEN` 설정(**코드에 비밀키 금지**).
- **클라우드는 표시 전용**: 수집·채점은 못 하므로(서버리스 시간제한·API키 부재)
  `is_remote=True`일 때 프론트가 수집 버튼을 숨기고 "마지막 수집 시각"을 보여준다.

```bash
# CLI 배포(예)
vercel deploy --prod --scope <team> --token <vercel-token>
```

---

## 자동화 & 데이터 갱신

- **사이트(Vercel+Turso)는 PC와 무관하게 24/7** 유지된다.
- **수집·채점 배치**는 이 PC에서 돈다(예: 08·13·17시). 배치가 Turso를 갱신하면 대시보드는
  **재배포 없이 자동 반영**된다(런타임에 Turso를 직접 조회).
- PC를 끄거나 배치를 안 돌리면 새 뉴스가 안 들어오고 화면은 "마지막 수집" 시점에서 멈춘다.
- 완전 무인 자동화(PC 무관)를 원하면 채점에 API 키를 붙여 클라우드 cron(GitHub Actions 등)으로
  옮기면 된다.

---

## 개발 하네스 (.claude/)

이 저장소는 Claude Code **에이전트 팀**으로 개발한다(설계→병렬 구현→점진 QA).

- **에이전트**: architect, collector-dev, filter-dev, dashboard-dev, web-designer,
  design-reviewer, qa-inspector, source-researcher, threshold-tuner
- **스킬**: `news-monitoring-orchestrator`(라우팅), `news-pipeline-run`(수집→채점→저장
  전 사이클), `news-batch-scoring`(키 없는 배치 채점), 그 외 도메인별 스킬
- **피드백 루프**: 대시보드의 기사별 평가(FP/FN/good) → `feedback` 테이블 →
  `threshold-tuner`가 임계값·프롬프트 조정안 제안(운영자 승인 후 반영)

---

## 설정 한 곳 (config.yaml)

소스 추가·임계값·키워드·발송 채널·우리금융 엔티티·표시 창 등 **운영 파라미터는 전부
`config.yaml`**에서. 새 RSS/토스 소스 추가 = `sources`에 항목 1개 추가(코드 변경 없음).
