from datetime import datetime, timezone
from src.models import NewsItem, Category, make_id, LABELS
from src.storage import Storage
from src.notifiers.base import SendResult, compose_message, Notifier
from src.notifiers.console import ConsoleNotifier
from src.notifiers.email import EmailNotifier
from src.notifiers.registry import build_notifiers
from src.notifiers.service import select_sendable, run_send


def _item(url, cat=Category.DOMESTIC_FINANCE_AI, score=6.0, rec=True):
    return NewsItem(
        id=make_id(url), category=cat, title=f"제목 {url}", url=url, source="토스",
        published_at="2026-05-29T00:00:00+09:00", collected_at="",
        summary_raw="이것은 요약 본문입니다.", importance_score=score,
        importance_reason="중요한 이유", send_recommended=rec)


# ─── 메시지 구성 (요구사항 5.3) ─────────────────────────────
def test_compose_message_contains_required_elements():
    it = _item("https://t.com/1")
    msg = compose_message([it], LABELS)
    assert "국내 금융 AI" in msg          # 카테고리 레이블
    assert it.title in msg                # 제목
    assert "요약" in msg                  # AI 요약
    assert "중요한 이유" in msg            # 판단 근거
    assert it.url in msg                  # 원문 링크
    assert "토스" in msg                  # 출처


def test_compose_message_batch_lists_count():
    msg = compose_message([_item("https://t.com/1"), _item("https://t.com/2")], LABELS)
    assert "총 2건" in msg


# ─── 콘솔 채널 ─────────────────────────────────────────────
def test_console_notifier_emits_to_sink():
    captured = []
    n = ConsoleNotifier(sink=captured.append)
    res = n.send([_item("https://t.com/1")], batch_id="b1")
    assert res.ok and res.sent_count == 1
    assert len(captured) == 1 and "국내 금융 AI" in captured[0]


def test_console_notifier_empty_is_ok():
    res = ConsoleNotifier(sink=lambda m: None).send([], batch_id="b1")
    assert res.ok and res.sent_count == 0


# ─── 이메일 채널 (실제 SMTP 호출 금지 — graceful skip / fake transport) ─
def test_email_notifier_skips_without_settings(monkeypatch):
    for v in ("SMTP_HOST", "SMTP_PORT", "SMTP_USERNAME", "SMTP_PASSWORD",
              "SMTP_FROM", "SMTP_TO"):
        monkeypatch.delenv(v, raising=False)
    res = EmailNotifier(settings=None).send([_item("https://t.com/1")], batch_id="b1")
    assert res.ok and res.skipped is True and res.sent_count == 0


def test_email_notifier_uses_injected_transport():
    sent = {}
    def fake_transport(cfg, subject, body):
        sent["subject"] = subject
        sent["body"] = body
        sent["to"] = cfg["to_addrs"]
    settings = {"host": "smtp.test", "port": 587, "username": "u",
                "password": "p", "from_addr": "a@b.c", "to_addrs": ["x@y.z"]}
    n = EmailNotifier(settings=settings, transport=fake_transport)
    res = n.send([_item("https://t.com/1")], batch_id="b1")
    assert res.ok and not res.skipped and res.sent_count == 1
    assert "국내 금융 AI" in sent["subject"]
    assert "중요한 이유" in sent["body"]


def test_email_notifier_transport_failure_reports_error():
    def boom(cfg, subject, body):
        raise RuntimeError("smtp down")
    settings = {"host": "h", "port": 1, "username": "u", "password": "p",
                "from_addr": "a@b.c", "to_addrs": ["x@y.z"]}
    res = EmailNotifier(settings=settings, transport=boom).send(
        [_item("https://t.com/1")], batch_id="b1")
    assert res.ok is False and "smtp down" in (res.error or "")


# ─── 레지스트리 ─────────────────────────────────────────────
def test_registry_defaults_to_console():
    ns = build_notifiers({})
    assert len(ns) == 1 and ns[0].name == "console"


