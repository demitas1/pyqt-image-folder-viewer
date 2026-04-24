"""
Image Folder Viewer - PyQt6 版
エントリーポイント
"""

import sys
from pathlib import Path
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication
from app.models.app_config import load_app_config
from app.utils import theme as theme_mod
from app.windows.startup_window import StartupWindow

_ASSETS_DIR = Path(__file__).parent / "assets"
_ICON_SIZES = [16, 32, 48, 64, 128, 256]


def _build_app_icon() -> QIcon:
    icon = QIcon()
    for size in _ICON_SIZES:
        path = _ASSETS_DIR / f"icon_{size}.png"
        if path.exists():
            icon.addFile(str(path))
    return icon


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("image-folder-viewer")
    app.setOrganizationName("org.example")
    app.setWindowIcon(_build_app_icon())

    # 起動時テーマ適用（StartupWindow より先に設定して初期フリッカーを防ぐ）
    config = load_app_config()
    theme_mod.apply_theme(app, config.theme)

    window = StartupWindow()
    # 自動オープンに成功した場合は MainWindow がすでに表示されているため表示しない
    if not window._launched:
        window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
