"""
サムネイルローダー（QThreadPool による非同期ロード）

メインスレッドをブロックせずにサムネイルを生成し、
Signal 経由でコールバックに QPixmap を届ける。
"""

from __future__ import annotations

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtCore import Qt


class _Signals(QObject):
    ready = pyqtSignal(str, QPixmap)   # (path, pixmap)
    failed = pyqtSignal(str)            # (path,)


class _ThumbnailTask(QRunnable):
    def __init__(self, path: str, size: int):
        super().__init__()
        self.path = path
        self.size = size
        self.signals = _Signals()

    def run(self) -> None:
        # ワーカースレッドで実行（QImage の C++ コードは GIL をリリース）
        img = QImage(self.path)
        if img.isNull():
            self.signals.failed.emit(self.path)
            return
        scaled = img.scaled(
            self.size,
            self.size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.signals.ready.emit(self.path, QPixmap.fromImage(scaled))


class ThumbnailLoader(QObject):
    """
    サムネイルを非同期でロードするクラス。

    使い方:
        loader = ThumbnailLoader(size=120, max_threads=4)
        loader.request(path, callback=self.on_thumbnail_ready)

    callback シグネチャ:
        def on_thumbnail_ready(path: str, pixmap: QPixmap) -> None: ...
    """

    def __init__(self, size: int = 120, max_threads: int = 4, parent=None):
        super().__init__(parent)
        self._size = size
        self._pool = QThreadPool()
        self._pool.setMaxThreadCount(max_threads)
        self._cache: dict[str, QPixmap] = {}
        self._pending: dict[str, list] = {}  # path → [callbacks]

    def request(self, path: str, callback) -> None:
        """サムネイルをリクエストする。キャッシュがあれば即時コールバック。"""
        if path in self._cache:
            callback(path, self._cache[path])
            return

        if path in self._pending:
            self._pending[path].append(callback)
            return

        self._pending[path] = [callback]
        task = _ThumbnailTask(path, self._size)
        task.signals.ready.connect(self._on_ready)
        task.signals.failed.connect(self._on_failed)
        self._pool.start(task)

    def _on_ready(self, path: str, pixmap: QPixmap) -> None:
        self._cache[path] = pixmap
        for cb in self._pending.pop(path, []):
            cb(path, pixmap)

    def _on_failed(self, path: str) -> None:
        for cb in self._pending.pop(path, []):
            cb(path, None)

    def clear_cache(self) -> None:
        self._cache.clear()

    def wait_for_done(self) -> None:
        """全タスク完了まで待機（テスト・終了時用）"""
        self._pool.waitForDone()
