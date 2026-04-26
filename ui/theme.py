"""Bilibili Neo-Pop — Light theme (DPI-aware).

Font sizes are scaled by screen DPI so they look consistent across
resolutions. Baseline is 96 DPI.
"""
from __future__ import annotations

from PyQt5.QtWidgets import QApplication

# ── Palette ────────────────────────────────────────────
ROOT_BG    = "#F3F1EE"
CARD_BG    = "#FFFFFF"
INPUT_BG   = "#F8F7F5"
BORDER     = "#E2DFDA"
BORDER_FOC = "#00A1D6"
TEXT_MAIN  = "#1C1B1F"
TEXT_SUB   = "#6E6B6B"
TEXT_DIM   = "#9E9C99"
BLUE       = "#00A1D6"
BLUE_HOVER = "#0AB8EC"
BLUE_PRESS = "#0089B8"
PINK       = "#FB7299"
PINK_HOVER = "#FF8BAB"
GREEN      = "#00C853"
AMBER      = "#F5A623"
RED        = "#FF5252"


def _scale(s: float, fs: int) -> str:
    return f"{round(fs * s)}px"


def _build_qss(scale: float) -> str:
    s = scale  # shorthand
    return f"""
/* ── Global ─────────────────────────────────── */
QMainWindow {{
    background-color: {ROOT_BG};
}}

QWidget {{
    font-family: "Microsoft YaHei UI", "PingFang SC", "Noto Sans SC", sans-serif;
    font-size: {_scale(s, 14)};
    color: {TEXT_MAIN};
}}

/* ── QPushButton base ────────────────────────── */
QPushButton {{
    background-color: {CARD_BG};
    color: {TEXT_MAIN};
    border: 1.5px solid {BORDER};
    border-radius: {_scale(s, 10)};
    padding: {_scale(s, 7)} {_scale(s, 18)};
    font-size: {_scale(s, 13)};
    font-weight: 500;
}}
QPushButton:hover {{
    border-color: {BLUE};
    background-color: #F0F9FD;
}}
QPushButton:pressed {{
    background-color: #E4F3FA;
}}
QPushButton:disabled {{
    background-color: #F5F4F2;
    color: {TEXT_DIM};
    border-color: #EBE8E4;
}}

/* Primary action button */
QPushButton[cssClass="primary"] {{
    background-color: {BLUE};
    color: #FFFFFF;
    border: none;
    font-weight: 700;
    font-size: {_scale(s, 16)};
    padding: {_scale(s, 9)} {_scale(s, 28)};
    border-radius: {_scale(s, 12)};
    min-width: {_scale(s, 140)};
    max-height: {_scale(s, 44)};
}}
QPushButton[cssClass="primary"]:hover {{
    background-color: {BLUE_HOVER};
}}
QPushButton[cssClass="primary"]:pressed {{
    background-color: {BLUE_PRESS};
}}
QPushButton[cssClass="primary"]:disabled {{
    background-color: #C8EAF5;
    color: #8CCFDF;
}}

/* Icon buttons (+/-) */
QPushButton[cssClass="iconBtn"] {{
    background-color: transparent;
    border: 1.5px solid {BORDER};
    border-radius: {_scale(s, 9)};
    min-width: {_scale(s, 34)};
    max-width: {_scale(s, 34)};
    min-height: {_scale(s, 34)};
    max-height: {_scale(s, 34)};
    font-size: {_scale(s, 18)};
    font-weight: 600;
    padding: 0px;
    color: {TEXT_SUB};
}}
QPushButton[cssClass="iconBtn"]:hover {{
    border-color: {BLUE};
    color: {BLUE};
    background-color: #F0F9FD;
}}

/* Pause — amber */
QPushButton[cssClass="pauseBtn"] {{
    border-color: {AMBER};
    color: {AMBER};
    font-weight: 600;
    min-width: {_scale(s, 56)};
    max-height: {_scale(s, 34)};
    font-size: {_scale(s, 13)};
}}
QPushButton[cssClass="pauseBtn"]:hover {{
    background-color: #FFF8ED;
    border-color: #F7B84A;
}}

/* Resume — green */
QPushButton[cssClass="resumeBtn"] {{
    border-color: {GREEN};
    color: {GREEN};
    font-weight: 600;
    min-width: {_scale(s, 56)};
    max-height: {_scale(s, 34)};
    font-size: {_scale(s, 13)};
}}
QPushButton[cssClass="resumeBtn"]:hover {{
    background-color: #EDFFF5;
    border-color: #00E066;
}}

/* Cancel — red */
QPushButton[cssClass="cancelBtn"] {{
    border-color: {RED};
    color: {RED};
    font-weight: 600;
    min-width: {_scale(s, 56)};
    max-height: {_scale(s, 34)};
    font-size: {_scale(s, 13)};
}}
QPushButton[cssClass="cancelBtn"]:hover {{
    background-color: #FFF0F2;
    border-color: #FF6B7A;
}}

/* ── QLineEdit ───────────────────────────────── */
QLineEdit {{
    background-color: {INPUT_BG};
    color: {TEXT_MAIN};
    border: 1.5px solid {BORDER};
    border-radius: {_scale(s, 10)};
    padding: {_scale(s, 8)} {_scale(s, 14)};
    font-size: {_scale(s, 14)};
    selection-background-color: {BLUE};
    selection-color: #FFFFFF;
}}
QLineEdit:focus {{
    border-color: {BLUE};
    background-color: #FFFFFF;
}}
QLineEdit::placeholder {{
    color: {TEXT_DIM};
}}
QLineEdit:disabled {{
    background-color: #F5F4F2;
    color: {TEXT_DIM};
}}

/* ── QLabel ─────────────────────────────────── */
QLabel {{
    color: {TEXT_MAIN};
    background: transparent;
    border: none;
    font-size: {_scale(s, 14)};
}}

QLabel[cssClass="dim"] {{
    color: {TEXT_SUB};
    font-size: {_scale(s, 14)};
}}

QLabel[cssClass="status"] {{
    font-size: {_scale(s, 13)};
    font-weight: 600;
    padding: 3px 10px;
    border-radius: 6px;
}}

QLabel[cssClass="title"] {{
    font-size: {_scale(s, 25)};
    font-weight: 800;
    letter-spacing: 1px;
    color: {TEXT_MAIN};
}}

QLabel[cssClass="indexLabel"] {{
    font-size: {_scale(s, 14)};
    font-weight: 600;
    color: {TEXT_MAIN};
}}

/* ── QTextEdit ──────────────────────────────── */
QTextEdit {{
    background-color: #FFFFFF;
    color: {TEXT_MAIN};
    border: 1.5px solid {BORDER};
    border-radius: {_scale(s, 14)};
    padding: {_scale(s, 14)};
    font-family: "Cascadia Code", "Fira Code", "Consolas", "Microsoft YaHei UI", monospace;
    font-size: {_scale(s, 13)};
    selection-background-color: {BLUE};
    selection-color: #FFFFFF;
}}
QTextEdit:focus {{
    border-color: {BLUE};
}}

/* ── QScrollBar ──────────────────────────────── */
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    border-radius: 5px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: #D8D5D0;
    border-radius: 5px;
    min-height: 40px;
}}
QScrollBar::handle:vertical:hover {{
    background: {BLUE};
}}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{
    height: 0px;
}}
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {{
    background: transparent;
}}

QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    border-radius: 5px;
    margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background: #D8D5D0;
    border-radius: 5px;
    min-width: 40px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {BLUE};
}}

/* ── Cards ───────────────────────────────────── */
QFrame[cssClass="card"] {{
    background-color: {CARD_BG};
    border: 1.5px solid {BORDER};
    border-radius: {_scale(s, 14)};
    padding: {_scale(s, 14)};
}}

QFrame[cssClass="sep"] {{
    border: none;
    background-color: {BORDER};
    max-height: 1px;
}}

/* ── QMessageBox ─────────────────────────────── */
QMessageBox {{
    background-color: {CARD_BG};
}}
QMessageBox QLabel {{
    font-size: {_scale(s, 14)};
    color: {TEXT_MAIN};
}}
QMessageBox QPushButton {{
    min-width: {_scale(s, 90)};
    min-height: {_scale(s, 36)};
    font-size: {_scale(s, 13)};
}}

/* ── QToolTip ────────────────────────────────── */
QToolTip {{
    background-color: {CARD_BG};
    color: {TEXT_MAIN};
    border: 1.5px solid {BLUE};
    border-radius: 6px;
    padding: {_scale(s, 6)} {_scale(s, 10)};
    font-size: {_scale(s, 13)};
}}
"""


SCALE: float = 1.0


def apply_theme(app: QApplication) -> None:
    global SCALE
    screen = app.primaryScreen()
    if screen is not None:
        dpi = screen.logicalDotsPerInch()
        SCALE = dpi / 96.0
    qss = _build_qss(SCALE)
    app.setStyleSheet(qss)
