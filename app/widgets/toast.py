"""
トースト通知システム。

ToastType : SUCCESS / ERROR / INFO
ToastItem : 1件のトースト表示ウィジェット（3秒後自動消去）
ToastManager : 親ウィンドウの右下にトーストを積み上げ配置する管理クラス
"""

from __future__ import annotations

from enum import Enum, auto

from PyQt6.QtCore import QEvent, QObject, Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QWidget


class ToastType(Enum):
    SUCCESS = auto()
    ERROR = auto()
    INFO = auto()


class ToastItem(QFrame):
    """1件のトースト表示ウィジェット。"""

    dismissed = pyqtSignal()

    TOAST_WIDTH = 300
    TOAST_HEIGHT = 48
    AUTO_DISMISS_MS = 3000

    _FRAME_STYLES = {
        ToastType.SUCCESS: "background-color: #1e5c1e; color: #ccf0cc;",
        ToastType.ERROR:   "background-color: #7a1515; color: #ffd0d0;",
        ToastType.INFO:    "background-color: #3a3a3a; color: #e8e8e8;",
    }
    _CLOSE_STYLES = {
        ToastType.SUCCESS: "background: transparent; border: none; color: #ccf0cc; font-weight: bold;",
        ToastType.ERROR:   "background: transparent; border: none; color: #ffd0d0; font-weight: bold;",
        ToastType.INFO:    "background: transparent; border: none; color: #e8e8e8; font-weight: bold;",
    }

    def __init__(self, message: str, toast_type: ToastType, parent: QWidget) -> None:
        super().__init__(parent)
        frame_css = self._FRAME_STYLES[toast_type]
        close_css = self._CLOSE_STYLES[toast_type]
        self.setStyleSheet(f"QFrame {{ {frame_css} border-radius: 6px; }}")
        self.setFixedSize(self.TOAST_WIDTH, self.TOAST_HEIGHT)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 4, 8, 4)
        layout.setSpacing(8)

        lbl = QLabel(message)
        lbl.setStyleSheet("background: transparent;")
        lbl.setWordWrap(False)
        layout.addWidget(lbl, 1)

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(20, 20)
        btn_close.setStyleSheet(close_css)
        btn_close.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_close.clicked.connect(self._dismiss)
        layout.addWidget(btn_close)

        QTimer.singleShot(self.AUTO_DISMISS_MS, self._dismiss)

        self.raise_()
        self.show()

    def _dismiss(self) -> None:
        if not self.isVisible():
            return  # 二重呼び出し防止
        self.hide()
        self.dismissed.emit()


class ToastManager(QObject):
    """トースト管理クラス。親ウィンドウの右下にトーストを積み上げ配置する。"""

    MARGIN = 12
    SPACING = 6

    def __init__(self, parent_window: QWidget) -> None:
        super().__init__(parent_window)
        self._parent = parent_window
        self._toasts: list[ToastItem] = []
        parent_window.installEventFilter(self)

    def add_toast(self, message: str, toast_type: ToastType = ToastType.INFO) -> None:
        """トーストを追加して右下に表示する。"""
        toast = ToastItem(message, toast_type, self._parent)
        self._toasts.append(toast)
        toast.dismissed.connect(lambda: self._on_dismissed(toast))
        self._reposition()

    def _on_dismissed(self, toast: ToastItem) -> None:
        self._toasts = [t for t in self._toasts if t is not toast]
        self._reposition()

    def _reposition(self) -> None:
        """アクティブなトーストを右下から積み上げ配置する。"""
        active = [t for t in self._toasts if t.isVisible()]
        pw = self._parent.width()
        ph = self._parent.height()
        x = pw - ToastItem.TOAST_WIDTH - self.MARGIN
        y = ph - self.MARGIN

        for toast in reversed(active):
            y -= toast.height()
            toast.move(x, y)
            y -= self.SPACING

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if obj is self._parent and event.type() in (
            QEvent.Type.Resize,
            QEvent.Type.Move,
        ):
            self._reposition()
        return False