def test_registry_builds_email_when_listed():
    ns = build_notifiers({"notifiers": ["console", "email"]})
    names = {n.name for n in ns}
    assert names == {"console", "email"}


# ─── 발송 서비스: 선정·캡·24h·재시도 ─────────────────────────
def _now():
    return datetime(2026, 5, 30, 12, 0, 0, tzinfo=timezone.utc)


def test_select_only_recommended_unsent(tmp_path):
    st = Storage(tmp_path / "s.db")
    st.upsert([
        _item("https://t.com/1", rec=True),
        _item("https://t.com/2", rec=False),
        NewsItem(id=make_id("https://t.com/3"), category=Category.GLOBAL_AI,
                 title="t", url="https://t.com/3", source="s",
                 published_at="2026-05-29T00:00:00+09:00", collected_at="",
                 summary_raw="s", importance_score=9.0, send_recommended=True, sent=True),
    ])
    sel = select_sendable(st, {}, now=_now())
    assert [i.url for i in sel] == ["https://t.com/1"]


def test_select_respects_24h_resend_block(tmp_path):
    st = Storage(tmp_path / "s.db")
    it = _item("https://t.com/1")
    st.upsert([it])
    st.record_send([it], channel="console", batch_id="b0", now=_now())
    # 발송 직후엔 후보에서 빠진다.
    assert select_sendable(st, {}, now=_now()) == []


def test_select_respects_monthly_cap(tmp_path):
    st = Storage(tmp_path / "s.db")
    st.upsert([
        _item("https://t.com/1", cat=Category.GLOBAL_FINANCE_AI, score=9.0),
        _item("https://t.com/2", cat=Category.GLOBAL_FINANCE_AI, score=8.0),
    ])
    cfg = {"monthly_cap": {"global_finance_ai": 1}}
    sel = select_sendable(st, cfg, now=_now())
    assert len(sel) == 1  # 캡 1 → 점수 높은 1건만


def test_run_send_records_history_and_marks_sent(tmp_path):
    st = Storage(tmp_path / "s.db")
    st.upsert([_item("https://t.com/1")])
    captured = []
    res = run_send(st, {}, notifiers=[ConsoleNotifier(sink=captured.append)], now=_now())
    assert res["sent"] == 1 and res["batch_id"]
    assert len(st.history()) == 1
    assert st.query()[0].sent is True
    assert len(captured) == 1


def test_run_send_empty_when_nothing_sendable(tmp_path):
    st = Storage(tmp_path / "s.db")
    res = run_send(st, {}, notifiers=[ConsoleNotifier(sink=lambda m: None)], now=_now())
    assert res["sent"] == 0 and res["batch_id"] is None
    assert st.history() == []


def test_run_send_retries_then_records_on_recovery(tmp_path):
    st = Storage(tmp_path / "s.db")
    st.upsert([_item("https://t.com/1")])

    class Flaky(Notifier):
        name = "flaky"
        def __init__(self):
            self.calls = 0
        def send(self, items, batch_id):
            self.calls += 1
            if self.calls == 1:
                return SendResult(channel=self.name, ok=False, error="temp")
            return SendResult(channel=self.name, ok=True, sent_count=len(items))

    flaky = Flaky()
    res = run_send(st, {"retry_max": 1}, notifiers=[flaky], now=_now())
    assert flaky.calls == 2 and res["sent"] == 1
    assert len(st.history()) == 1


def test_run_send_failure_does_not_record(tmp_path):
    st = Storage(tmp_path / "s.db")
    st.upsert([_item("https://t.com/1")])

    class Dead(Notifier):
        name = "dead"
        def send(self, items, batch_id):
            return SendResult(channel=self.name, ok=False, error="down")

    res = run_send(st, {"retry_max": 1}, notifiers=[Dead()], now=_now())
    assert res["sent"] == 0 and res["batch_id"] is None
    assert st.history() == []
    assert st.query()[0].sent is False
