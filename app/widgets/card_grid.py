"""
CardGrid — カードのグリッド表示（QListView + カスタムデリゲート）
サムネイルは ThumbnailLoader で非同期ロード。
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import (
    QAbstractListModel,
    QModelIndex,
    QSize,
    Qt,
    pyqtSignal,
)
from PyQt6.QtGui import QColor, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QListView,
    QMenu,
    QMessageBox,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QVBoxLayout,
    QWidget,
)

from app.models.profile import Card, ProfileData
from app.utils import theme as theme_mod
from app.widgets.thumbnail_loader import ThumbnailLoader

# サムネイル高さ固定・最大幅（16:9）でキャッシュ生成
THUMB_H = 180
THUMBNAIL_SIZE = 320   # 常に最大サイズ（16:9 の thumb_w）でキャッシュ
CARD_HEIGHT = 236      # 4 + THUMB_H + 8 + タイトル40 + 4

ASPECT_RATIO_MAP: dict[str, tuple[int, int]] = {
    "16:9": (16, 9),
    "4:3":  (4, 3),
    "1:1":  (1, 1),
}
DEFAULT_ASPECT_RATIO = "16:9"


def _thumb_w(ratio: str) -> int:
    r = ASPECT_RATIO_MAP.get(ratio, ASPECT_RATIO_MAP[DEFAULT_ASPECT_RATIO])
    return int(THUMB_H * r[0] / r[1])


def _card_width(ratio: str) -> int:
    return _thumb_w(ratio) + 8


class CardModel(QAbstractListModel):
    """カード一覧の Qt モデル。"""

    def __init__(self, profile: ProfileData, parent=None):
        super().__init__(parent)
        self._profile = profile

    @property
    def cards(self) -> list[Card]:
        return self._profile.cards

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._profile.cards)

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self._profile.cards):
            return None
        card = self._profile.cards[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return card.title
        if role == Qt.ItemDataRole.UserRole:
            return card
        return None

    def flags(self, index: QModelIndex):
        default = super().flags(index)
        return default | Qt.ItemFlag.ItemIsDragEnabled | Qt.ItemFlag.ItemIsDropEnabled

    def refresh(self) -> None:
        self.beginResetModel()
        self.endResetModel()


class CardDelegate(QStyledItemDelegate):
    """カードの描画デリゲート。"""

    def __init__(self, loader: ThumbnailLoader, view: QListView, aspect_ratio: str, parent=None):
        super().__init__(parent)
        self._loader = loader
        self._view = view
        self._pixmaps: dict[str, QPixmap | None] = {}
        self._thumb_w = _thumb_w(aspect_ratio)

    def set_aspect_ratio(self, ratio: str) -> None:
        self._thumb_w = _thumb_w(ratio)

    def sizeHint(self, option, index) -> QSize:
        return QSize(self._thumb_w + 8, CARD_HEIGHT)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        card: Card = index.data(Qt.ItemDataRole.UserRole)
        if not card:
            return

        rect = option.rect
        is_selected = bool(option.state & QStyle.StateFlag.State_Selected)

        # テーマ色を取得
        colors = theme_mod.card_colors()

        # 背景
        bg_color = QColor(colors["card_bg_sel"]) if is_selected else QColor(colors["card_bg"])
        painter.fillRect(rect, bg_color)

        # サムネイル領域
        thumb_rect = rect.adjusted(4, 4, -4, -(CARD_HEIGHT - THUMB_H - 4))

        if card.thumbnail and card.thumbnail not in self._pixmaps:
            # 初回リクエスト
            self._pixmaps[card.thumbnail] = None  # ロード中マーカー
            self._loader.request(card.thumbnail, self._on_thumbnail_ready)

        pixmap = self._pixmaps.get(card.thumbnail) if card.thumbnail else None
        if pixmap:
            scaled = pixmap.scaled(
                thumb_rect.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            # センタークリップ
            x_off = (scaled.width() - thumb_rect.width()) // 2
            y_off = (scaled.height() - thumb_rect.height()) // 2
            painter.drawPixmap(
                thumb_rect,
                scaled,
                scaled.rect().adjusted(x_off, y_off, -x_off, -y_off),
            )
        else:
            # サムネイルなし
            painter.fillRect(thumb_rect, QColor(colors["thumb_bg"]))
            painter.setPen(QColor(colors["icon_fg"]))
            painter.drawText(thumb_rect, Qt.AlignmentFlag.AlignCenter, "📁")

        # タイトル
        title_rect = rect.adjusted(4, THUMB_H + 8, -4, -4)
        painter.setPen(QColor(colors["title_fg"]))
        painter.drawText(
            title_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
            card.title,
        )

    def _on_thumbnail_ready(self, path: str, pixmap: QPixmap | None) -> None:
        self._pixmaps[path] = pixmap
        self._view.viewport().update()


class CardGrid(QWidget):
    """カードグリッドウィジェット（IndexPage のメインコンテンツ）。"""

    card_opened = pyqtSignal(object)   # Card
    profile_changed = pyqtSignal()

    def __init__(self, profile: ProfileData, aspect_ratio: str = DEFAULT_ASPECT_RATIO, parent=None):
        super().__init__(parent)
        self._profile = profile
        self._aspect_ratio = aspect_ratio
        self._loader = ThumbnailLoader(size=THUMBNAIL_SIZE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        self._model = CardModel(profile)

        self._view = QListView()
        self._delegate = CardDelegate(
            self._loader, view=self._view, aspect_ratio=aspect_ratio, parent=self
        )
        self._view.setModel(self._model)
        self._view.setItemDelegate(self._delegate)
        self._view.setViewMode(QListView.ViewMode.IconMode)
        self._view.setResizeMode(QListView.ResizeMode.Adjust)
        self._view.setSpacing(8)
        self._view.setDragDropMode(QListView.DragDropMode.InternalMove)
        self._view.setDefaultDropAction(Qt.DropAction.MoveAction)
        self._view.setGridSize(QSize(_card_width(aspect_ratio) + 8, CARD_HEIGHT + 8))
        self._view.activated.connect(self._on_double_click)
        self._view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._view.customContextMenuRequested.connect(self._on_context_menu)

        layout.addWidget(self._view)

    def current_card(self) -> Card | None:
        """現在選択中のカードを返す。未選択の場合は None。"""
        index = self._view.currentIndex()
        if not index.isValid():
            return None
        return index.data(Qt.ItemDataRole.UserRole)

    def delete_selected(self) -> None:
        """選択中のカードを削除する（確認ダイアログあり）。"""
        card = self.current_card()
        if card:
            self._on_delete(card)

    def select_card_by_id(self, card_id: str) -> None:
        """指定 ID のカードを選択状態にしてスクロールする。"""
        for row, card in enumerate(self._profile.cards):
            if card.id == card_id:
                index = self._model.index(row, 0)
                self._view.setCurrentIndex(index)
                self._view.scrollTo(index)
                return

    def set_focus(self) -> None:
        """内部の QListView にフォーカスを移す。"""
        self._view.setFocus()

    def set_profile(self, profile: ProfileData) -> None:
        """プロファイルを切り替えてグリッドを更新する。"""
        self._profile = profile
        self._model._profile = profile
        self._delegate._pixmaps.clear()
        self._model.refresh()

    def set_aspect_ratio(self, ratio: str) -> None:
        """アスペクト比を変更してグリッドを再描画する。キャッシュ無効化は不要。"""
        self._aspect_ratio = ratio
        self._delegate.set_aspect_ratio(ratio)
        self._view.setGridSize(QSize(_card_width(ratio) + 8, CARD_HEIGHT + 8))
        self._view.viewport().update()

    def refresh(self) -> None:
        self._model.refresh()

    def _on_double_click(self, index: QModelIndex) -> None:
        card: Card = index.data(Qt.ItemDataRole.UserRole)
        if card and Path(card.folder_path).exists():
            self.card_opened.emit(card)

    def _on_context_menu(self, pos) -> None:
        index = self._view.indexAt(pos)
        if not index.isValid():
            return
        card: Card = index.data(Qt.ItemDataRole.UserRole)
        menu = QMenu(self)
        menu.addAction("編集", lambda: self._on_edit(card))
        menu.addAction("削除", lambda: self._on_delete(card))
        menu.exec(self._view.viewport().mapToGlobal(pos))

    def _on_edit(self, card: Card) -> None:
        from app.windows.card_dialog import CardDialog

        dlg = CardDialog(card=card, parent=self)
        if dlg.exec():
            updated = dlg.result_card()
            card.title = updated.title
            card.folder_path = updated.folder_path
            card.thumbnail = updated.thumbnail
            card.recursive = updated.recursive
            self._model.refresh()
            self.profile_changed.emit()

    def _on_delete(self, card: Card) -> None:
        ret = QMessageBox.question(
            self,
            "カードの削除",
            f"「{card.title}」を削除しますか？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ret == QMessageBox.StandardButton.Yes:
            self._profile.cards.remove(card)
            self._model.refresh()
            self.profile_changed.emit()
