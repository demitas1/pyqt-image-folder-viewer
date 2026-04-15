"""
ViewerWindow — ViewerPage 相当（画像ビューア）
"""

from __future__ import annotations

import os
import random
from pathlib import Path

from PyQt6.QtCore import QPoint, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QImage, QKeyEvent, QPainter, QPixmap, QTransform
from PyQt6.QtWidgets import (
    QApplication,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStatusBar,
    QToolBar,
    QWidget,
)

from app.models.profile import Card, CardViewerState, ProfileData, save_profile
from app.utils.image_utils import collect_images
from app.widgets.toast import ToastManager, ToastType


class ImageView(QGraphicsView):
    """画像表示ウィジェット（ズーム・H-Flip 対応）。"""

    clicked = pyqtSignal()
    right_clicked = pyqtSignal(QPoint)  # グローバル座標
    zoom_changed = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene()
        self.setScene(self._scene)
        self._item = QGraphicsPixmapItem()
        self._scene.addItem(self._item)
        self._h_flip = False
        self._zoom = 1.0
        self._ignore_resize = False  # プログラムリサイズ中はfit_zoomをスキップ
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QGraphicsView.Shape.NoFrame)
        self.setBackgroundBrush(Qt.GlobalColor.black)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_image(self, path: str) -> None:
        pixmap = QPixmap(path)
        if pixmap.isNull():
            return
        self._item.setPixmap(pixmap)
        self._scene.setSceneRect(self._item.boundingRect())
        self._fit_zoom()

    def set_h_flip(self, enabled: bool) -> None:
        self._h_flip = enabled
        self._apply_transform()

    def set_zoom(self, zoom: float) -> None:
        self._zoom = zoom
        self._apply_transform()

    def zoom_in(self) -> None:
        self.set_zoom(min(self._zoom * 1.2, 4.0))

    def zoom_out(self) -> None:
        self.set_zoom(max(self._zoom * 0.8, 0.05))

    def _fit_zoom(self) -> None:
        pixmap = self._item.pixmap()
        if pixmap.isNull():
            return
        vw = self.viewport().width()
        vh = self.viewport().height()
        pw = pixmap.width()
        ph = pixmap.height()
        if pw <= 0 or ph <= 0:
            return
        self._zoom = min(vw / pw, vh / ph, 4.0)
        self._apply_transform()
        self.zoom_changed.emit(self._zoom)

    def _apply_transform(self) -> None:
        sx = -self._zoom if self._h_flip else self._zoom
        self.setTransform(QTransform.fromScale(sx, self._zoom))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if not self._ignore_resize:
            self._fit_zoom()

    def keyPressEvent(self, event) -> None:
        # キーイベントは ViewerWindow で一元処理するため親に委譲
        event.ignore()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        elif event.button() == Qt.MouseButton.RightButton:
            self.right_clicked.emit(event.globalPosition().toPoint())
        super().mousePressEvent(event)


