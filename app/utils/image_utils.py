"""
画像ユーティリティ（ファイル列挙・拡張子判定）
"""

from pathlib import Path

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}


def is_image_file(path: Path) -> bool:
    """画像ファイルか判定する（macOS ZIPアーティファクト除外）"""
    if path.name.startswith("._"):
        return False
    return path.suffix.lower() in IMAGE_EXTENSIONS


def collect_images(folder_path: str, recursive: bool = False) -> list[Path]:
    """フォルダ内の画像ファイルを収集して返す（ソート済み）"""
    root = Path(folder_path)
    if not root.exists() or not root.is_dir():
        return []

    if recursive:
        paths = [
            p for p in root.rglob("*")
            if p.is_file()
            and is_image_file(p)
            and "__MACOSX" not in p.parts
        ]
    else:
        paths = [
            p for p in root.iterdir()
            if p.is_file() and is_image_file(p)
        ]

    return sorted(paths)
