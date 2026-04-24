from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout


class QrCodeDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("扫码登录")
        self.setModal(True)
        self.setMinimumWidth(360)

        self.status_label = QLabel("请使用 B 站 APP 扫码")
        self.status_label.setAlignment(Qt.AlignCenter)

        self.qr_label = QLabel()
        self.qr_label.setAlignment(Qt.AlignCenter)
        self.qr_label.setMinimumSize(300, 300)

        self.url_label = QLabel()
        self.url_label.setAlignment(Qt.AlignCenter)
        self.url_label.setWordWrap(True)
        self.url_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.close_button = QPushButton("关闭")
        self.close_button.clicked.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.status_label)
        layout.addWidget(self.qr_label)
        layout.addWidget(self.url_label)
        layout.addWidget(self.close_button)

    def set_qr_code(self, image_bytes: bytes, login_url: str) -> None:
        pixmap = QPixmap()
        pixmap.loadFromData(image_bytes, "PNG")
        self.qr_label.setPixmap(
            pixmap.scaled(280, 280, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        )
        self.url_label.setText(login_url)

    def set_status_text(self, text: str) -> None:
        self.status_label.setText(text)
