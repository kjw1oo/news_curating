"""Turso(libSQL) HTTP API 클라이언트 — 순수 httpx (Rust 드라이버 불필요).

Turso의 /v2/pipeline 엔드포인트에 SQL을 POST한다. storage.py가 쓰는 sqlite3 연결의
최소 API(execute / executemany / commit, 그리고 커서의 description / fetchall /
fetchone / lastrowid)를 흉내내, Windows 로컬과 Vercel(리눅스) 양쪽에서 동일하게 동작한다.
"""
import base64
import httpx


def _clean(s) -> str:
    """BOM(U+FEFF)·앞뒤 공백 제거 — env 주입 과정에서 끼어든 BOM이 헤더/URL을 깨뜨리는 것 방지."""
    return (s or "").replace("﻿", "").strip()


def _to_http(url: str) -> str:
    u = _clean(url)
    if u.startswith("libsql://"):
        u = "https://" + u[len("libsql://"):]
    elif u.startswith("ws://"):
        u = "http://" + u[len("ws://"):]
    elif u.startswith("wss://"):
        u = "https://" + u[len("wss://"):]
    return u.rstrip("/")


def _enc_arg(v):
    if v is None:
        return {"type": "null"}
    if isinstance(v, bool):
        return {"type": "integer", "value": str(int(v))}
    if isinstance(v, int):
        return {"type": "integer", "value": str(v)}
    if isinstance(v, float):
        return {"type": "float", "value": v}
    if isinstance(v, (bytes, bytearray)):
        return {"type": "blob", "base64": base64.b64encode(bytes(v)).decode()}
    return {"type": "text", "value": str(v)}


def _dec_val(cell):
    t = cell.get("type")
    if t == "null":
        return None
    if t == "integer":
        return int(cell.get("value"))
    if t == "float":
        return float(cell.get("value"))
    if t == "blob":
        return base64.b64decode(cell.get("base64", ""))
    return cell.get("value")  # text


class _Cursor:
    """libSQL execute 결과 1건을 sqlite3 커서처럼 노출."""
    def __init__(self, result):
        self.description = None
        self._rows = []
        self.lastrowid = None
        if result:
            cols = result.get("cols") or []
            self.description = [(c.get("name"),) for c in cols] if cols else None
            self._rows = [tuple(_dec_val(c) for c in row)
                          for row in (result.get("rows") or [])]
            lir = result.get("last_insert_rowid")
            self.lastrowid = int(lir) if lir not in (None, "") else None

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


class TursoConnection:
    def __init__(self, url, token, timeout=30.0):
        token = _clean(token)
        self._url = _to_http(url) + "/v2/pipeline"
        self._headers = {"Authorization": f"Bearer {token}"} if token else {}
        self._client = httpx.Client(timeout=timeout)

    def _pipeline(self, stmts):
        """stmts: [(sql, args), ...] → 실행 결과(result dict) 리스트(execute 응답만)."""
        reqs = [{"type": "execute",
                 "stmt": {"sql": sql, "args": [_enc_arg(a) for a in (args or [])]}}
                for sql, args in stmts]
        reqs.append({"type": "close"})
        r = self._client.post(self._url, json={"requests": reqs}, headers=self._headers)
        r.raise_for_status()
        data = r.json()
        out = []
        for item in data.get("results", []):
            if item.get("type") == "error":
                raise RuntimeError("Turso SQL error: " + str(item.get("error")))
            resp = item.get("response") or {}
            if resp.get("type") == "execute":
                out.append(resp.get("result"))
        return out

    def execute(self, sql, args=()):
        results = self._pipeline([(sql, tuple(args) if args else ())])
        return _Cursor(results[0] if results else None)

    def executemany(self, sql, seq_of_args):
        seq = list(seq_of_args)
        if seq:
            self._pipeline([(sql, tuple(a)) for a in seq])
        return _Cursor(None)

    def commit(self):
        pass  # 각 /v2/pipeline 호출이 즉시 커밋됨

    def close(self):
        self._client.close()


def connect(url, token):
    return TursoConnection(url, token)
