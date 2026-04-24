from __future__ import annotations

import threading
from typing import Any
from dataclasses import dataclass
from typing import Callable, Optional

from .errors import BiliRewardCancelledError


@dataclass(slots=True)
class AwardInfo:
    act_id: str
    act_name: str
    task_name: str
    award_name: str


@dataclass(slots=True)
class ClaimOptions:
    task_id: str
    thread_count: int = 2
    max_retry: int = 120
    retry_interval: float = 1.0
    timeout: float = 10.0


@dataclass(slots=True)
class ClaimResult:
    award_info: AwardInfo
    cdkey: str


@dataclass(slots=True)
class LinkTaskItem:
    index: int
    task_url: str
    task_id: str


@dataclass(slots=True)
class PreparedLinkTask:
    index: int
    task_url: str
    task_id: str
    options: "ClaimOptions"
    client: Any
    award_info: AwardInfo
    logger: Any


@dataclass(slots=True)
class SingleLinkClaimResult:
    index: int
    task_id: str
    status: str
    cdkey: str | None = None
    error: str | None = None


@dataclass(slots=True)
class BatchClaimResult:
    results: list[SingleLinkClaimResult]


@dataclass(slots=True)
class QrCodeData:
    login_url: str
    qrcode_key: str
    image_bytes: bytes


@dataclass(slots=True)
class RuntimePaths:
    data_dir: str
    logs_dir: str
    cookie_file: str
    log_file: str


class ClaimExecutionControl:
    def __init__(self) -> None:
        self._cancel_event = threading.Event()
        self._resume_event = threading.Event()
        self._resume_event.set()

    def pause(self) -> bool:
        if self._cancel_event.is_set() or not self._resume_event.is_set():
            return False
        self._resume_event.clear()
        return True

    def resume(self) -> bool:
        if self._cancel_event.is_set() or self._resume_event.is_set():
            return False
        self._resume_event.set()
        return True

    def cancel(self) -> bool:
        already_cancelled = self._cancel_event.is_set()
        self._cancel_event.set()
        self._resume_event.set()
        return not already_cancelled

    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def is_paused(self) -> bool:
        return not self._resume_event.is_set() and not self._cancel_event.is_set()

    def wait_if_paused(self, poll_interval: float = 0.1) -> None:
        while self.is_paused():
            self.check_cancelled()
            self._resume_event.wait(timeout=poll_interval)
        self.check_cancelled()

    def check_cancelled(self) -> None:
        if self._cancel_event.is_set():
            raise BiliRewardCancelledError("[任务] 已取消抢奖")


LogCallback = Callable[[str], None]
QrCodeCallback = Callable[[QrCodeData], None]
CancelCheck = Callable[[], bool]

OptionalLogCallback = Optional[LogCallback]
OptionalQrCodeCallback = Optional[QrCodeCallback]
OptionalCancelCheck = Optional[CancelCheck]
