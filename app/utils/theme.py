"""
テーマ管理ユーティリティ

QApplication レベルの QSS 切替と、QPainter で直接描画する
CardDelegate 用のカラーパレットを提供する。
"""

from __future__ import annotations

from PyQt6.QtWidgets import QApplication

# ---------------------------------------------------------------------------
# カラーパレット（CardDelegate の QPainter 描画で使用）
# ---------------------------------------------------------------------------

_DARK_CARD_COLORS = {
    "card_bg":        "#374151",   # カード背景
    "card_bg_sel":    "#3b82f6",   # 選択中カード背景
    "thumb_bg":       "#1f2937",   # サムネイルなし時の背景
    "title_fg":       "#f3f4f6",   # タイトルテキスト
    "icon_fg":        "#6b7280",   # フォルダアイコン色
}

_LIGHT_CARD_COLORS = {
    "card_bg":        "#e5e7eb",
    "card_bg_sel":    "#3b82f6",
    "thumb_bg":       "#d1d5db",
    "title_fg":       "#111827",
    "icon_fg":        "#6b7280",
}

# ---------------------------------------------------------------------------
# QSS スタイルシート
# ---------------------------------------------------------------------------

_DARK_QSS = """
QWidget {
    background-color: #1f2937;
    color: #f3f4f6;
}
QMainWindow {
    background-color: #111827;
}
QToolBar {
    background-color: #1f2937;
    border-bottom: 1px solid #374151;
    spacing: 4px;
    padding: 2px 4px;
}
QToolBar QLabel {
    color: #9ca3af;
}
QPushButton {
    background-color: #374151;
    color: #f3f4f6;
    border: 1px solid #4b5563;
    border-radius: 4px;
    padding: 4px 10px;
}
QPushButton:hover {
    background-color: #4b5563;
}
QPushButton:pressed {
    background-color: #6b7280;
}
QPushButton:checked {
    background-color: #3b82f6;
    color: white;
    border-color: #2563eb;
}
QPushButton:disabled {
    background-color: #374151;
    color: #6b7280;
}
QFileDialog QSizeGrip {
    background-color: transparent;
    image: none;
}
QListView {
    background-color: #111827;
    border: none;
}
QListView::item:selected {
    background-color: transparent;
}
QDialog {
    background-color: #1f2937;
}
QLineEdit, QTextEdit {
    background-color: #374151;
    color: #f3f4f6;
    border: 1px solid #4b5563;
    border-radius: 4px;
    padding: 4px;
}
QLineEdit:focus, QTextEdit:focus {
    border-color: #3b82f6;
}
QCheckBox {
    color: #f3f4f6;
}
QCheckBox::indicator {
    border: 1px solid #4b5563;
    background-color: #374151;
    border-radius: 2px;
    width: 14px;
    height: 14px;
}
QCheckBox::indicator:checked {
    background-color: #3b82f6;
    border-color: #2563eb;
}
QLabel {
    color: #f3f4f6;
    background-color: transparent;
}
QStatusBar {
    background-color: #1f2937;
    color: #9ca3af;
    border-top: 1px solid #374151;
}
QMenu {
    background-color: #1f2937;
    color: #f3f4f6;
    border: 1px solid #374151;
}
QMenu::item:selected {
    background-color: #3b82f6;
}
QMessageBox {
    background-color: #1f2937;
}
QScrollBar:vertical {
    background-color: #1f2937;
    width: 8px;
}
QScrollBar::handle:vertical {
    background-color: #4b5563;
    border-radius: 4px;
    min-height: 20px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
"""

_LIGHT_QSS = """
QWidget {
    background-color: #f3f4f6;
    color: #111827;
}
QMainWindow {
    background-color: #e5e7eb;
}
QToolBar {
    background-color: #f3f4f6;
    border-bottom: 1px solid #d1d5db;
    spacing: 4px;
    padding: 2px 4px;
}
QToolBar QLabel {
    color: #6b7280;
}
QPushButton {
    background-color: #e5e7eb;
    color: #111827;
    border: 1px solid #d1d5db;
    border-radius: 4px;
    padding: 4px 10px;
}
QPushButton:hover {
    background-color: #d1d5db;
}
QPushButton:pressed {
    background-color: #9ca3af;
}
QPushButton:checked {
    background-color: #3b82f6;
    color: white;
    border-color: #2563eb;
}
QPushButton:disabled {
    background-color: #e5e7eb;
    color: #9ca3af;
}
QFileDialog QSizeGrip {
    background-color: transparent;
    image: none;
}
QListView {
    background-color: #e5e7eb;
    border: none;
}
QListView::item:selected {
    background-color: transparent;
}
QDialog {
    background-color: #f3f4f6;
}
QLineEdit, QTextEdit {
    background-color: white;
    color: #111827;
    border: 1px solid #d1d5db;
    border-radius: 4px;
    padding: 4px;
}
QLineEdit:focus, QTextEdit:focus {
    border-color: #3b82f6;
}
QCheckBox {
    color: #111827;
}
QCheckBox::indicator {
    border: 1px solid #d1d5db;
    background-color: white;
    border-radius: 2px;
    width: 14px;
    height: 14px;
}
QCheckBox::indicator:checked {
    background-color: #3b82f6;
    border-color: #2563eb;
}
QLabel {
    color: #111827;
    background-color: transparent;
}
QStatusBar {
    background-color: #f3f4f6;
    color: #6b7280;
    border-top: 1px solid #d1d5db;
}
QMenu {
    background-color: #f9fafb;
    color: #111827;
    border: 1px solid #d1d5db;
}
QMenu::item:selected {
    background-color: #3b82f6;
    color: white;
}
QMessageBox {
    background-color: #f3f4f6;
}
QScrollBar:vertical {
    background-color: #e5e7eb;
    width: 8px;
}
QScrollBar::handle:vertical {
    background-color: #9ca3af;
    border-radius: 4px;
    min-height: 20px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
"""

# ---------------------------------------------------------------------------
# 公開 API
# ---------------------------------------------------------------------------

_current_theme: str = "dark"


def card_colors() -> dict[str, str]:
    """現在のテーマに対応したカード描画色を返す。"""
    return _DARK_CARD_COLORS if _current_theme == "dark" else _LIGHT_CARD_COLORS


def apply_theme(app: QApplication, theme: str) -> None:
    """QApplication にテーマを適用する。"""
    global _current_theme
    _current_theme = theme
    qss = _DARK_QSS if theme == "dark" else _LIGHT_QSS
    app.setStyleSheet(qss)
