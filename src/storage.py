import sqlite3
from pathlib import Path
from src.models import NewsItem

_FIELDS = list(NewsItem.__dataclass_fields__)

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
        self.conn = sqlite3.connect(str(db_path))
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

    def query(self, category=None, min_score=None) -> list[NewsItem]:
        sql, args = "SELECT * FROM news_items WHERE 1=1", []
        if category:
            sql += " AND category=?"; args.append(category)
        if min_score is not None:
            sql += " AND importance_score >= ?"; args.append(min_score)
        sql += " ORDER BY importance_score DESC NULLS LAST, collected_at DESC"
        return [self._row_to_item(r) for r in self.conn.execute(sql, args)]

    @staticmethod
    def _encode(v):
        return int(v) if isinstance(v, bool) else v

    @staticmethod
    def _row_to_item(r: sqlite3.Row) -> NewsItem:
        d = dict(r)
        for b in ("keyword_passed", "send_recommended", "sent"):
            d[b] = bool(d[b])
        return NewsItem.from_dict(d)
