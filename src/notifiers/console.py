"""콘솔/로그 기본 채널 — 항상 동작한다.

대시보드 자체가 1차 알림 표면이므로, 발송 기록(send_history)은 storage가 담당하고
이 채널은 운영자가 터미널에서 확인할 수 있도록 메시지를 출력한다.
"""
import logging
from src.models import LABELS
from src.notifiers.base import Notifier, SendResult, compose_message

_log = logging.getLogger("notifier.console")


class ConsoleNotifier(Notifier):
    name = "console"

    def __init__(self, sink=None, labels: dict | None = None):
        # sink: 테스트 주입용 콜러블(message:str)->None. 기본은 logging.
        self._sink = sink
        self._labels = labels if labels is not None else LABELS

    def _emit(self, message: str) -> None:
        if self._sink is not None:
            self._sink(message)
        else:
            _log.info("알림 발송\n%s", message)

    def send(self, items, batch_id) -> SendResult:
        if not items:
            return SendResult(channel=self.name, ok=True, sent_count=0,
                              detail="발송 대상 없음")
        try:
            self._emit(compose_message(items, self._labels))
        except Exception as e:  # noqa: BLE001 — 채널 실패는 예외 대신 결과로 보고
            return SendResult(channel=self.name, ok=False, error=str(e))
        return SendResult(channel=self.name, ok=True, sent_count=len(items),
                          detail=f"batch={batch_id}")
