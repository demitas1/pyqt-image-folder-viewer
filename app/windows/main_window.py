"""
MainWindow — IndexPage 相当（カードグリッド表示）
"""

from __future__ import annotations

import os
from pathlib import Path

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QStatusBar,
    QToolBar,
    QWidget,
)

from PyQt6.QtWidgets import QApplication

from app.models.app_config import AppConfig, add_recent_profile, save_app_config
from app.models.profile import (
    Card,
    ProfileData,
    create_empty_profile,
    load_profile,
    save_profile,
)
from app.utils import theme as theme_mod
from app.widgets.card_grid import CardGrid
from app.widgets.settings_panel import SettingsPanel
from app.widgets.toast import ToastManager, ToastType


class MainWindow(QMainWindow):
    """カードグリッドを表示するメインウィンドウ（IndexPage 相当）。"""

    def __init__(
        self,
        profile: ProfileData,
        profile_path: str,
        config: AppConfig,
        parent=None,
    ):
        super().__init__(parent)
        self._profile = profile
        self._profile_path = profile_path
        self._config = config

        self.setWindowTitle(self._window_title())
        self._restore_window()
        self._build_ui()
        self._toast = ToastManager(self)
        if os.environ.get("APP_DEBUG"):
            from app.widgets.toast_test_panel import ToastTestPanel
            self._toast_test = ToastTestPanel(self._toast, self)

    # ------------------------------------------------------------------
    # UI 構築
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        # ツールバー
        toolbar = QToolBar()
        self.addToolBar(toolbar)

        # プロファイル選択コンボボックス
        self._profile_combo = QComboBox()
        self._profile_combo.setMinimumWidth(180)
        self._refresh_profile_combo()
        self._profile_combo.currentIndexChanged.connect(self._on_profile_selected)
        toolbar.addWidget(self._profile_combo)
        toolbar.addSeparator()

        btn_add = QPushButton("＋ カード追加")
        btn_add.clicked.connect(self._on_add_card)
        toolbar.addWidget(btn_add)

        btn_save_as = QPushButton("別名保存")
        btn_save_as.clicked.connect(self._on_save_as)
        toolbar.addWidget(btn_save_as)

        # スペーサー（設定ボタンを右端に寄せる）
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)

        # 歯車（設定）ボタン
        self._btn_settings = QPushButton("⚙")
        self._btn_settings.setToolTip("設定")
        self._btn_settings.setFixedWidth(32)
        self._btn_settings.clicked.connect(self._on_settings)
        toolbar.addWidget(self._btn_settings)

        # カードグリッド
        self._card_grid = CardGrid(
            self._profile,
            aspect_ratio=self._config.thumbnail_aspect_ratio,
            parent=self,
        )
        self._card_grid.card_opened.connect(self._on_card_open)
        self._card_grid.profile_changed.connect(self._save_profile)
        self.setCentralWidget(self._card_grid)

        # ステータスバー
        self.setStatusBar(QStatusBar())

        self._setup_shortcuts()

    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence(Qt.Key.Key_Delete), self).activated.connect(
            self._on_delete_selected
        )
        QShortcut(QKeySequence("Ctrl+N"), self).activated.connect(self._on_add_card)
        QShortcut(QKeySequence(Qt.Key.Key_Q), self).activated.connect(
            QApplication.instance().quit
        )

    # ------------------------------------------------------------------
    # ウィンドウ状態
    # ------------------------------------------------------------------

    def _restore_window(self) -> None:
        w = self._profile.app_state.window
        self.resize(w.width, w.height)
        if w.x is not None and w.y is not None:
            self.move(w.x, w.y)

    def _save_window_state(self) -> None:
        geo = self.geometry()
        self._profile.app_state.window.x = geo.x()
        self._profile.app_state.window.y = geo.y()
        self._profile.app_state.window.width = geo.width()
        self._profile.app_state.window.height = geo.height()

    def _restore_viewer_state(self) -> None:
        """前回 ViewerPage で終了していた場合は自動遷移。"""
        state = self._profile.app_state
        if state.last_page != "viewer" or not state.last_card_id:
            return
        card = next(
            (c for c in self._profile.cards if c.id == state.last_card_id), None
        )
        if card:
            self._open_viewer(card)

    def _window_title(self) -> str:
        return f"Image Folder Viewer — {Path(self._profile_path).stem}"

    # ------------------------------------------------------------------
    # プロファイル操作
    # ------------------------------------------------------------------

    def _refresh_profile_combo(self) -> None:
        """コンボボックスのプロファイル一覧を再構築する。"""
        self._profile_combo.blockSignals(True)
        self._profile_combo.clear()
        for r in self._config.recent_profiles:
            self._profile_combo.addItem(r.name, r.path)
        self._profile_combo.addItem("プロファイルを開く...", "open")
        self._profile_combo.addItem("新規作成...", "new")
        # 現在のプロファイルを選択状態にする（末尾2項目はアクションなので除外）
        for i in range(self._profile_combo.count() - 2):
            if self._profile_combo.itemData(i) == self._profile_path:
                self._profile_combo.setCurrentIndex(i)
                break
        self._profile_combo.blockSignals(False)

    def _on_profile_selected(self, index: int) -> None:
        data = self._profile_combo.itemData(index)
        if data == "open":
            self._on_open_profile()
            return
        if data == "new":
            self._on_new_profile()
            return
        if data == self._profile_path:
            return
        self._switch_profile(data)

    def _on_new_profile(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "新規プロファイルの保存先",
            "profile.ivprofile",
            "IVプロファイル (*.ivprofile)",
        )
        if not path:
            self._refresh_profile_combo()
            return
        try:
            create_empty_profile(path)
        except Exception as e:
            self._toast.add_toast(f"プロファイルを作成できません: {e}", ToastType.ERROR)
            self._refresh_profile_combo()
            return
        self._switch_profile(path)

    def _on_open_profile(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "プロファイルを開く",
            "",
            "IVプロファイル (*.ivprofile)",
        )
        if not path:
            # キャンセル時はコンボを現在のプロファイルに戻す
            self._refresh_profile_combo()
            return
        self._switch_profile(path)

    def _switch_profile(self, path: str) -> None:
        """現在のプロファイルを保存して新しいプロファイルに切り替える。"""
        try:
            new_profile = load_profile(path)
        except Exception as e:
            self._toast.add_toast(f"プロファイルを開けません: {e}", ToastType.ERROR)
            self._refresh_profile_combo()
            return

        self._save_profile()

        self._profile = new_profile
        self._profile_path = path

        add_recent_profile(self._config, path, Path(path).stem)
        save_app_config(self._config)

        self.setWindowTitle(self._window_title())
        self._card_grid.set_profile(new_profile)
        self._refresh_profile_combo()
        QTimer.singleShot(0, self._restore_card_focus)

    def _on_save_as(self) -> None:
        """現在のプロファイルを別名で保存し、新しいパスに切り替える。"""
        path, _ = QFileDialog.getSaveFileName(
            self,
            "別名で保存",
            self._profile_path,
            "IVプロファイル (*.ivprofile)",
        )
        if not path:
            return
        try:
            save_profile(path, self._profile)
        except Exception as e:
            self._toast.add_toast(f"保存に失敗しました: {e}", ToastType.ERROR)
            return

        self._profile_path = path
        add_recent_profile(self._config, path, Path(path).stem)
        save_app_config(self._config)

        self.setWindowTitle(self._window_title())
        self._refresh_profile_combo()
        self._toast.add_toast("別名で保存しました", ToastType.SUCCESS)

    def _save_profile(self) -> None:
        try:
            save_profile(self._profile_path, self._profile)
        except Exception as e:
            self._toast.add_toast(f"保存に失敗しました: {e}", ToastType.ERROR)

    # ------------------------------------------------------------------
    # カード操作
    # ------------------------------------------------------------------

    def _on_settings(self) -> None:
        panel = SettingsPanel(
            theme=self._config.theme,
            aspect_ratio=self._config.thumbnail_aspect_ratio,
            parent=self,
        )
        panel.theme_changed.connect(self._on_theme_changed)
        panel.aspect_ratio_changed.connect(self._on_aspect_ratio_changed)
        panel.popup_below(self._btn_settings)

    def _on_aspect_ratio_changed(self, ratio: str) -> None:
        self._config.thumbnail_aspect_ratio = ratio
        self._card_grid.set_aspect_ratio(ratio)
        try:
            save_app_config(self._config)
        except Exception:
            pass

    def _on_theme_changed(self, theme: str) -> None:
        self._config.theme = theme
        app = QApplication.instance()
        if app:
            theme_mod.apply_theme(app, theme)
        self._card_grid.refresh()
        try:
            save_app_config(self._config)
        except Exception:
            pass

    def _on_add_card(self) -> None:
        from app.windows.card_dialog import CardDialog

        dlg = CardDialog(parent=self)
        if dlg.exec():
            card = dlg.result_card()
            card.sort_order = len(self._profile.cards)
            self._profile.cards.append(card)
            self._card_grid.refresh()
            self._save_profile()

    def _on_card_open(self, card: Card) -> None:
        self._open_viewer(card)

    def _open_viewer(self, card: Card) -> None:
        from app.windows.viewer_window import ViewerWindow

        self._profile.app_state.last_page = "viewer"
        self._profile.app_state.last_card_id = card.id

        self._viewer = ViewerWindow(
            card=card,
            profile=self._profile,
            profile_path=self._profile_path,
            parent=self,
        )
        self._viewer.closed.connect(self._on_viewer_closed)
        self._viewer.show()
        self.hide()

    def _on_delete_selected(self) -> None:
        self._card_grid.delete_selected()

    def _on_viewer_closed(self) -> None:
        # last_page は ViewerWindow 側で設定済み（戻る→index、直接閉じる→viewer のまま）
        self._save_profile()
        self.show()
        # ViewerWindow の close 処理完了後にフォーカスを確実に設定する
        QTimer.singleShot(0, self._restore_card_focus)

    def _restore_card_focus(self) -> None:
        """直前に開いていたカードを選択してフォーカスを移す。
        last_card_id が未設定の場合は先頭カードを選択する。"""
        last_id = self._profile.app_state.last_card_id
        if last_id:
            self._card_grid.select_card_by_id(last_id)
        elif self._profile.cards:
            self._card_grid.select_card_by_id(self._profile.cards[0].id)
        self._card_grid.set_focus()

    # ------------------------------------------------------------------
    # ウィンドウイベント
    # ------------------------------------------------------------------

    def showEvent(self, event) -> None:
        super().showEvent(event)
        QTimer.singleShot(0, self._restore_card_focus)

    def closeEvent(self, event) -> None:
        self._save_window_state()
        self._profile.app_state.last_page = "index"
        self._save_profile()
        event.accept()
