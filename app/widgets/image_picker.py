"""
ImagePickerDialog — サムネイル付き画像選択ダイアログ

フォルダ内の画像・サブフォルダをグリッド表示し、画像のパスを返す。
ThumbnailLoader で非同期サムネイルロード（UIフリーズなし）。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import QAbstractListModel, QModelIndex, QSize, Qt, QTimer
from PyQt6.QtGui import QColor, QKeyEvent, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QPushButton,
    QSizePolicy,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QVBoxLayout,
)

from app.widgets.thumbnail_loader import shared_loader

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}

# アドレスバーのデバウンス待機時間（ms）
_ADDRESS_DEBOUNCE_MS = 300

# サムネイル表示サイズ（正方形）とロードサイズ
_THUMB_PX = 120
_LOADER_SIZE = 160   # shared_loader に渡すキャッシュサイズ（表示より少し大きく）
_LABEL_H = 20
_ITEM_W = _THUMB_PX + 8
_ITEM_H = 4 + _THUMB_PX + 4 + _LABEL_H + 4
_GRID_SIZE = QSize(_ITEM_W + 8, _ITEM_H + 8)


@dataclass
class _PickerItem:
    path: str
    name: str
    is_folder: bool


class _PickerModel(QAbstractListModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: list[_PickerItem] = []

    def set_items(self, items: list[_PickerItem]) -> None:
        self.beginResetModel()
        self._items = items
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._items)

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self._items):
            return None
        item = self._items[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return item.name
        if role == Qt.ItemDataRole.UserRole:
            return item
        return None


class _PickerDelegate(QStyledItemDelegate):
    """フォルダ・画像タイルの描画デリゲート。"""

    def __init__(self, view: QListView, parent=None):
        super().__init__(parent)
        self._view = view
        self._loader = shared_loader(_LOADER_SIZE)
        self._pixmaps: dict[str, QPixmap | None] = {}

    def sizeHint(self, option, index) -> QSize:
        return QSize(_ITEM_W, _ITEM_H)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        item: _PickerItem = index.data(Qt.ItemDataRole.UserRole)
        if not item:
            return

        rect = option.rect
        is_selected = bool(option.state & QStyle.StateFlag.State_Selected)
        palette = option.palette

        # 背景
        bg = palette.highlight().color() if is_selected else palette.base().color()
        painter.fillRect(rect, bg)

        # サムネイル領域（ラベル分を下から除く）
        thumb_rect = rect.adjusted(4, 4, -4, -(4 + _LABEL_H + 4))

        if item.is_folder:
            painter.fillRect(thumb_rect, palette.mid().color())
            old_font = painter.font()
            font = painter.font()
            font.setPointSize(32)
            painter.setFont(font)
            painter.setPen(palette.text().color())
            painter.drawText(thumb_rect, Qt.AlignmentFlag.AlignCenter, "📁")
            painter.setFont(old_font)
        else:
            if item.path not in self._pixmaps:
                self._pixmaps[item.path] = None
                self._loader.request(item.path, self._on_thumbnail_ready)

            pixmap = self._pixmaps.get(item.path)
            if pixmap:
                scaled = pixmap.scaled(
                    thumb_rect.size(),
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
                x_off = (scaled.width() - thumb_rect.width()) // 2
                y_off = (scaled.height() - thumb_rect.height()) // 2
                painter.drawPixmap(
                    thumb_rect,
                    scaled,
                    scaled.rect().adjusted(x_off, y_off, -x_off, -y_off),
                )
            else:
                painter.fillRect(thumb_rect, palette.mid().color())
                painter.setPen(palette.placeholderText().color())
                painter.drawText(thumb_rect, Qt.AlignmentFlag.AlignCenter, "🖼")

        # 選択枠
        if is_selected:
            pen = painter.pen()
            pen.setColor(QColor("#3b82f6"))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(thumb_rect.adjusted(1, 1, -1, -1))
            painter.setPen(palette.highlightedText().color())
        else:
            painter.setPen(palette.text().color())

        # ファイル名（下部ラベル）
        label_rect = rect.adjusted(2, _ITEM_H - _LABEL_H - 4, -2, -4)
        fm = painter.fontMetrics()
        elided = fm.elidedText(item.name, Qt.TextElideMode.ElideRight, label_rect.width())
        painter.drawText(
            label_rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter, elided
        )

    def _on_thumbnail_ready(self, path: str, pixmap: QPixmap | None) -> None:
        self._pixmaps[path] = pixmap
        self._view.viewport().update()


class ImagePickerDialog(QDialog):
    """フォルダ内の画像・フォルダをグリッドで表示して選択するダイアログ。

    mode="image"（デフォルト）: 画像ファイルを選択して返す
    mode="folder": フォルダのみ表示し、フォルダパスを返す
    """

    def __init__(self, start_path: str = "", mode: str = "image",
                 address_debounce_ms: int = _ADDRESS_DEBOUNCE_MS, parent=None):
        super().__init__(parent)
        self._mode = mode
        self._debounce_ms = address_debounce_ms
        self._address_valid = True
        self.setWindowTitle("フォルダを選択" if mode == "folder" else "サムネイル画像を選択")
        self.setMinimumSize(640, 520)
        self._selected_path: str | None = None
        self._current_dir: Path = self._resolve_start(start_path)
        self._build_ui()
        self._navigate(self._current_dir)

    # ------------------------------------------------------------------
    # UI 構築
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # ナビゲーションバー
        nav = QHBoxLayout()
        self._btn_up = QPushButton("↑ 上へ")
        self._btn_up.setFixedWidth(80)
        self._btn_up.clicked.connect(self._on_go_up)
        self._address_bar = QLineEdit()
        self._address_bar.setPlaceholderText("パスを入力して Enter")
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.timeout.connect(self._on_address_validate)
        self._address_bar.textChanged.connect(
            lambda: self._debounce_timer.start(self._debounce_ms)
        )
        self._address_bar.returnPressed.connect(self._on_address_committed)
        nav.addWidget(self._btn_up)
        nav.addWidget(self._address_bar)
        layout.addLayout(nav)

        # グリッドビュー
        self._model = _PickerModel(self)
        self._view = QListView()
        self._delegate = _PickerDelegate(self._view, self)
        self._view.setModel(self._model)
        self._view.setItemDelegate(self._delegate)
        self._view.setViewMode(QListView.ViewMode.IconMode)
        self._view.setResizeMode(QListView.ResizeMode.Adjust)
        self._view.setSpacing(4)
        self._view.setGridSize(_GRID_SIZE)
        self._view.setUniformItemSizes(True)
        self._view.clicked.connect(self._on_item_clicked)
        self._view.doubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self._view)

        # 選択中パス表示
        self._selection_label = QLabel("選択中: （未選択）")
        self._selection_label.setWordWrap(True)
        layout.addWidget(self._selection_label)

        # ボタン
        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        ok_btn = self._buttons.button(QDialogButtonBox.StandardButton.Ok)
        cancel_btn = self._buttons.button(QDialogButtonBox.StandardButton.Cancel)
        ok_btn.setText("決定")
        cancel_btn.setText("キャンセル")
        # アドレスバーの Enter がダイアログ OK に伝播しないよう autoDefault を無効化
        ok_btn.setAutoDefault(False)
        ok_btn.setDefault(False)
        cancel_btn.setAutoDefault(False)
        self._ok_btn = ok_btn
        # フォルダモードは OK を常に有効（未選択時は現在ディレクトリを返す）
        ok_btn.setEnabled(self._mode == "folder")
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)

    # ------------------------------------------------------------------
    # ナビゲーション
    # ------------------------------------------------------------------

    def _resolve_start(self, start_path: str) -> Path:
        if start_path:
            p = Path(start_path)
            if p.is_dir():
                return p
            if p.is_file():
                return p.parent
        return Path.home()

    def _navigate(self, directory: Path) -> None:
        self._current_dir = directory
        self._debounce_timer.stop()
        self._address_bar.blockSignals(True)
        self._address_bar.setText(str(directory))
        self._address_bar.blockSignals(False)
        self._address_bar.setStyleSheet("")
        self._btn_up.setEnabled(directory.parent != directory)

        items: list[_PickerItem] = []
        try:
            entries = sorted(
                directory.iterdir(),
                key=lambda p: (not p.is_dir(), p.name.lower()),
            )
        except PermissionError:
            entries = []

        for entry in entries:
            if entry.name.startswith("."):
                continue
            if entry.is_dir():
                items.append(_PickerItem(str(entry), entry.name, is_folder=True))
            elif self._mode == "image" and entry.suffix.lower() in IMAGE_EXTENSIONS:
                items.append(_PickerItem(str(entry), entry.name, is_folder=False))

        self._model.set_items(items)
        self._view.clearSelection()

        # フォルダモードでは現在ディレクトリを選択状態にする
        if self._mode == "folder":
            self._selected_path = str(directory)
            name = directory.name or str(directory)
            self._selection_label.setText(f"選択中: {name}")

    # ------------------------------------------------------------------
    # スロット
    # ------------------------------------------------------------------

    def _on_go_up(self) -> None:
        self._navigate(self._current_dir.parent)

    def _on_address_validate(self) -> None:
        """デバウンス後にバリデートのみ実施（ナビゲートしない）。"""
        p = Path(self._address_bar.text().strip())
        self._address_valid = p.is_dir()
        self._address_bar.setStyleSheet(
            "" if self._address_valid else "QLineEdit { border: 1px solid red; }"
        )
        self._update_ok_btn()

    def _on_address_committed(self) -> None:
        """Enter 押下時：タイマーをキャンセルしてナビゲートを試みる。"""
        self._debounce_timer.stop()
        p = Path(self._address_bar.text().strip())
        if p.is_dir():
            self._navigate(p)
        else:
            self._address_valid = False
            self._address_bar.setStyleSheet("QLineEdit { border: 1px solid red; }")
            self._update_ok_btn()

    def _update_ok_btn(self) -> None:
        if self._mode == "folder":
            self._ok_btn.setEnabled(self._address_valid)
        else:
            has_selection = bool(self._selected_path)
            self._ok_btn.setEnabled(self._address_valid and has_selection)

    def _on_item_clicked(self, index: QModelIndex) -> None:
        item: _PickerItem = index.data(Qt.ItemDataRole.UserRole)
        if not item:
            return
        if self._mode == "folder" and item.is_folder:
            self._selected_path = item.path
            self._selection_label.setText(f"選択中: {item.name}")
        elif self._mode == "image" and not item.is_folder:
            self._selected_path = item.path
            self._selection_label.setText(f"選択中: {item.name}")
            self._update_ok_btn()

    def _on_item_double_clicked(self, index: QModelIndex) -> None:
        item: _PickerItem = index.data(Qt.ItemDataRole.UserRole)
        if not item:
            return
        if item.is_folder:
            self._navigate(Path(item.path))
        else:
            self._selected_path = item.path
            self.accept()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        # アドレスバー入力中の Enter/Return を QDialog::keyPressEvent に伝播させない
        if (event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
                and self._address_bar.hasFocus()):
            event.accept()
            return
        super().keyPressEvent(event)

    # ------------------------------------------------------------------
    # 結果取得
    # ------------------------------------------------------------------

    def selected_path(self) -> str | None:
        return self._selected_path
