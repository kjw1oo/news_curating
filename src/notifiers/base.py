"""플러그인형 알림 채널 인터페이스.

새 채널 추가 = Notifier 서브클래스 1개 구현 + config의 notifiers 목록에 이름 등록.
send()는 발송 가능한(이미 묶인) NewsItem 리스트를 받아 SendResult를 반환한다.
실패 시 예외를 던지지 말고 SendResult(ok=False, ...)로 보고한다(상위에서 재시도 판단).
"""
from dataclasses import dataclass, field
from src.models import NewsItem


@dataclass
class SendResult:
    """단일 채널 발송 시도 결과."""
    channel: str
    ok: bool
    sent_count: int = 0
    skipped: bool = False          # 설정 미비 등으로 graceful skip한 경우
    error: str | None = None
    detail: str = ""

    def to_dict(self) -> dict:
        return {
            "channel": self.channel,
            "ok": self.ok,
            "sent_count": self.sent_count,
            "skipped": self.skipped,
            "error": self.error,
            "detail": self.detail,
        }


class Notifier:
    """알림 채널 인터페이스. name은 config notifiers 목록과 매칭되는 키."""
    name: str = "base"

    def send(self, items: list[NewsItem], batch_id: str) -> SendResult:
        raise NotImplementedError


def compose_message(items: list[NewsItem], labels: dict) -> str:
    """요구사항 5.3 필수 요소를 담은 알림 본문을 구성한다.

    제목 형식: [카테고리명] 뉴스 알림 — {주요 키워드}
    묶음 발송 시 건별 요약을 순서대로 나열 + 총 건수 명시.
    """
    if not items:
        return "(발송 대상 없음)"

    first = items[0]
    cat_label = labels.get(first.category, first.category)
    headline_kw = (first.title or "").strip()[:40]
    lines = [f"[{cat_label}] 뉴스 알림 — {headline_kw}"]
    if len(items) > 1:
        lines.append(f"총 {len(items)}건")
    lines.append("")

    for idx, it in enumerate(items, 1):
        label = labels.get(it.category, it.category)
        summary = (it.summary_raw or "").strip()
        if len(summary) > 280:
            summary = summary[:277] + "..."
        score = "-" if it.importance_score is None else f"{it.importance_score}"
        lines.append(f"{idx}. [{label}] {it.title}")
        if summary:
            lines.append(f"   요약: {summary}")
        if it.importance_reason:
            lines.append(f"   판단 근거(점수 {score}): {it.importance_reason}")
        lines.append(f"   출처: {it.source} · {it.published_at}")
        lines.append(f"   원문: {it.url}")
        lines.append("")

    return "\n".join(lines).rstrip()
