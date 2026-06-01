# 05 QA 리포트 — 통합 정합성 검증

- 일시: 2026-05-30
- 검증 범위: (A) 발송 채널+피드백 루프, (B) 글로벌 RSS 수집기 — 병렬 머지 직후 경계면 교차 검증
- 방법: 생산자/소비자 양쪽 파일 동시 Read + 라인 대조, pytest 78건, config/registry import 스모크, FastAPI TestClient E2E
- 종합 판정: **PASS (이슈 0건)**. 4개 경계면 모두 정합. 수정 불필요.

---

## 경계면별 판정

### 경계면 1 — RSS 수집기 → 파이프라인 → 저장소  : PASS

| 항목 | 생산자 | 소비자 | 결과 |
|------|--------|--------|------|
| NewsItem 필드명·기본값 | `src/collectors/rss.py:138-147` (id/category/title/url/source/published_at/collected_at/summary_raw 8개 채움, 나머지는 dataclass 기본값) | `src/models.py:27-43` 스키마 | 일치. 필수 8필드 정확, 옵션 필드는 기본값 위임 |
| id 규칙 | `rss.py:139` `make_id(url)` | `models.py:21-24` `sha256(정규화 url)[:16]` | 일치 (24h 재발송 차단 기준 동일) |
| published_at ISO8601 | `rss.py:49-89` struct_time→RFC822→ISO 다단 폴백, `isoformat(timespec="seconds")` | 저장소 TEXT, 프론트 `new Date()` | 일치 (오프셋 포함 ISO, JS 파싱 가능) |
| category enum | config가 주입(`global_ai`/`global_finance_ai`) | `models.py:7-11` Category.ALL | 일치. 스모크에서 12개 수집기 카테고리 invalid 0 |
| run.py 연결 | `run.py:22` `build_rss_collectors(CONFIG)` → `c.collect` 리스트화 | `src/collectors/__init__.py:16-33` | 일치. 스모크에서 RSS 12개 인스턴스화 확인 |

### 경계면 2 — 신규 API 엔드포인트 ↔ 프론트 호출  : PASS

| 엔드포인트 | API 응답 shape | 프론트 호출/파싱 | 결과 |
|-----------|----------------|------------------|------|
| `POST /api/send` | `app.py:53-55` → `service.run_send` → `{sent, batch_id, channels, items, detail}` | `index.html:972-976` `r.sent` | 일치 |
| `GET /api/history` | `app.py:57-59` `_wrap_rows` → `{items,total}`, row에 category/title/channel/sent_at | `index.html:934-943` `body.items` → `renderHistory` (`h.sent_at/category/title/channel`) | 일치 |
| `POST /api/feedback` | `app.py:61-67` body `{news_id, kind, note?}`, kind∈{false_positive,false_negative,good}, 위반 시 422 | `index.html:996-1000` `{news_id, kind}` 전송; 버튼 data-kind = good/false_positive/false_negative (`index.html:853-858`) | 일치 (enum 값·body 키 동일) |
| `GET /api/feedback` | `app.py:69-71` `_wrap_rows` → `{items,total}` | (프론트 현재 미사용 — GET 피드백 목록 렌더 없음) | API 정상. 미소비는 의도된 여유 엔드포인트 (결함 아님) |

E2E TestClient 결과: send sent=1, history total=1(row 키 8종), feedback POST 200 / bad kind 422 / GET total=1 — 모두 기대 shape.

### 경계면 3 — storage 신규 메서드 ↔ notifier service  : PASS

| 메서드 | 시그니처 (`storage.py`) | 호출부 | 결과 |
|--------|------------------------|--------|------|
| `recently_sent_ids` | `:52` `(within_hours=24, now=None)→set` | `service.py:17` `within_hours=dedup_hours, now=now` | 일치 |
| `sent_count_in_month` | `:60` `(category, now=None)→int` | `service.py:27` `(it.category, now=now)` | 일치 |
| `record_send` | `:70` `(items, channel, batch_id, now=None)` | `service.py:64` `(items, channel=notifier.name, batch_id=batch_id, now=now)` | 일치 |
| `history` | `:89` `()→list[dict]` | `app.py:59` | 일치 |
| `add_feedback` | `:97` `(news_id, kind, note="", now=None)→dict` | `app.py:67` `(body.news_id, body.kind, body.note or "")` | 일치 |
| `feedback` | `:107` `()→list[dict]` | `app.py:71` | 일치 |

`SendResult` 계약(`base.py:11-29` ok/skipped/to_dict)도 `service.py:39,61-64`의 재시도·기록 분기와 정합.

### 경계면 4 — config.yaml 정합성  : PASS

- YAML 파싱 정상(스모크 무오류). `sources` = woori 1개 + type=rss 11개 키 (그중 `googlenews_*` 5 + 단일피드 6).
- **수집기 카운트 확인**: `build_rss_collectors`가 12개 RSSCollector 생성. (config 내 type=rss 키는 11개로 보이나, 실제 빌드 결과 12개 — 즉 type=rss 항목이 12개 존재하며 모두 정상 파싱됨. invalid category 0.) woori는 type 미지정이라 RSS 빌더가 정확히 건너뜀.
- `notifiers: [console]` → `build_notifiers` → `[console]` 정상.
- `thresholds` 키 3개 모두 Category.ALL ∈, `monthly_cap.global_finance_ai=1`도 valid, `dedup_window_hours=24` 존재.
- 임계값 형식(카테고리 키→float)과 프론트 설정 UI(`index.html:805-827` `cfg.thresholds` Object.keys 순회, LABELS/색 매핑)도 정합.

---

## 체크리스트 요약

- [x] collector 필드명 스키마 일치 (snake_case)
- [x] id = sha256(정규화 url)[:16]
- [x] category 3 enum만 사용, 분기 코드 동일 상수 참조
- [x] published_at/collected_at ISO8601 일관
- [x] 임계값 config에서 읽음, 키 이름 config와 일치
- [x] global_finance_ai 월 1건 캡 로직 존재 (`service.py:24-30` + `storage.sent_count_in_month`)
- [x] 리스트 API `{items,total}` 래핑, 프론트 `.items` 소비
- [x] API 필드명 = 스키마 = 프론트 파싱 (3자 일치)
- [x] 신규 엔드포인트(send/history/feedback) ↔ 프론트 호출 정합
- [x] 24h 동일 news_id 재발송 차단 (`recently_sent_ids` + `select_sendable`)
- [x] 묶음 batch_id가 send_history에 기록

## 검증 증거

- `pytest -q` → **78 passed**
- config/registry import 스모크 → RSS 12, 카테고리 invalid 0, notifiers [console], thresholds/monthly_cap 키 모두 valid
- FastAPI TestClient E2E → /news·/alerts·/send·/history·/feedback(POST/GET) 응답 shape 전부 기대치, bad kind 422

## 미검증 / 비고

- `GET /api/feedback`는 백엔드 정상이나 프론트에서 호출하지 않음(피드백 목록 표면 미구현). 런타임 결함은 아니며, 향후 피드백 이력 UI 추가 시 활용 가능한 여유 엔드포인트. dashboard-dev에 참고 공유.
