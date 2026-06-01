"""config의 notifiers 목록 → Notifier 인스턴스 목록으로 해석한다.

config 예:
  notifiers: ["console", "email"]      # 기본은 ["console"]
  notifier_settings:
    email: { host: ..., port: 587, ... }
"""
from src.notifiers.console import ConsoleNotifier
from src.notifiers.email import EmailNotifier

_BUILDERS = {
    "console": lambda cfg: ConsoleNotifier(),
    "dashboard": lambda cfg: ConsoleNotifier(),  # 대시보드는 DB 기록이 본체 — 콘솔로 표면화
    "email": lambda cfg: EmailNotifier(settings=(cfg.get("notifier_settings") or {}).get("email")),
}


def build_notifiers(config: dict) -> list:
    """활성 채널 인스턴스 리스트. 알 수 없는 이름은 무시. 비면 console 1개로 폴백."""
    names = (config or {}).get("notifiers") or ["console"]
    out = []
    seen = set()
    for name in names:
        builder = _BUILDERS.get(name)
        if builder is None or name in seen:
            continue
        seen.add(name)
        out.append(builder(config or {}))
    if not out:
        out.append(ConsoleNotifier())
    return out
