import sqlite3
from datetime import datetime, timedelta, timezone, date
from pathlib import Path
from src.models import NewsItem

_FIELDS = list(NewsItem.__dataclass_fields__)


def _within_days(published_at: str, days: int, today: date) -> bool:
    """발행일이 최근 `days`일 이내인가(달력일 기준). 날짜 불명/미래는 숨기지 않음."""
    if not published_at:
        return True
    try:
        d = date.fromisoformat(published_at[:10])
    except ValueError:
        return True
    return (today - d).days <= days

_SCHEMA = """
CREATE TABLE IF NOT EXISTS news_items (
  id TEXT PRIMARY KEY, category TEXT, title TEXT, url TEXT, source TEXT,
  published_at TEXT, collected_at TEXT, summary_raw TEXT,
  keyword_passed INTEGER DEFAULT 0, importance_score REAL, importance_reason TEXT,
  send_recommended INTEGER DEFAULT 0, dedup_group TEXT,
  sent INTEGER DEFAULT 0, sent_at TEXT
);
CREATE TABLE IF NOT EXISTS send_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT, news_id TEXT, category TEXT, title TEXT,
  channel TEXT, sent_at TEXT, batch_id TEXT
);
CREATE TABLE IF NOT EXISTS feedback (
  id INTEGER PRIMARY KEY AUTOINCREMENT, news_id TEXT, kind TEXT, note TEXT, created_at TEXT
);
"""


class Storage:
    def __init__(self, db_path):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(_SCHEMA)
        self.conn.commit()

    def upsert(self, items: list[NewsItem]) -> None:
        rows = [tuple(self._encode(getattr(it, f)) for f in _FIELDS) for it in items]
        placeholders = ",".join("?" * len(_FIELDS))
        cols = ",".join(_FIELDS)
        self.conn.executemany(
            f"INSERT OR REPLACE INTO news_items ({cols}) VALUES ({placeholders})", rows)
        self.conn.commit()

    def query(self, category=None, min_score=None, max_age_days=None,
              today=None) -> list[NewsItem]:
        sql, args = "SELECT * FROM news_items WHERE 1=1", []
        if category:
            sql += " AND category=?"; args.append(category)
        if min_score is not None:
            sql += " AND importance_score >= ?"; args.append(min_score)
        sql += " ORDER BY importance_score DESC NULLS LAST, collected_at DESC"
        items = [self._row_to_item(r) for r in self.conn.execute(sql, args)]
        # 표시 창 제한: 최근 max_age_days일 이내만(<=0 또는 None이면 전체).
        if max_age_days is not None and max_age_days > 0:
            t = today or date.today()
            items = [it for it in items if _within_days(it.published_at, max_age_days, t)]
        return items

    def delete(self, ids) -> int:
        """주어진 id 항목을 물리 삭제(중복 뉴스 제거용). 삭제 건수 반환."""
        ids = list(ids)
        if not ids:
            return 0
        self.conn.executemany("DELETE FROM news_items WHERE id=?", [(i,) for i in ids])
        self.conn.commit()
        return len(ids)

    def unscored(self) -> list[NewsItem]:
        """아직 중요도 점수가 없는(importance_score IS NULL) 항목 — 배치 채점 대상."""
        rows = self.conn.execute(
            "SELECT * FROM news_items WHERE importance_score IS NULL"
            " ORDER BY collected_at DESC")
        return [self._row_to_item(r) for r in rows]

    # ─── 발송 이력 ──────────────────────────────────────────
    def recently_sent_ids(self, within_hours: int = 24, now=None) -> set[str]:
        """최근 within_hours 내 send_history에 기록된 news_id 집합(24h 재발송 차단용)."""
        now = now or datetime.now(timezone.utc)
        cutoff = (now - timedelta(hours=within_hours)).isoformat()
        rows = self.conn.execute(
            "SELECT DISTINCT news_id FROM send_history WHERE sent_at >= ?", (cutoff,))
        return {r["news_id"] for r in rows}

    def sent_count_in_month(self, category: str, now=None) -> int:
        """이번 달(UTC) 해당 카테고리의 발송 건수(월 캡 판정용)."""
        now = now or datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0,
                                  microsecond=0).isoformat()
        row = self.conn.execute(
            "SELECT COUNT(*) AS c FROM send_history WHERE category=? AND sent_at >= ?",
            (category, month_start)).fetchone()
        return int(row["c"])

    def record_send(self, items: list[NewsItem], channel: str, batch_id: str,
                    now=None) -> list[dict]:
        """send_history에 기록하고 news_items의 sent=1, sent_at을 갱신한다."""
        now = now or datetime.now(timezone.utc)
        sent_at = now.isoformat()
        recorded = []
        for it in items:
            self.conn.execute(
                "INSERT INTO send_history (news_id, category, title, channel, sent_at, batch_id)"
                " VALUES (?,?,?,?,?,?)",
                (it.id, it.category, it.title, channel, sent_at, batch_id))
            self.conn.execute(
                "UPDATE news_items SET sent=1, sent_at=? WHERE id=?", (sent_at, it.id))
            recorded.append({"news_id": it.id, "category": it.category,
                             "title": it.title, "channel": channel,
                             "sent_at": sent_at, "batch_id": batch_id})
        self.conn.commit()
        return recorded

    def history(self) -> list[dict]:
        """발송 이력(최신순)."""
        rows = self.conn.execute(
            "SELECT id, news_id, category, title, channel, sent_at, batch_id"
            " FROM send_history ORDER BY sent_at DESC, id DESC")
        return [dict(r) for r in rows]

    # ─── 피드백 ────────────────────────────────────────────
    def add_feedback(self, news_id: str, kind: str, note: str = "", now=None) -> dict:
        now = now or datetime.now(timezone.utc)
        created_at = now.isoformat()
        cur = self.conn.execute(
            "INSERT INTO feedback (news_id, kind, note, created_at) VALUES (?,?,?,?)",
            (news_id, kind, note or "", created_at))
        self.conn.commit()
        return {"id": cur.lastrowid, "news_id": news_id, "kind": kind,
                "note": note or "", "created_at": created_at}

    def feedback(self) -> list[dict]:
        rows = self.conn.execute(
            "SELECT id, news_id, kind, note, created_at"
            " FROM feedback ORDER BY created_at DESC, id DESC")
        return [dict(r) for r in rows]

    @staticmethod
    def _encode(v):
        return int(v) if isinstance(v, bool) else v

    @staticmethod
    def _row_to_item(r: sqlite3.Row) -> NewsItem:
        d = dict(r)
        for b in ("keyword_passed", "send_recommended", "sent"):
            d[b] = bool(d[b])
        return NewsItem.from_dict(d)
