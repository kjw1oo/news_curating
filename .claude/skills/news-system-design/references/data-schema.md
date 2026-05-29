# 표준 데이터 스키마 (런타임 계약)

이 문서는 collector-dev, filter-dev, dashboard-dev가 공유하는 단일 진실 공급원이다. architect는 이를 `_workspace/01_architect_schema.md`로 구체화하고, 빌드 에이전트는 그 산출물을 따른다. 필드명·타입을 임의로 바꾸면 경계면 버그가 발생한다.

## 목차
1. 카테고리 enum
2. NewsItem 스키마
3. config.yaml 형식
4. DB 테이블 (DDL)
5. 모듈 인터페이스

---

## 1. 카테고리 enum

문자열 상수로 관리한다. 오타 방지를 위해 코드에서는 상수를 참조한다.

```python
class Category:
    GLOBAL_AI = "global_ai"                      # 글로벌 AI 뉴스 (빅테크)
    GLOBAL_FINANCE_AI = "global_finance_ai"      # 글로벌 금융사 AI 도입
    DOMESTIC_FINANCE_AI = "domestic_finance_ai"  # 국내 금융지주 AI/데이터
```

대시보드 표시 레이블: global_ai="글로벌 AI", global_finance_ai="글로벌 금융 AI", domestic_finance_ai="국내 금융 AI".

## 2. NewsItem 스키마

수집→필터→발송을 거치며 필드가 점진적으로 채워진다. snake_case로 통일한다.

```python
@dataclass
class NewsItem:
    # --- collector가 채움 ---
    id: str               # sha256(url)[:16] — 중복 제거 키. 예: "a1b2c3d4e5f6a7b8"
    category: str         # Category enum 값
    title: str            # 원문 제목
    url: str              # 원문 링크
    source: str           # 매체명. 예: "TechCrunch", "토스인베스트"
    published_at: str     # ISO 8601. 예: "2026-05-29T08:30:00+09:00"
    collected_at: str     # ISO 8601 수집 시각
    summary_raw: str      # 원문 요약 또는 본문 일부 (LLM 입력용)

    # --- filter가 채움 (collector 단계에서는 기본값) ---
    keyword_passed: bool = False      # 1단계 키워드 필터 통과 여부
    importance_score: float | None = None   # 0.0~10.0, 소수점 1자리
    importance_reason: str = ""       # 판단 근거 1~2문장 (알림에 그대로 사용)
    send_recommended: bool = False    # LLM의 발송 권고 (Yes/No)
    dedup_group: str | None = None    # 동일 이벤트 그룹 키 (대표 1건만 발송)

    # --- 발송 단계에서 채움 ---
    sent: bool = False
    sent_at: str | None = None
```

**id 생성 규칙**: `hashlib.sha256(url.encode()).hexdigest()[:16]`. URL이 동일하면 같은 id → 24시간 재발송 차단의 기준.

**래핑 규칙**: API가 리스트를 반환할 때는 `{"items": [...], "total": N}` 형태로 래핑한다. 프론트는 `.items`를 꺼내 쓴다 (이 계약을 어기면 `filter is not a function` 류 버그 발생).

## 3. config.yaml 형식

운영자가 조정하는 설정. filter와 dashboard 설정 UI가 동일한 키를 읽는다.

```yaml
thresholds:           # 카테고리별 발송 임계값 (이 점수 이상이면 발송 후보)
  global_ai: 8.5
  global_finance_ai: 7.0
  domestic_finance_ai: 4.0
monthly_cap:          # 월 최대 발송 건수 (없으면 무제한)
  global_finance_ai: 1
collect_interval_hours: 6
dedup_window_hours: 24      # 동일 id 재발송 차단 윈도우
batch_window_minutes: 90    # 묶음 발송 윈도우
keyword_filters:            # 1단계 키워드
  - AI
  - 인공지능
  - LLM
  - 머신러닝
  - 데이터
retry_max: 3
notifiers:
  - dashboard         # 기본 (1차 표면)
  # - email           # 확장 스텁
```

## 4. DB 테이블 (SQLite)

```sql
CREATE TABLE news_items (
  id TEXT PRIMARY KEY,
  category TEXT NOT NULL,
  title TEXT NOT NULL,
  url TEXT NOT NULL,
  source TEXT,
  published_at TEXT,
  collected_at TEXT,
  summary_raw TEXT,
  keyword_passed INTEGER DEFAULT 0,
  importance_score REAL,
  importance_reason TEXT,
  send_recommended INTEGER DEFAULT 0,
  dedup_group TEXT,
  sent INTEGER DEFAULT 0,
  sent_at TEXT
);

CREATE TABLE send_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  news_id TEXT REFERENCES news_items(id),
  category TEXT,
  title TEXT,
  channel TEXT,            -- "dashboard" | "email" ...
  sent_at TEXT,
  batch_id TEXT            -- 묶음 발송 식별
);

CREATE TABLE feedback (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  news_id TEXT REFERENCES news_items(id),
  kind TEXT,               -- "false_positive" | "false_negative"
  note TEXT,
  created_at TEXT
);
```

로그·DB는 최소 30일 보관 (요구사항 6.2).

## 5. 모듈 인터페이스

```python
# collectors/base.py
class Collector:
    category: str
    def collect(self) -> list[NewsItem]: ...   # 정규화된 NewsItem 반환

# filters
def keyword_filter(items: list[NewsItem], keywords: list[str]) -> list[NewsItem]
def score(items: list[NewsItem]) -> list[NewsItem]      # importance_* 채움
def apply_threshold(items: list[NewsItem], cfg) -> list[NewsItem]  # send_recommended 확정
def dedup(items: list[NewsItem]) -> list[NewsItem]       # dedup_group 설정

# notifiers/base.py
class Notifier:
    def send(self, items: list[NewsItem], batch_id: str) -> bool: ...
```

이 시그니처가 collector→filter→notifier 파이프라인의 계약이다.
