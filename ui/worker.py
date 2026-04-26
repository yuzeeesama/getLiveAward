from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot

from core.errors import BiliRewardCancelledError, BiliRewardError
from core.logging_utils import format_log_line
from core.models import (
    BatchClaimResult,
    ClaimExecutionControl,
    LinkTaskItem,
    PreparedLinkTask,
    QrCodeData,
    SingleLinkClaimResult,
)
from core.service import RewardService


class ClaimWorker(QObject):
    finished = pyqtSignal()
    log_message = pyqtSignal(str)
    status_changed = pyqtSignal(str)
    qr_code_ready = pyqtSignal(int, object)
    link_status_changed = pyqtSignal(int, str)
    link_claim_stage_changed = pyqtSignal(int, bool)
    batch_completed = pyqtSignal(object)

    def __init__(self, service: RewardService, link_tasks: list[LinkTaskItem]) -> None:
        super().__init__()
        self.service = service
        self.link_tasks = link_tasks
        self._login_cancel_event = threading.Event()
        self._claim_controls = {
            item.index: ClaimExecutionControl()
            for item in link_tasks
        }
        self._prepared_loggers: dict[int, Any] = {}

    def cancel_login(self) -> None:
        self._login_cancel_event.set()

    def pause_claim(self, link_index: int) -> bool:
        control = self._claim_controls.get(link_index)
        if control is None:
            return False
        changed = control.pause()
        if changed:
            self._log_for_link(link_index, "[任务] 已暂停抢奖")
            self.link_status_changed.emit(link_index, "已暂停")
        return changed

    def resume_claim(self, link_index: int) -> bool:
        control = self._claim_controls.get(link_index)
        if control is None:
            return False
        changed = control.resume()
        if changed:
            self._log_for_link(link_index, "[任务] 已继续抢奖")
            self.link_status_changed.emit(link_index, "抢奖中")
        return changed

    def cancel_claim(self, link_index: int) -> bool:
        control = self._claim_controls.get(link_index)
        if control is None:
            return False
        changed = control.cancel()
        return changed

    def _is_login_cancelled(self) -> bool:
        return self._login_cancel_event.is_set()

    def _emit_batch_log(self, message: str) -> None:
        self.log_message.emit(format_log_line(f"[批次] {message}"))

    def _emit_link_log(self, link_index: int, message: str) -> None:
        self.log_message.emit(format_log_line(f"[链接{link_index + 1}] {message}"))

    def _log_for_link(self, link_index: int, message: str) -> None:
        logger = self._prepared_loggers.get(link_index)
        if logger is not None:
            logger.log(message)
        else:
            self._emit_link_log(link_index, message)

    def _prepare_link_task(self, link_task: LinkTaskItem) -> PreparedLinkTask:
        self._login_cancel_event.clear()
        self.link_status_changed.emit(link_task.index, "预处理中")
        self.link_claim_stage_changed.emit(link_task.index, False)
        self._emit_link_log(link_task.index, f"[任务] 开始处理第 {link_task.index + 1} 条链接")
        prepared = self.service.prepare_link_task(
            link_task,
            log_callback=self.log_message.emit,
            qr_callback=lambda qr_data, idx=link_task.index: self.qr_code_ready.emit(idx, qr_data),
            cancel_check=self._is_login_cancelled,
            log_scope=f"[链接{link_task.index + 1}]",
        )
        self._prepared_loggers[link_task.index] = prepared.logger
        self.link_status_changed.emit(link_task.index, "待抢奖")
        return prepared

    def _claim_prepared_task(self, prepared_task: PreparedLinkTask) -> SingleLinkClaimResult:
        link_index = prepared_task.index
        try:
            self.link_status_changed.emit(link_index, "抢奖中")
            result = self.service.claim_prepared_task(
                prepared_task,
                claim_control=self._claim_controls[link_index],
                claim_stage_callback=lambda active, idx=link_index: self.link_claim_stage_changed.emit(idx, active),
            )
            self.link_status_changed.emit(link_index, "成功")
            return SingleLinkClaimResult(
                index=link_index,
                task_id=prepared_task.task_id,
                status="success",
                cdkey=result.cdkey,
            )
        except BiliRewardCancelledError as exc:
            self.link_status_changed.emit(link_index, "已取消")
            return SingleLinkClaimResult(
                index=link_index,
                task_id=prepared_task.task_id,
                status="cancelled",
                error=str(exc),
            )
        except BiliRewardError as exc:
            prepared_task.logger.log(f"[任务] 执行失败: {exc}")
            self.link_status_changed.emit(link_index, "失败")
            return SingleLinkClaimResult(
                index=link_index,
                task_id=prepared_task.task_id,
                status="failed",
                error=str(exc),
            )
        except Exception as exc:  # pragma: no cover
            prepared_task.logger.log(f"[任务] 执行失败: {type(exc).__name__}: {exc}")
            self.link_status_changed.emit(link_index, "失败")
            return SingleLinkClaimResult(
                index=link_index,
                task_id=prepared_task.task_id,
                status="failed",
                error=f"{type(exc).__name__}: {exc}",
            )
        finally:
            self.link_claim_stage_changed.emit(link_index, False)

    def _resolve_batch_status(self, results: list[SingleLinkClaimResult]) -> str:
        if any(result.status == "success" for result in results):
            return "成功"
        if any(result.status == "failed" for result in results):
            return "失败"
        if results and all(result.status == "cancelled" for result in results):
            return "已取消"
        return "失败"

    @pyqtSlot()
    def run(self) -> None:
        self.status_changed.emit("运行中")
        self._emit_batch_log(f"共 {len(self.link_tasks)} 条链接，开始处理")
        results: list[SingleLinkClaimResult] = []
        prepared_tasks: list[PreparedLinkTask] = []

        try:
            for link_task in self.link_tasks:
                try:
                    prepared_tasks.append(self._prepare_link_task(link_task))
                except BiliRewardError as exc:
                    self._emit_link_log(link_task.index, f"[任务] 预处理失败: {exc}")
                    self.link_status_changed.emit(link_task.index, "失败")
                    results.append(
                        SingleLinkClaimResult(
                            index=link_task.index,
                            task_id=link_task.task_id,
                            status="failed",
                            error=str(exc),
                        )
                    )

            if prepared_tasks:
                self._emit_batch_log("预处理完成，开始并行抢奖")
                with ThreadPoolExecutor(max_workers=len(prepared_tasks)) as executor:
                    futures = [executor.submit(self._claim_prepared_task, task) for task in prepared_tasks]
                    for future in as_completed(futures):
                        results.append(future.result())
            else:
                self._emit_batch_log("没有可执行的链接")
        finally:
            sorted_results = sorted(results, key=lambda item: item.index)
            self._emit_batch_log("全部链接处理完成")
            self.batch_completed.emit(BatchClaimResult(results=sorted_results))
            self.status_changed.emit(self._resolve_batch_status(sorted_results))
            self.finished.emit()