class ViewerWindow(QMainWindow):
    """画像ビューアウィンドウ（ViewerPage 相当）。"""

    closed = pyqtSignal()

    def __init__(
        self,
        card: Card,
        profile: ProfileData,
        profile_path: str,
        parent=None,
    ):
        super().__init__(parent)
        self._card = card
        self._profile = profile
        self._profile_path = profile_path
        self._images: list[Path] = []
        self._indices: list[int] = []  # シャッフル時の仮想インデックス
        self._current: int = 0  # _indices 上の位置
        self._h_flip = False
        self._shuffle = False
        self._closing_to_index = False  # 「戻る」操作でのクローズフラグ

        self.setWindowTitle(card.title)
        self._build_ui()
        self._toast = ToastManager(self)
        if os.environ.get("APP_DEBUG"):
            from app.widgets.toast_test_panel import ToastTestPanel
            self._toast_test = ToastTestPanel(self._toast, self)
        self._restore_window()
        self._load_images()

    # ------------------------------------------------------------------
    # UI 構築
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        toolbar = QToolBar()
        self.addToolBar(toolbar)

        btn_back = QPushButton("← 戻る")
        btn_back.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_back.clicked.connect(self._on_back)
        toolbar.addWidget(btn_back)

        self._lbl_title = QLabel()
        toolbar.addWidget(self._lbl_title)
        toolbar.addSeparator()

        self._lbl_zoom = QLabel("100%")
        toolbar.addWidget(self._lbl_zoom)

        self._btn_hflip = QPushButton("H")
        self._btn_hflip.setCheckable(True)
        self._btn_hflip.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_hflip.setToolTip("水平反転 (H)")
        self._btn_hflip.clicked.connect(self._toggle_hflip)
        toolbar.addWidget(self._btn_hflip)

        self._btn_shuffle = QPushButton("R")
        self._btn_shuffle.setCheckable(True)
        self._btn_shuffle.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_shuffle.setToolTip("シャッフル (R)")
        self._btn_shuffle.clicked.connect(self._toggle_shuffle)
        toolbar.addWidget(self._btn_shuffle)

        # 画像表示エリア
        self._image_view = ImageView()
        self._image_view.clicked.connect(self._go_next)
        self._image_view.right_clicked.connect(self._show_context_menu)
        self._image_view.zoom_changed.connect(
            lambda z: self._lbl_zoom.setText(f"{int(z * 100)}%")
        )
        self.setCentralWidget(self._image_view)

        # ステータスバー（ナビゲーション情報）
        self._status = QStatusBar()
        self.setStatusBar(self._status)

    # ------------------------------------------------------------------
    # ウィンドウ状態
    # ------------------------------------------------------------------

    def _restore_window(self) -> None:
        w = self._profile.app_state.viewer_window
        self.resize(w.width, w.height)
        if w.x is not None and w.y is not None:
            self.move(w.x, w.y)

    def _save_window_state(self) -> None:
        geo = self.geometry()
        self._profile.app_state.viewer_window.x = geo.x()
        self._profile.app_state.viewer_window.y = geo.y()
        self._profile.app_state.viewer_window.width = geo.width()
        self._profile.app_state.viewer_window.height = geo.height()

    # ------------------------------------------------------------------
    # 画像ロード
    # ------------------------------------------------------------------

    def _load_images(self) -> None:
        self._images = collect_images(self._card.folder_path, self._card.recursive)
        if not self._images:
            QMessageBox.warning(self, "エラー", "フォルダに画像が見つかりません")
            self._on_back()
            return

        # ビューア状態の復元
        vs = self._card.viewer_state
        start_index = vs.last_image_index if vs else 0
        start_index = min(start_index, len(self._images) - 1)

        # ファイル名の一致確認
        if vs and vs.last_image_filename:
            matched = next(
                (i for i, p in enumerate(self._images)
                 if p.name == vs.last_image_filename),
                None,
            )
            if matched is not None:
                start_index = matched

        self._h_flip = vs.h_flip_enabled if vs else False
        self._shuffle = vs.shuffle_enabled if vs else False
        self._btn_hflip.setChecked(self._h_flip)
        self._btn_shuffle.setChecked(self._shuffle)
        self._image_view.set_h_flip(self._h_flip)

        self._indices = list(range(len(self._images)))
        if self._shuffle:
            random.shuffle(self._indices)
            # 復元インデックスをシャッフル列の先頭に移動
            if start_index in self._indices:
                pos = self._indices.index(start_index)
                self._indices[0], self._indices[pos] = self._indices[pos], self._indices[0]
            self._current = 0
        else:
            self._current = start_index

        self._show_current()

    def _show_current(self) -> None:
        if not self._images:
            return
        real_index = self._indices[self._current]
        path = self._images[real_index]
        self._image_view.set_image(str(path))
        self._lbl_title.setText(f"  {self._card.title} — {path.name}  ")
        total = len(self._images)
        self._status.showMessage(
            f"{self._current + 1} / {total}"
            + ("  (シャッフル)" if self._shuffle else "")
            + "    ←→: ナビゲーション | H: 反転 | R: シャッフル | +/-: ズーム | Space: メニュー | ESC: 戻る"
        )
        self._save_viewer_state()

    # ------------------------------------------------------------------
    # ズーム（ウィンドウ連動）
    # ------------------------------------------------------------------

    def _zoom_and_resize(self, zoom_factor: float) -> None:
        """ズーム率を変更し、ウィンドウサイズを連動リサイズする。"""
        pixmap = self._image_view._item.pixmap()
        if pixmap.isNull():
            return
        pw, ph = pixmap.width(), pixmap.height()

        new_zoom = min(self._image_view._zoom * zoom_factor, 4.0)

        # chrome 高 = ウィンドウ高 − ビューポート高
        chrome_h = self.height() - self._image_view.viewport().height()

        new_w = int(pw * new_zoom)
        new_h = int(ph * new_zoom) + chrome_h

        # 最小サイズクランプ
        new_w = max(new_w, 200)
        new_h = max(new_h, 200)

        # 最大サイズクランプ（スクリーンサイズ）
        screen = QApplication.primaryScreen()
        if screen:
            avail = screen.availableGeometry()
            new_w = min(new_w, avail.width())
            new_h = min(new_h, avail.height())

        # クランプ後のズーム率を再計算
        effective_zoom = min(new_w / pw, (new_h - chrome_h) / ph)
        effective_zoom = max(effective_zoom, 0.01)

        # プログラムリサイズ中は resizeEvent の fit_zoom をスキップ
        self._image_view._ignore_resize = True
        self.resize(new_w, new_h)
        self._image_view.set_zoom(effective_zoom)
        QTimer.singleShot(0, lambda: setattr(self._image_view, '_ignore_resize', False))

        self._lbl_zoom.setText(f"{int(effective_zoom * 100)}%")

    # ------------------------------------------------------------------
    # ナビゲーション
    # ------------------------------------------------------------------

    def _go_next(self) -> None:
        if not self._images:
            return
        self._current = (self._current + 1) % len(self._images)
        self._show_current()

    def _go_prev(self) -> None:
        if not self._images:
            return
        self._current = (self._current - 1) % len(self._images)
        self._show_current()

    def _toggle_hflip(self) -> None:
        self._h_flip = not self._h_flip
        self._btn_hflip.setChecked(self._h_flip)
        self._image_view.set_h_flip(self._h_flip)
        self._save_viewer_state()

    def _toggle_shuffle(self) -> None:
        self._shuffle = not self._shuffle
        self._btn_shuffle.setChecked(self._shuffle)
        if self._shuffle:
            real_current = self._indices[self._current]
            self._indices = list(range(len(self._images)))
            random.shuffle(self._indices)
            # 現在表示中の画像を先頭に
            pos = self._indices.index(real_current)
            self._indices[0], self._indices[pos] = self._indices[pos], self._indices[0]
            self._current = 0
        else:
            real_current = self._indices[self._current]
            self._indices = list(range(len(self._images)))
            self._current = real_current
        self._show_current()

    # ------------------------------------------------------------------
    # 状態保存
    # ------------------------------------------------------------------

    def _save_viewer_state(self) -> None:
        if not self._images:
            return
        real_index = self._indices[self._current]
        self._card.viewer_state = CardViewerState(
            last_image_index=real_index,
            last_image_filename=self._images[real_index].name,
            h_flip_enabled=self._h_flip,
            shuffle_enabled=self._shuffle,
        )
        self._profile.app_state.last_page = "viewer"
        self._profile.app_state.last_card_id = self._card.id
        try:
            save_profile(self._profile_path, self._profile)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # コンテキストメニュー
    # ------------------------------------------------------------------

    def _show_context_menu(self, global_pos: QPoint) -> None:
        """コンテキストメニューを表示する（右クリック・Space）。"""
        menu = QMenu(self)

        # 現在の画像パスを取得
        if self._images:
            real_index = self._indices[self._current]
            image_path = str(self._images[real_index])

            act_copy_image = menu.addAction("コピー")
            act_copy_path = menu.addAction("パスをコピー")
            menu.addSeparator()
        else:
            act_copy_image = None
            act_copy_path = None
            image_path = None

        hflip_label = f"水平反転: {'OFF' if self._h_flip else 'ON'}"
        act_hflip = menu.addAction(f"{hflip_label}\tH")

        shuffle_label = f"シャッフル: {'OFF' if self._shuffle else 'ON'}"
        act_shuffle = menu.addAction(f"{shuffle_label}\tR")

        menu.addSeparator()
        act_zoom_in = menu.addAction("ズームイン\t+")
        act_zoom_out = menu.addAction("ズームアウト\t-")

        menu.addSeparator()
        act_back = menu.addAction("インデックスに戻る\tESC")
        act_quit = menu.addAction("終了\tQ")

        action = menu.exec(global_pos)
        if action is None:
            return

        if action == act_copy_image and image_path:
            self._copy_image_to_clipboard(image_path)
        elif action == act_copy_path and image_path:
            self._copy_path_to_clipboard(image_path)
        elif action == act_hflip:
            self._toggle_hflip()
        elif action == act_shuffle:
            self._toggle_shuffle()
        elif action == act_zoom_in:
            self._zoom_and_resize(1.2)
        elif action == act_zoom_out:
            self._zoom_and_resize(0.8)
        elif action == act_back:
            self._on_back()
        elif action == act_quit:
            self._on_quit()

    def _copy_image_to_clipboard(self, path: str) -> None:
        """画像をクリップボードにコピーする。"""
        image = QImage(path)
        if image.isNull():
            self._toast.add_toast("画像の読み込みに失敗しました", ToastType.ERROR)
            return
        QApplication.clipboard().setImage(image)
        self._toast.add_toast("画像をコピーしました", ToastType.SUCCESS)

    def _copy_path_to_clipboard(self, path: str) -> None:
        """パスをクリップボードにコピーする。"""
        QApplication.clipboard().setText(path)
        self._toast.add_toast("パスをコピーしました", ToastType.SUCCESS)

    # ------------------------------------------------------------------
    # 戻る
    # ------------------------------------------------------------------

    def _on_back(self) -> None:
        """IndexPage に戻る（「戻る」ボタン・Escape）。"""
        self._closing_to_index = True
        self._profile.app_state.last_page = "index"
        try:
            save_profile(self._profile_path, self._profile)
        except Exception:
            pass
        self.close()

    def _on_quit(self) -> None:
        """アプリケーションを終了する（Q キー・X ボタン）。"""
        self._save_window_state()
        self._save_viewer_state()
        QApplication.quit()

    # ------------------------------------------------------------------
    # キーボードショートカット
    # ------------------------------------------------------------------

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self._on_back()
        elif key == Qt.Key.Key_Q:
            self._on_quit()
        elif key == Qt.Key.Key_Left:
            self._go_prev()
        elif key == Qt.Key.Key_Right:
            self._go_next()
        elif key in (Qt.Key.Key_H,):
            self._toggle_hflip()
        elif key in (Qt.Key.Key_R,):
            self._toggle_shuffle()
        elif key in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
            self._zoom_and_resize(1.2)
        elif key == Qt.Key.Key_Minus:
            self._zoom_and_resize(0.8)
        elif key == Qt.Key.Key_Space:
            # ウィンドウ中央にコンテキストメニューを表示
            center = self.rect().center()
            self._show_context_menu(self.mapToGlobal(center))
        else:
            super().keyPressEvent(event)

    # ------------------------------------------------------------------
    # ウィンドウイベント
    # ------------------------------------------------------------------

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.activateWindow()
        self._image_view.setFocus()

    def closeEvent(self, event) -> None:
        self._save_window_state()
        if self._closing_to_index:
            # 「戻る」操作: MainWindow に制御を返す
            self.closed.emit()
        else:
            # X ボタンによる直接クローズ: アプリ終了
            self._save_viewer_state()
            QApplication.quit()
        event.accept()
