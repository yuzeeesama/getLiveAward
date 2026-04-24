from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

from PySide6.QtCore import QThread
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.logging_utils import format_log_line
from core.models import BatchClaimResult, LinkTaskItem, QrCodeData
from core.service import RewardService
from ui.qr_dialog import QrCodeDialog
from ui.worker import ClaimWorker


@dataclass
class LinkRowWidgets:
    container: QWidget
    label: QLabel
    input: QLineEdit
    add_button: QPushButton
    remove_button: QPushButton
    pause_button: QPushButton
    resume_button: QPushButton
    cancel_button: QPushButton
    status_label: QLabel


class MainWindow(QMainWindow):
    STATUS_IDLE = "空闲"
    STATUS_RUNNING = "运行中"
    STATUS_SUCCESS = "成功"
    STATUS_FAILED = "失败"
    STATUS_CANCELLED = "已取消"

    def __init__(self, service: RewardService) -> None:
        super().__init__()
        self.service = service
        self.worker_thread: QThread | None = None
        self.worker: ClaimWorker | None = None
        self.qr_dialog: QrCodeDialog | None = None
        self._is_running = False
        self._current_qr_link_index: int | None = None
        self._row_claim_stage_active: dict[int, bool] = {}
        self.link_rows: list[LinkRowWidgets] = []

        self.setWindowTitle("Bilibili Live Reward")
        self.resize(1080, 640)
        self._build_ui()

    def _build_ui(self) -> None:
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        self.start_button = QPushButton("全部开始")
        self.start_button.clicked.connect(self.start_claim)

        self.status_title = QLabel("批次状态")
        self.status_value = QLabel(self.STATUS_IDLE)

        header_layout = QHBoxLayout()
        header_layout.addWidget(self.start_button)
        header_layout.addWidget(self.status_title)
        header_layout.addWidget(self.status_value)
        header_layout.addStretch(1)

        self.rows_layout = QVBoxLayout()
        self.rows_layout.setSpacing(8)
        self.add_link_row()

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)

        root_layout = QVBoxLayout(central_widget)
        root_layout.addLayout(header_layout)
        root_layout.addLayout(self.rows_layout)
        root_layout.addWidget(self.log_text, 1)

    def _create_link_row(self, text: str = "") -> LinkRowWidgets:
        container = QWidget(self)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)

        label = QLabel()
        input_widget = QLineEdit()
        input_widget.setText(text)
        input_widget.setPlaceholderText(
            "请输入领取界面链接，例如 https://www.bilibili.com/blackboard/era/award-exchange.html?task_id=18ERA2wloghvyx300"
        )
        add_button = QPushButton("+")
        remove_button = QPushButton("-")
        pause_button = QPushButton("暂停")
        resume_button = QPushButton("继续")
        cancel_button = QPushButton("取消")
        status_label = QLabel(self.STATUS_IDLE)

        row = LinkRowWidgets(
            container=container,
            label=label,
            input=input_widget,
            add_button=add_button,
            remove_button=remove_button,
            pause_button=pause_button,
            resume_button=resume_button,
            cancel_button=cancel_button,
            status_label=status_label,
        )

        add_button.clicked.connect(lambda: self.add_link_row(after_row=row))
        remove_button.clicked.connect(lambda: self.remove_link_row(row))
        pause_button.clicked.connect(lambda: self.pause_claim(row))
        resume_button.clicked.connect(lambda: self.resume_claim(row))
        cancel_button.clicked.connect(lambda: self.cancel_claim(row))

        layout.addWidget(label)
        layout.addWidget(input_widget, 1)
        layout.addWidget(add_button)
        layout.addWidget(remove_button)
        layout.addWidget(pause_button)
        layout.addWidget(resume_button)
        layout.addWidget(cancel_button)
        layout.addWidget(status_label)

        return row

    def add_link_row(self, *, after_row: LinkRowWidgets | None = None, text: str = "") -> None:
        new_row = self._create_link_row(text)
        if after_row is None:
            insert_index = len(self.link_rows)
        else:
            insert_index = self.link_rows.index(after_row) + 1
        self.link_rows.insert(insert_index, new_row)
        self.rows_layout.insertWidget(insert_index, new_row.container)
        self._refresh_link_rows()

    def remove_link_row(self, row: LinkRowWidgets) -> None:
        if self._is_running or len(self.link_rows) <= 1:
            return
        index = self.link_rows.index(row)
        removed = self.link_rows.pop(index)
        self.rows_layout.removeWidget(removed.container)
        removed.container.deleteLater()
        self._refresh_link_rows()

    def _refresh_link_rows(self) -> None:
        for index, row in enumerate(self.link_rows):
            row.label.setText(f"链接{index + 1}")
            row.input.setEnabled(not self._is_running)
            row.add_button.setEnabled(not self._is_running)
            row.remove_button.setEnabled(not self._is_running and len(self.link_rows) > 1)
            self._sync_row_action_buttons(index)

    def _parse_task_id_from_url(self, task_url: str) -> str:
        parsed = urlparse(task_url)
        query = parse_qs(parsed.query)
        task_ids = query.get("task_id") or query.get("taskId")
        if not task_ids:
            return ""
        return task_ids[0].strip()

    def _collect_link_tasks(self) -> list[LinkTaskItem]:
        tasks: list[LinkTaskItem] = []
        for index, row in enumerate(self.link_rows):
            task_url = row.input.text().strip()
            if not task_url:
                continue
            task_id = self._parse_task_id_from_url(task_url)
            if not task_id:
                raise ValueError(f"第 {index + 1} 条领取链接无效，未解析到 task_id。")
            tasks.append(LinkTaskItem(index=index, task_url=task_url, task_id=task_id))
        return tasks

    def start_claim(self) -> None:
        if self._is_running:
            self.append_ui_log("[批次] 批次任务进行中，请勿重复点击")
            return

        try:
            link_tasks = self._collect_link_tasks()
        except ValueError as exc:
            QMessageBox.warning(self, "领取链接无效", str(exc))
            return

        if not link_tasks:
            QMessageBox.warning(self, "领取链接为空", "请至少输入一条领取链接。")
            return

        for row in self.link_rows:
            row.status_label.setText(self.STATUS_IDLE if row.input.text().strip() else self.STATUS_IDLE)

        for task in link_tasks:
            self.append_ui_log(f"[链接{task.index + 1}] [任务] 已解析 task_id: {task.task_id}")

        self._set_running(True)
        self.set_status(self.STATUS_RUNNING)

        self.worker_thread = QThread(self)
        self.worker = ClaimWorker(self.service, link_tasks)
        self.worker.moveToThread(self.worker_thread)

        self.worker_thread.started.connect(self.worker.run)
        self.worker.log_message.connect(self.append_log)
        self.worker.status_changed.connect(self.set_status)
        self.worker.link_status_changed.connect(self.set_link_status)
        self.worker.link_claim_stage_changed.connect(self.set_link_claim_stage_active)
        self.worker.qr_code_ready.connect(self.show_qr_dialog)
        self.worker.batch_completed.connect(self.on_batch_completed)
        self.worker.finished.connect(self.on_worker_finished)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)
        self.worker_thread.start()

    def append_log(self, message: str) -> None:
        self.log_text.append(message)
        if self.qr_dialog is not None and self.qr_dialog.isVisible() and "[登录]" in message:
            self.qr_dialog.set_status_text(message)

    def append_ui_log(self, message: str) -> None:
        self.append_log(format_log_line(message))

    def set_status(self, text: str) -> None:
        self.status_value.setText(text)
        self.start_button.setEnabled(not self._is_running)

    def _set_running(self, running: bool) -> None:
        self._is_running = running
        self.start_button.setEnabled(not running)
        self._refresh_link_rows()

    def _sync_row_action_buttons(self, link_index: int) -> None:
        if link_index >= len(self.link_rows):
            return
        row = self.link_rows[link_index]
        status = row.status_label.text()
        active = self._row_claim_stage_active.get(link_index, False)
        row.pause_button.setEnabled(self._is_running and active and status == "抢奖中")
        row.resume_button.setEnabled(self._is_running and active and status == "已暂停")
        row.cancel_button.setEnabled(self._is_running and active and status in {"抢奖中", "已暂停"})

    def set_link_status(self, link_index: int, status: str) -> None:
        if link_index >= len(self.link_rows):
            return
        self.link_rows[link_index].status_label.setText(status)
        self._sync_row_action_buttons(link_index)

    def set_link_claim_stage_active(self, link_index: int, active: bool) -> None:
        self._row_claim_stage_active[link_index] = active
        self._sync_row_action_buttons(link_index)

    def pause_claim(self, row: LinkRowWidgets) -> None:
        if self.worker is None:
            return
        self.worker.pause_claim(self.link_rows.index(row))

    def resume_claim(self, row: LinkRowWidgets) -> None:
        if self.worker is None:
            return
        self.worker.resume_claim(self.link_rows.index(row))

    def cancel_claim(self, row: LinkRowWidgets) -> None:
        if self.worker is None:
            return
        self.worker.cancel_claim(self.link_rows.index(row))

    def show_qr_dialog(self, link_index: int, qr_data: QrCodeData) -> None:
        self._current_qr_link_index = link_index
        if self.qr_dialog is None:
            self.qr_dialog = QrCodeDialog(self)
            self.qr_dialog.rejected.connect(self.cancel_login)
        self.qr_dialog.setWindowTitle(f"链接{link_index + 1} 扫码登录")
        self.qr_dialog.set_status_text(f"链接{link_index + 1}：请使用 B 站 APP 扫码")
        self.qr_dialog.set_qr_code(qr_data.image_bytes, qr_data.login_url)
        self.qr_dialog.show()
        self.qr_dialog.raise_()
        self.qr_dialog.activateWindow()

    def cancel_login(self) -> None:
        if self.worker is None:
            return
        if self._current_qr_link_index is not None:
            self.append_ui_log(f"[链接{self._current_qr_link_index + 1}] [登录] 用户关闭二维码弹窗，准备取消登录")
        else:
            self.append_ui_log("[登录] 用户关闭二维码弹窗，准备取消登录")
        self.worker.cancel_login()

    def on_batch_completed(self, result: BatchClaimResult) -> None:
        success_count = sum(1 for item in result.results if item.status == "success")
        failed_count = sum(1 for item in result.results if item.status == "failed")
        cancelled_count = sum(1 for item in result.results if item.status == "cancelled")
        self.append_ui_log(
            f"[批次] 处理完成：成功 {success_count} 条，失败 {failed_count} 条，取消 {cancelled_count} 条"
        )
        QMessageBox.information(
            self,
            "批次完成",
            f"成功 {success_count} 条\n失败 {failed_count} 条\n取消 {cancelled_count} 条",
        )

    def on_worker_finished(self) -> None:
        self._set_running(False)
        self._row_claim_stage_active.clear()
        self._current_qr_link_index = None
        for index in range(len(self.link_rows)):
            self._sync_row_action_buttons(index)
        if self.qr_dialog is not None:
            self.qr_dialog.hide()
        if self.worker_thread is not None:
            self.worker_thread = None
        self.worker = None

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if self._is_running and self.worker is not None:
            self.worker.cancel_login()
            for index in range(len(self.link_rows)):
                self.worker.cancel_claim(index)
        super().closeEvent(event)
