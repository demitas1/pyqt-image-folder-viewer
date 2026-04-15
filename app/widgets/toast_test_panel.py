"""
トーストテストパネル（APP_DEBUG=1 時のみ使用）。

デバッグ時に画面左上（ツールバー下）に表示し、
各タイプのトーストを手動テストできる小パネル。
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from app.widgets.toast import ToastManager, ToastType


class ToastTestPanel(QWidget):
    """トースト通知テストパネル（デバッグ用）。"""

    def __init__(self, toast_manager: ToastManager, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.SubWindow)
        self.setStyleSheet(
            "background-color: rgba(40, 40, 40, 220);"
            " border: 1px solid #666;"
            " border-radius: 4px;"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        lbl = QLabel("Toast Test")
        lbl.setStyleSheet("color: #aaa; font-size: 10px; background: transparent;")
        layout.addWidget(lbl)

        tests: list[tuple[str, str, ToastType]] = [
            ("✓ Success", "クリップボードにコピーしました", ToastType.SUCCESS),
            ("✗ Error",   "保存に失敗しました",             ToastType.ERROR),
            ("ℹ Info",    "情報: 処理が完了しました",        ToastType.INFO),
        ]
        for label, msg, toast_type in tests:
            btn = QPushButton(label)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.clicked.connect(
                lambda _checked, m=msg, t=toast_type: toast_manager.add_toast(m, t)
            )
            layout.addWidget(btn)

        btn_multi = QPushButton("複数同時")
        btn_multi.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        def _show_multi() -> None:
            toast_manager.add_toast("画像をコピーしました", ToastType.SUCCESS)
            toast_manager.add_toast("保存に失敗しました", ToastType.ERROR)
            toast_manager.add_toast("処理中です...", ToastType.INFO)

        btn_multi.clicked.connect(_show_multi)
        layout.addWidget(btn_multi)

        self.adjustSize()
        self.move(8, 48)  # ツールバー下・左端
        self.show()
        self.raise_()
