from __future__ import annotations

import os
from time import strftime
from typing import Protocol

from .models import OptionalLogCallback


def format_log_line(message: str) -> str:
    timestamp = strftime("%Y-%m-%d %H:%M:%S")
    return f"[{timestamp}] {message}"


class LoggerProtocol(Protocol):
    def log(self, message: str) -> None: ...


class EventLogger:
    def __init__(self, log_file: str, log_callback: OptionalLogCallback = None) -> None:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        self.log_file = log_file
        self.log_callback = log_callback

    def log(self, message: str) -> None:
        line = format_log_line(message)
        with open(self.log_file, "a", encoding="utf-8") as file:
            file.write(line + "\n")
        if self.log_callback is not None:
            self.log_callback(line)


class ScopedLogger:
    def __init__(self, logger: LoggerProtocol, scope: str) -> None:
        self.logger = logger
        self.scope = scope

    def log(self, message: str) -> None:
        self.logger.log(f"{self.scope} {message}")
