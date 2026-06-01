"""발송 오케스트레이션 — 이벤트 기반.

대상 선정: send_recommended=True AND sent=0 AND 최근 24h 미발송 AND 월 캡 미초과.
묶음: 단일 batch_id로 한 번에 발송(데모는 즉시 발송 — 윈도우 누적 없이 후보 전체를 1배치로).
재시도: 채널 실패 시 1회 재시도. 재실패 시 실패 상태로 결과에 기록(발송 기록 안 함).
"""
import uuid
from datetime import datetime, timezone
from src.notifiers.registry import build_notifiers


def select_sendable(storage, config, now=None) -> list:
    """발송 가능한 NewsItem 목록을 계약대로 선정한다."""
    now = now or datetime.now(timezone.utc)
    dedup_hours = (config or {}).get("dedup_window_hours", 24)
    recent = storage.recently_sent_ids(within_hours=dedup_hours, now=now)
    caps = (config or {}).get("monthly_cap", {}) or {}

    # 점수 높은 순으로 캡을 채운다(query는 이미 점수 내림차순).
    used = {}  # category -> 이번 발송에서 추가될 건수
    out = []
    for it in storage.query():
        if not it.send_recommended or it.sent or it.id in recent:
            continue
        cap = caps.get(it.category)
        if cap is not None:
            already = storage.sent_count_in_month(it.category, now=now)
            if already + used.get(it.category, 0) >= cap:
                continue
            used[it.category] = used.get(it.category, 0) + 1
        out.append(it)
    return out


def _send_with_retry(notifier, items, batch_id, retry_max=1):
    """1회 재시도. SendResult 반환."""
    result = notifier.send(items, batch_id)
    attempts = 1
    while not result.ok and not result.skipped and attempts <= retry_max:
        result = notifier.send(items, batch_id)
        attempts += 1
    return result


def run_send(storage, config, notifiers=None, now=None) -> dict:
    """발송 실행. 결과 요약(dict) 반환."""
    now = now or datetime.now(timezone.utc)
    items = select_sendable(storage, config, now=now)
    if not items:
        return {"sent": 0, "batch_id": None, "channels": [], "items": [],
                "detail": "발송 대상 없음"}

    notifiers = notifiers if notifiers is not None else build_notifiers(config)
    batch_id = uuid.uuid4().hex[:12]
    retry_max = (config or {}).get("retry_max", 1)

    channel_results = []
    any_delivered = False
    for notifier in notifiers:
        res = _send_with_retry(notifier, items, batch_id, retry_max=retry_max)
        channel_results.append(res.to_dict())
        # 실제 전송에 성공한 채널이 하나라도 있으면 발송 기록.
        if res.ok and not res.skipped:
            storage.record_send(items, channel=notifier.name, batch_id=batch_id, now=now)
            any_delivered = True

    return {
        "sent": len(items) if any_delivered else 0,
        "batch_id": batch_id if any_delivered else None,
        "channels": channel_results,
        "items": [it.id for it in items],
        "detail": "발송 완료" if any_delivered else "모든 채널 발송 실패/건너뜀",
    }
