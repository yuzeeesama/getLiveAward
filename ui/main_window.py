from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

from PyQt5.QtCore import Qt, QThread
from PyQt5.QtWidgets import (
    QFrame,
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
from ui.theme import SCALE
from ui.worker import ClaimWorker


# ── Helpers ────────────────────────────────────────────
def _css(widget, class_name: str) -> None:
    widget.setProperty("cssClass", class_name)
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def _btn(text: str, css: str, parent: QWidget) -> QPushButton:
    btn = QPushButton(text, parent)
    btn.setCursor(Qt.PointingHandCursor)
    _css(btn, css)
    return btn


def _icon_btn(text: str, parent: QWidget) -> QPushButton:
    btn = QPushButton(text, parent)
    btn.setCursor(Qt.PointingHandCursor)
    _css(btn, "iconBtn")
    return btn


# ── Data ───────────────────────────────────────────────
@dataclass
class LinkRowWidgets:
    frame: QFrame
    index_label: QLabel
    input: QLineEdit
    add_btn: QPushButton
    remove_btn: QPushButton
    pause_btn: QPushButton
    resume_btn: QPushButton
    cancel_btn: QPushButton
    status_label: QLabel


# ── Main Window ────────────────────────────────────────
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
        self.resize(1060, 680)
        self.setMinimumSize(800, 500)
        self._build_ui()

    # ── Build ───────────────────────────────────────────
    def _build_ui(self) -> None:
        root = QWidget(self)
        self.setCentralWidget(root)

        # Header
        title = QLabel("Bilibili Live Reward")
        _css(title, "title")

        self.start_btn = _btn("全 部 开 始", "primary", root)
        self.start_btn.clicked.connect(self.start_claim)

        self.batch_label = QLabel("批次状态")
        _css(self.batch_label, "dim")

        self.batch_status = QLabel(self.STATUS_IDLE)
        _css(self.batch_status, "dim")

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.batch_label)
        header.addSpacing(round(8 * SCALE))
        header.addWidget(self.batch_status)
        header.addSpacing(round(24 * SCALE))
        header.addWidget(self.start_btn)

        # Separator
        sep = QFrame(root)
        _css(sep, "sep")

        # Link rows
        self.rows_wrap = QVBoxLayout()
        self.rows_wrap.setContentsMargins(0, 0, 0, 0)
        self.rows_wrap.setSpacing(round(12 * SCALE))
        self.add_link_row()

        # Log area
        self.log_text = QTextEdit(root)
        self.log_text.setReadOnly(True)
        self.log_text.setPlaceholderText("等待任务开始...")

        # Root layout
        layout = QVBoxLayout(root)
        layout.setContentsMargins(round(32 * SCALE), round(28 * SCALE), round(32 * SCALE), round(24 * SCALE))
        layout.setSpacing(round(18 * SCALE))
        layout.addLayout(header)
        layout.addWidget(sep)
        layout.addLayout(self.rows_wrap, 0)
        layout.addWidget(self.log_text, 1)

    # ── Row management ──────────────────────────────────
    def _create_link_row(self, text: str = "") -> LinkRowWidgets:
        frame = QFrame(self.centralWidget())
        _css(frame, "card")

        row = QHBoxLayout(frame)
        row.setContentsMargins(round(20 * SCALE), round(14 * SCALE), round(20 * SCALE), round(14 * SCALE))
        row.setSpacing(round(12 * SCALE))

        idx = QLabel()
        _css(idx, "indexLabel")
        idx.setFixedWidth(round(68 * SCALE))
        idx.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        row.addWidget(idx)

        inp = QLineEdit()
        inp.setText(text)
        inp.setPlaceholderText("输入兑换链接，如 https://www.bilibili.com/blackboard/era/award-exchange.html?task_id=...")
        row.addWidget(inp, 1)

        add_btn = _icon_btn("+", frame)
        row.addWidget(add_btn)

        rem_btn = _icon_btn("−", frame)
        row.addWidget(rem_btn)

        pause_btn = _btn("暂停", "pauseBtn", frame)
        row.addWidget(pause_btn)

        resume_btn = _btn("继续", "resumeBtn", frame)
        row.addWidget(resume_btn)

        cancel_btn = _btn("取消", "cancelBtn", frame)
        row.addWidget(cancel_btn)

        status_lbl = QLabel(self.STATUS_IDLE)
        _css(status_lbl, "dim")
        status_lbl.setFixedWidth(round(64 * SCALE))
        status_lbl.setAlignment(Qt.AlignVCenter | Qt.AlignCenter)
        row.addWidget(status_lbl)

        rw = LinkRowWidgets(
            frame=frame, index_label=idx, input=inp,
            add_btn=add_btn, remove_btn=rem_btn,
            pause_btn=pause_btn, resume_btn=resume_btn,
            cancel_btn=cancel_btn, status_label=status_lbl,
        )

        add_btn.clicked.connect(lambda: self.add_link_row(after_row=rw))
        rem_btn.clicked.connect(lambda: self.remove_link_row(rw))
        pause_btn.clicked.connect(lambda: self.pause_claim(rw))
        resume_btn.clicked.connect(lambda: self.resume_claim(rw))
        cancel_btn.clicked.connect(lambda: self.cancel_claim(rw))

        return rw

    def add_link_row(self, *, after_row: LinkRowWidgets | None = None, text: str = "") -> None:
        new_row = self._create_link_row(text)
        idx = self.link_rows.index(after_row) + 1 if after_row else len(self.link_rows)
        self.link_rows.insert(idx, new_row)
        self.rows_wrap.insertWidget(idx, new_row.frame)
        self._refresh_link_rows()

    def remove_link_row(self, row: LinkRowWidgets) -> None:
        if self._is_running or len(self.link_rows) <= 1:
            return
        self.link_rows.remove(row)
        self.rows_wrap.removeWidget(row.frame)
        row.frame.deleteLater()
        self._refresh_link_rows()

    def _refresh_link_rows(self) -> None:
        for i, rw in enumerate(self.link_rows):
            rw.index_label.setText(f"链接 {i + 1}")
            rw.input.setEnabled(not self._is_running)
            rw.add_btn.setEnabled(not self._is_running)
            rw.remove_btn.setEnabled(not self._is_running and len(self.link_rows) > 1)
            self._sync_row_action_buttons(i)

    # ── URL parsing ─────────────────────────────────────
    @staticmethod
    def _parse_task_id_from_url(task_url: str) -> str:
        parsed = urlparse(task_url)
        qs = parse_qs(parsed.query)
        ids = qs.get("task_id") or qs.get("taskId")
        return ids[0].strip() if ids else ""

    def _collect_link_tasks(self) -> list[LinkTaskItem]:
        tasks: list[LinkTaskItem] = []
        for i, rw in enumerate(self.link_rows):
            url = rw.input.text().strip()
            if not url:
                continue
            tid = self._parse_task_id_from_url(url)
            if not tid:
                raise ValueError(f"第 {i + 1} 条领取链接无效，未解析到 task_id。")
            tasks.append(LinkTaskItem(index=i, task_url=url, task_id=tid))
        return tasks

    # ── Claim flow ──────────────────────────────────────
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

        for rw in self.link_rows:
            rw.status_label.setText(self.STATUS_IDLE if rw.input.text().strip() else self.STATUS_IDLE)

        for task in link_tasks:
            self.append_ui_log(f"[链接{task.index + 1}] [任务] task_id: {task.task_id}")

        self._set_running(True)
        self.set_batch_status(self.STATUS_RUNNING, "primary")

        self.worker_thread = QThread(self)
        self.worker = ClaimWorker(self.service, link_tasks)
        self.worker.moveToThread(self.worker_thread)

        self.worker_thread.started.connect(self.worker.run)
        self.worker.log_message.connect(self.append_log)
        self.worker.status_changed.connect(lambda s: self.set_batch_status(s, None))
        self.worker.link_status_changed.connect(self.set_link_status)
        self.worker.link_claim_stage_changed.connect(self.set_link_claim_stage_active)
        self.worker.qr_code_ready.connect(self.show_qr_dialog)
        self.worker.batch_completed.connect(self.on_batch_completed)
        self.worker.finished.connect(self.on_worker_finished)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)
        self.worker_thread.start()

    # ── Logging ─────────────────────────────────────────
    def append_log(self, message: str) -> None:
        self.log_text.append(message)
        if self.qr_dialog and self.qr_dialog.isVisible() and "[登录]" in message:
            self.qr_dialog.set_status_text(message)

    def append_ui_log(self, message: str) -> None:
        self.append_log(format_log_line(message))

    # ── State ───────────────────────────────────────────
    def set_batch_status(self, text: str, css: str | None) -> None:
        self.batch_status.setText(text)
        if css:
            _css(self.batch_status, css)

    def _set_running(self, running: bool) -> None:
        self._is_running = running
        self._refresh_link_rows()
        if not running:
            self.set_batch_status(self.STATUS_IDLE, "dim")
            self.start_btn.setEnabled(True)
        else:
            self.start_btn.setEnabled(False)

    def _sync_row_action_buttons(self, link_index: int) -> None:
        if link_index >= len(self.link_rows):
            return
        rw = self.link_rows[link_index]
        st = rw.status_label.text()
        active = self._row_claim_stage_active.get(link_index, False)

        rw.pause_btn.setEnabled(self._is_running and active and st == "抢奖中")
        rw.resume_btn.setEnabled(self._is_running and active and st == "已暂停")
        rw.cancel_btn.setEnabled(self._is_running and active and st in {"抢奖中", "已暂停"})

        # Color the status label
        color_map = {"抢奖中": "resumeBtn", "已暂停": "pauseBtn",
                     "成功": "resumeBtn", "失败": "cancelBtn", "已取消": "cancelBtn"}
        _css(rw.status_label, color_map.get(st, "dim"))

    def set_link_status(self, link_index: int, status: str) -> None:
        if link_index >= len(self.link_rows):
            return
        self.link_rows[link_index].status_label.setText(status)
        self._sync_row_action_buttons(link_index)

    def set_link_claim_stage_active(self, link_index: int, active: bool) -> None:
        self._row_claim_stage_active[link_index] = active
        self._sync_row_action_buttons(link_index)

    # ── Actions ─────────────────────────────────────────
    def pause_claim(self, row: LinkRowWidgets) -> None:
        if self.worker:
            self.worker.pause_claim(self.link_rows.index(row))

    def resume_claim(self, row: LinkRowWidgets) -> None:
        if self.worker:
            self.worker.resume_claim(self.link_rows.index(row))

    def cancel_claim(self, row: LinkRowWidgets) -> None:
        if self.worker:
            self.worker.cancel_claim(self.link_rows.index(row))

    # ── QR dialog ───────────────────────────────────────
    def show_qr_dialog(self, link_index: int, qr_data: QrCodeData) -> None:
        self._current_qr_link_index = link_index
        if self.qr_dialog is None:
            self.qr_dialog = QrCodeDialog(self)
            self.qr_dialog.rejected.connect(self.cancel_login)
        self.qr_dialog.setWindowTitle(f"链接{link_index + 1} 扫码登录")
        self.qr_dialog.set_status_text(f"链接{link_index + 1}：使用 B 站 APP 扫码")
        self.qr_dialog.set_qr_code(qr_data.image_bytes, qr_data.login_url)
        self.qr_dialog.show()
        self.qr_dialog.raise_()
        self.qr_dialog.activateWindow()

    def cancel_login(self) -> None:
        if self.worker is None:
            return
        idx = self._current_qr_link_index
        self.append_ui_log(f"[链接{idx + 1}] [登录] 用户关闭二维码弹窗" if idx is not None else "[登录] 关闭弹窗")
        self.worker.cancel_login()

    # ── Completion ──────────────────────────────────────
    def on_batch_completed(self, result: BatchClaimResult) -> None:
        sc = sum(1 for r in result.results if r.status == "success")
        fc = sum(1 for r in result.results if r.status == "failed")
        cc = sum(1 for r in result.results if r.status == "cancelled")
        self.append_ui_log(f"[批次] 完成 — 成功 {sc} / 失败 {fc} / 取消 {cc}")
        QMessageBox.information(self, "批次完成",
            f"成功 {sc} 条\n失败 {fc} 条\n取消 {cc} 条")

    def on_worker_finished(self) -> None:
        self._set_running(False)
        self._row_claim_stage_active.clear()
        self._current_qr_link_index = None
        for i in range(len(self.link_rows)):
            self._sync_row_action_buttons(i)
        if self.qr_dialog:
            self.qr_dialog.hide()
        self.worker_thread = None
        self.worker = None

    def closeEvent(self, event) -> None:
        if self._is_running and self.worker:
            self.worker.cancel_login()
            for i in range(len(self.link_rows)):
                self.worker.cancel_claim(i)
        super().closeEvent(event)
