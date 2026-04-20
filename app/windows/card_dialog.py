"""
CardDialog — カード追加・編集ダイアログ
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from app.models.profile import Card


class CardDialog(QDialog):
    """カード追加・編集ダイアログ。"""

    def __init__(self, card: Card | None = None, parent=None):
        super().__init__(parent)
        self._card = card
        self.setWindowTitle("カードを編集" if card else "カードを追加")
        self.setMinimumWidth(480)
        self._build_ui()
        if card:
            self._populate(card)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._title_edit = QLineEdit()
        form.addRow("タイトル", self._title_edit)

        # フォルダパス
        folder_row = QHBoxLayout()
        self._folder_edit = QLineEdit()
        self._folder_edit.textChanged.connect(self._on_folder_text_changed)
        btn_folder = QPushButton("参照...")
        btn_folder.clicked.connect(self._on_browse_folder)
        folder_row.addWidget(self._folder_edit)
        folder_row.addWidget(btn_folder)
        form.addRow("フォルダ", folder_row)

        # サムネイル
        thumb_row = QHBoxLayout()
        self._thumb_edit = QLineEdit()
        self._thumb_edit.setPlaceholderText("（未設定）")
        self._thumb_edit.textChanged.connect(self._on_thumb_text_changed)
        btn_thumb = QPushButton("選択...")
        btn_thumb.clicked.connect(self._on_browse_thumbnail)
        thumb_row.addWidget(self._thumb_edit)
        thumb_row.addWidget(btn_thumb)
        form.addRow("サムネイル", thumb_row)

        # サブディレクトリ
        self._recursive_check = QCheckBox("サブディレクトリを含む")
        form.addRow("", self._recursive_check)

        layout.addLayout(form)

        # OK / キャンセル
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._ok_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _populate(self, card: Card) -> None:
        self._title_edit.setText(card.title)
        self._folder_edit.setText(card.folder_path)
        self._thumb_edit.setText(card.thumbnail or "")
        self._recursive_check.setChecked(card.recursive)
        self._update_ok_state()

    def _on_folder_text_changed(self, text: str) -> None:
        from pathlib import Path
        invalid = bool(text and not Path(text).is_dir())
        self._folder_edit.setStyleSheet("QLineEdit { border: 1px solid red; }" if invalid else "")
        self._update_ok_state()

    def _on_thumb_text_changed(self, text: str) -> None:
        from pathlib import Path
        invalid = bool(text and not Path(text).is_file())
        self._thumb_edit.setStyleSheet("QLineEdit { border: 1px solid red; }" if invalid else "")
        self._update_ok_state()

    def _update_ok_state(self) -> None:
        from pathlib import Path
        folder = self._folder_edit.text()
        thumb = self._thumb_edit.text()
        folder_ok = bool(folder) and Path(folder).is_dir()
        thumb_ok = not thumb or Path(thumb).is_file()
        self._ok_btn.setEnabled(folder_ok and thumb_ok)

    def _on_browse_folder(self) -> None:
        from app.widgets.image_picker import ImagePickerDialog

        start = self._folder_edit.text() or ""
        dlg = ImagePickerDialog(start_path=start, mode="folder", parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            path = dlg.selected_path()
            if path:
                self._folder_edit.setText(path)
                if not self._title_edit.text():
                    import os
                    self._title_edit.setText(os.path.basename(path))

    def _on_browse_thumbnail(self) -> None:
        from app.widgets.image_picker import ImagePickerDialog

        start = self._thumb_edit.text() or self._folder_edit.text() or ""
        dlg = ImagePickerDialog(start_path=start, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            path = dlg.selected_path()
            if path:
                self._thumb_edit.setText(path)

    def result_card(self) -> Card:
        """ダイアログの入力内容を反映した Card を返す。"""
        base = self._card or Card()
        base.title = self._title_edit.text().strip()
        base.folder_path = self._folder_edit.text().strip()
        base.thumbnail = self._thumb_edit.text().strip() or None
        base.recursive = self._recursive_check.isChecked()
        return base
