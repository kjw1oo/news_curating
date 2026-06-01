"""SMTP 이메일 채널 — 확장 스텁.

자격증명은 config(notifier_settings.email) 또는 환경변수에서 읽는다(하드코딩 금지).
설정이 없으면 예외 없이 graceful skip(SendResult.skipped=True).
실제 SMTP 전송은 _transport 콜러블로 추상화 — 테스트는 fake를 주입한다.

필요한 설정 키(없으면 skip):
  host, port, username, password, from_addr, to_addrs(list)
환경변수 대체: SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD,
  SMTP_FROM, SMTP_TO(콤마 구분)
"""
import os
import smtplib
from email.mime.text import MIMEText
from src.models import LABELS
from src.notifiers.base import Notifier, SendResult, compose_message

_REQUIRED = ("host", "port", "username", "password", "from_addr", "to_addrs")


def _load_settings(settings: dict | None) -> dict | None:
    cfg = dict(settings or {})
    # 환경변수로 보강(설정 우선).
    env_map = {
        "host": "SMTP_HOST", "port": "SMTP_PORT", "username": "SMTP_USERNAME",
        "password": "SMTP_PASSWORD", "from_addr": "SMTP_FROM",
    }
    for key, env in env_map.items():
        if not cfg.get(key) and os.environ.get(env):
            cfg[key] = os.environ[env]
    if not cfg.get("to_addrs") and os.environ.get("SMTP_TO"):
        cfg["to_addrs"] = [a.strip() for a in os.environ["SMTP_TO"].split(",") if a.strip()]
    if isinstance(cfg.get("to_addrs"), str):
        cfg["to_addrs"] = [a.strip() for a in cfg["to_addrs"].split(",") if a.strip()]
    if all(cfg.get(k) for k in _REQUIRED):
        return cfg
    return None


def _default_transport(cfg: dict, subject: str, body: str) -> None:
    msg = MIMEText(body, _charset="utf-8")
    msg["Subject"] = subject
    msg["From"] = cfg["from_addr"]
    msg["To"] = ", ".join(cfg["to_addrs"])
    with smtplib.SMTP(cfg["host"], int(cfg["port"])) as server:
        server.starttls()
        server.login(cfg["username"], cfg["password"])
        server.sendmail(cfg["from_addr"], cfg["to_addrs"], msg.as_string())


class EmailNotifier(Notifier):
    name = "email"

    def __init__(self, settings: dict | None = None, transport=None,
                 labels: dict | None = None):
        self._settings = settings
        self._transport = transport or _default_transport
        self._labels = labels if labels is not None else LABELS

    def send(self, items, batch_id) -> SendResult:
        if not items:
            return SendResult(channel=self.name, ok=True, sent_count=0,
                              detail="발송 대상 없음")
        cfg = _load_settings(self._settings)
        if cfg is None:
            return SendResult(channel=self.name, ok=True, skipped=True,
                              detail="SMTP 설정 없음 — 발송 건너뜀")
        body = compose_message(items, self._labels)
        first = items[0]
        label = self._labels.get(first.category, first.category)
        subject = f"[{label}] 뉴스 알림 — {(first.title or '').strip()[:40]}"
        try:
            self._transport(cfg, subject, body)
        except Exception as e:  # noqa: BLE001
            return SendResult(channel=self.name, ok=False, error=str(e))
        return SendResult(channel=self.name, ok=True, sent_count=len(items),
                          detail=f"batch={batch_id}")
