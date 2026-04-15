"""
アプリ共通設定モデル（app_config.json と互換）
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from PyQt6.QtCore import QStandardPaths


APP_NAME = "image-folder-viewer"
ORG_NAME = "org.example"
MAX_RECENT_PROFILES = 10


def _config_path() -> Path:
    data_dir = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.AppDataLocation
    )
    return Path(data_dir) / "app_config.json"


@dataclass
class RecentProfile:
    path: str
    name: str
    last_opened_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @classmethod
    def from_dict(cls, d: dict) -> RecentProfile:
        return cls(
            path=d["path"],
            name=d.get("name", Path(d["path"]).stem),
            last_opened_at=d.get("lastOpenedAt", ""),
        )

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "name": self.name,
            "lastOpenedAt": self.last_opened_at,
        }


@dataclass
class AppConfig:
    version: str = "1.0"
    recent_profiles: list[RecentProfile] = field(default_factory=list)
    max_recent_profiles: int = MAX_RECENT_PROFILES
    theme: str = "dark"
    focus_on_startup: bool = True
    thumbnail_aspect_ratio: str = "16:9"

    @classmethod
    def from_dict(cls, d: dict) -> AppConfig:
        return cls(
            version=d.get("version", "1.0"),
            recent_profiles=[
                RecentProfile.from_dict(r) for r in d.get("recentProfiles", [])
            ],
            max_recent_profiles=d.get("maxRecentProfiles", MAX_RECENT_PROFILES),
            theme=d.get("theme", "dark"),
            focus_on_startup=d.get("focusOnStartup", True),
            thumbnail_aspect_ratio=d.get("thumbnailAspectRatio", "16:9"),
        )

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "recentProfiles": [r.to_dict() for r in self.recent_profiles],
            "maxRecentProfiles": self.max_recent_profiles,
            "theme": self.theme,
            "focusOnStartup": self.focus_on_startup,
            "thumbnailAspectRatio": self.thumbnail_aspect_ratio,
        }


def load_app_config() -> AppConfig:
    path = _config_path()
    if not path.exists():
        return AppConfig()
    try:
        with open(path, encoding="utf-8") as f:
            return AppConfig.from_dict(json.load(f))
    except Exception:
        return AppConfig()


def save_app_config(config: AppConfig) -> None:
    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config.to_dict(), f, ensure_ascii=False, indent=2)


def add_recent_profile(config: AppConfig, profile_path: str, name: str) -> None:
    # 既存エントリを削除（重複排除）
    config.recent_profiles = [
        r for r in config.recent_profiles if r.path != profile_path
    ]
    # 先頭に追加
    config.recent_profiles.insert(
        0, RecentProfile(path=profile_path, name=name)
    )
    # 上限切り詰め
    config.recent_profiles = config.recent_profiles[: config.max_recent_profiles]


def remove_recent_profile(config: AppConfig, profile_path: str) -> None:
    config.recent_profiles = [
        r for r in config.recent_profiles if r.path != profile_path
    ]
