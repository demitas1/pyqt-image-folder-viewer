"""
SettingsPanel — 歯車ボタンクリックで表示される設定パネル（ポップアップ）

テーマ切替とサムネイルアスペクト比切替のUIを提供する。
実際の設定保存・適用は呼び出し側で行う。
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

ASPECT_RATIOS = ["16:9", "4:3", "1:1"]


class _SegmentedButtons(QWidget):
    """選択状態を持つセグメントボタン群。"""

    selection_changed = pyqtSignal(str)

    def __init__(self, options: list[str], current: str, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

        for i, opt in enumerate(options):
            btn = QPushButton(opt)
            btn.setCheckable(True)
            btn.setChecked(opt == current)
            btn.setFixedHeight(28)

            # 角丸：左端・右端・中間で異なるスタイル
            radius = "4px"
            if len(options) == 1:
                btn.setStyleSheet(self._btn_style(radius, radius, radius, radius, "0"))
            elif i == 0:
                btn.setStyleSheet(self._btn_style(radius, "0", "0", radius, "0"))
            elif i == len(options) - 1:
                btn.setStyleSheet(self._btn_style("0", radius, radius, "0", "-1px"))
            else:
                btn.setStyleSheet(self._btn_style("0", "0", "0", "0", "-1px"))

            self._group.addButton(btn, i)
            layout.addWidget(btn)

        self._options = options
        self._group.idToggled.connect(self._on_toggled)

    def _btn_style(self, tl: str, tr: str, br: str, bl: str, mgl: str) -> str:
        return f"""
            QPushButton {{
                border: 1px solid #888;
                border-radius: 0;
                border-top-left-radius: {tl};
                border-top-right-radius: {tr};
                border-bottom-right-radius: {br};
                border-bottom-left-radius: {bl};
                padding: 0 10px;
                margin-left: {mgl};
            }}
            QPushButton:checked {{
                background-color: #3b82f6;
                color: white;
                border-color: #2563eb;
            }}
        """

    def _on_toggled(self, btn_id: int, checked: bool) -> None:
        if checked:
            self.selection_changed.emit(self._options[btn_id])

    def set_current(self, value: str) -> None:
        for i, opt in enumerate(self._options):
            btn = self._group.button(i)
            if btn:
                btn.setChecked(opt == value)


class SettingsPanel(QDialog):
    """歯車ボタン直下に表示される設定ポップアップ。"""

    theme_changed = pyqtSignal(str)            # "light" | "dark"
    aspect_ratio_changed = pyqtSignal(str)     # "16:9" | "4:3" | "1:1"

    def __init__(self, theme: str, aspect_ratio: str, parent=None):
        super().__init__(parent, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self._theme = theme
        self._aspect_ratio = aspect_ratio
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # テーマ
        lbl_theme = QLabel("テーマ")
        lbl_theme.setStyleSheet("font-size: 11px; color: #888;")
        layout.addWidget(lbl_theme)

        self._theme_btns = _SegmentedButtons(["ライト", "ダーク"], self._theme_label(), self)
        self._theme_btns.selection_changed.connect(self._on_theme_changed)
        layout.addWidget(self._theme_btns)

        # サムネイルアスペクト比
        lbl_ratio = QLabel("サムネイル比率")
        lbl_ratio.setStyleSheet("font-size: 11px; color: #888;")
        layout.addWidget(lbl_ratio)

        self._ratio_btns = _SegmentedButtons(ASPECT_RATIOS, self._aspect_ratio, self)
        self._ratio_btns.selection_changed.connect(self._on_aspect_ratio_changed)
        layout.addWidget(self._ratio_btns)

        self.setFixedWidth(200)

    def _theme_label(self) -> str:
        return "ライト" if self._theme == "light" else "ダーク"

    def _on_theme_changed(self, label: str) -> None:
        theme = "light" if label == "ライト" else "dark"
        self._theme = theme
        self.theme_changed.emit(theme)

    def _on_aspect_ratio_changed(self, ratio: str) -> None:
        self._aspect_ratio = ratio
        self.aspect_ratio_changed.emit(ratio)

    def popup_below(self, anchor: QWidget) -> None:
        """指定ウィジェットの直下にポップアップ表示する。"""
        pos = anchor.mapToGlobal(anchor.rect().bottomLeft())
        pos.setX(pos.x() - self.sizeHint().width() + anchor.width())
        # 画面右端からはみ出さないよう調整
        if pos.x() < 4:
            pos.setX(4)
        self.move(pos)
        self.exec()
