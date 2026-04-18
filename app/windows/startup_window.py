"""
StartupWindow — プロファイル選択画面
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from app.models.app_config import (
    AppConfig,
    add_recent_profile,
    load_app_config,
    remove_recent_profile,
    save_app_config,
)
from app.models.profile import ProfileData, create_empty_profile, load_profile


class StartupWindow(QDialog):
    """起動時のプロファイル選択ダイアログ。"""

    def __init__(self, parent=None, auto_open: bool = True):
        super().__init__(parent)
        self.setWindowTitle("Image Folder Viewer")
        self.setMinimumWidth(560)

        self._config = load_app_config()
        self._profile: ProfileData | None = None
        self._profile_path: str | None = None
        self._launched: bool = False  # 自動オープン成功フラグ

        self._build_ui()
        self._refresh_recent_list()

        # 前回プロファイルの自動オープン
        if auto_open and self._config.recent_profiles:
            self._auto_open(self._config.recent_profiles[0].path)

    # ------------------------------------------------------------------
    # UI 構築
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        title = QLabel("プロファイルを選択してください")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # 最近使用したプロファイル一覧（2カラム）
        recent_label = QLabel("最近使用したプロファイル")
        layout.addWidget(recent_label)

        self._recent_list = QTreeWidget()
        self._recent_list.setColumnCount(2)
        self._recent_list.setHeaderLabels(["プロファイル名", "パス"])
        self._recent_list.setRootIsDecorated(False)
        self._recent_list.setSelectionBehavior(
            self._recent_list.SelectionBehavior.SelectRows
        )
        self._recent_list.header().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self._recent_list.header().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self._recent_list.itemDoubleClicked.connect(self._on_recent_double_click)
        layout.addWidget(self._recent_list)

        # 履歴・ファイル削除ボタン
        btn_row2 = QHBoxLayout()
        self._btn_remove = QPushButton("履歴から削除")
        self._btn_remove.clicked.connect(self._on_remove_recent)
        btn_row2.addWidget(self._btn_remove)
        self._btn_delete_file = QPushButton("ファイルを削除")
        self._btn_delete_file.clicked.connect(self._on_delete_file)
        btn_row2.addWidget(self._btn_delete_file)
        layout.addLayout(btn_row2)

        # アクションボタン
        btn_row = QHBoxLayout()
        self._btn_open = QPushButton("プロファイルを開く")
        self._btn_new = QPushButton("新規作成")
        self._btn_open.clicked.connect(self._on_open)
        self._btn_new.clicked.connect(self._on_new)
        btn_row.addWidget(self._btn_open)
        btn_row.addWidget(self._btn_new)
        layout.addLayout(btn_row)

    # ------------------------------------------------------------------
    # ロジック
    # ------------------------------------------------------------------

    def _refresh_recent_list(self) -> None:
        self._recent_list.clear()
        for r in self._config.recent_profiles:
            item = QTreeWidgetItem([r.name, r.path])
            item.setData(0, Qt.ItemDataRole.UserRole, r.path)
            self._recent_list.addTopLevelItem(item)

    def _current_path(self) -> str | None:
        item = self._recent_list.currentItem()
        if not item:
            return None
        return item.data(0, Qt.ItemDataRole.UserRole)

    def _auto_open(self, path: str) -> None:
        try:
            self._open_profile(path)
        except Exception:
            pass  # 失敗時はそのまま StartupWindow を表示

    def _open_profile(self, path: str) -> None:
        profile = load_profile(path)
        add_recent_profile(self._config, path, Path(path).stem)
        save_app_config(self._config)

        self._profile = profile
        self._profile_path = path
        self._launch_main_window()

    def _launch_main_window(self) -> None:
        from app.windows.main_window import MainWindow

        # self に保持しないと関数終了時に GC されてウィンドウが即座に破棄される
        self._main_window = MainWindow(
            profile=self._profile,
            profile_path=self._profile_path,
            config=self._config,
        )
        self._main_window.show()
        self._main_window._restore_viewer_state()  # show() の後に呼ぶことで hide() が有効になる
        self._launched = True
        self.close()

    # ------------------------------------------------------------------
    # スロット
    # ------------------------------------------------------------------

    def _on_open(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "プロファイルを開く",
            "",
            "IVプロファイル (*.ivprofile)",
        )
        if not path:
            return
        try:
            self._open_profile(path)
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"プロファイルを開けません:\n{e}")

    def _on_new(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "新規プロファイルの保存先",
            "profile.ivprofile",
            "IVプロファイル (*.ivprofile)",
        )
        if not path:
            return
        try:
            profile = create_empty_profile(path)
            add_recent_profile(self._config, path, Path(path).stem)
            save_app_config(self._config)
            self._profile = profile
            self._profile_path = path
            self._launch_main_window()
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"プロファイルを作成できません:\n{e}")

    def _on_recent_double_click(self, item: QTreeWidgetItem) -> None:
        path = item.data(0, Qt.ItemDataRole.UserRole)
        try:
            self._open_profile(path)
        except Exception as e:
            QMessageBox.warning(self, "エラー", f"プロファイルを開けません:\n{e}")

    def _on_remove_recent(self) -> None:
        path = self._current_path()
        if not path:
            return
        remove_recent_profile(self._config, path)
        save_app_config(self._config)
        self._refresh_recent_list()

    def _on_delete_file(self) -> None:
        path = self._current_path()
        if not path:
            return
        ret = QMessageBox.question(
            self,
            "ファイルの削除",
            f"プロファイルファイルを削除しますか？\n{path}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ret != QMessageBox.StandardButton.Yes:
            return
        try:
            Path(path).unlink()
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"ファイルを削除できません:\n{e}")
            return
        remove_recent_profile(self._config, path)
        save_app_config(self._config)
        self._refresh_recent_list()
