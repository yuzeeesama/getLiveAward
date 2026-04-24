from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from core.service import RewardService
from ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    service = RewardService()
    window = MainWindow(service)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
