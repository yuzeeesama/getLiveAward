from __future__ import annotations

import os
import sys

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication

from core.service import RewardService
from ui.main_window import MainWindow
from ui.theme import apply_theme

# Enable high-DPI scaling — must happen before QApplication creation
os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")
QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)


def main() -> int:
    app = QApplication(sys.argv)

    # Report detected scale factor
    screen = app.primaryScreen()
    if screen is not None:
        dpi = screen.logicalDotsPerInch()
        ratio = screen.devicePixelRatio()
        print(f"Screen DPI: {dpi:.0f}, devicePixelRatio: {ratio:.1f}")

    apply_theme(app)
    service = RewardService()
    window = MainWindow(service)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
