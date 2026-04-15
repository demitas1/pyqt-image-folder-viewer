"""
プロファイルデータモデル（.ivprofile と互換）
JSON キーは camelCase、Python 属性は snake_case で管理する
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class CardViewerState:
    last_image_index: int = 0
    last_image_filename: Optional[str] = None
    h_flip_enabled: bool = False
    shuffle_enabled: bool = False

    @classmethod
    def from_dict(cls, d: dict) -> CardViewerState:
        return cls(
            last_image_index=d.get("lastImageIndex", 0),
            last_image_filename=d.get("lastImageFilename"),
            h_flip_enabled=d.get("hFlipEnabled", False),
            shuffle_enabled=d.get("shuffleEnabled", False),
        )

    def to_dict(self) -> dict:
        d: dict = {
            "lastImageIndex": self.last_image_index,
            "hFlipEnabled": self.h_flip_enabled,
            "shuffleEnabled": self.shuffle_enabled,
        }
        if self.last_image_filename is not None:
            d["lastImageFilename"] = self.last_image_filename
        return d


@dataclass
class Card:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    folder_path: str = ""
    thumbnail: Optional[str] = None
    sort_order: int = 0
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)
    recursive: bool = False
    viewer_state: Optional[CardViewerState] = None

    @classmethod
    def from_dict(cls, d: dict) -> Card:
        vs = d.get("viewerState")
        return cls(
            id=d.get("id", str(uuid.uuid4())),
            title=d.get("title", ""),
            folder_path=d.get("folderPath", ""),
            thumbnail=d.get("thumbnail"),
            sort_order=d.get("sortOrder", 0),
            created_at=d.get("createdAt", _now_iso()),
            updated_at=d.get("updatedAt", _now_iso()),
            recursive=d.get("recursive", False),
            viewer_state=CardViewerState.from_dict(vs) if vs else None,
        )

    def to_dict(self) -> dict:
        d: dict = {
            "id": self.id,
            "title": self.title,
            "folderPath": self.folder_path,
            "thumbnail": self.thumbnail,
            "sortOrder": self.sort_order,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
            "recursive": self.recursive,
        }
        if self.viewer_state is not None:
            d["viewerState"] = self.viewer_state.to_dict()
        return d


@dataclass
class WindowState:
    x: Optional[int] = None
    y: Optional[int] = None
    width: int = 1200
    height: int = 800

    @classmethod
    def from_dict(cls, d: dict) -> WindowState:
        return cls(
            x=d.get("x"),
            y=d.get("y"),
            width=d.get("width", 1200),
            height=d.get("height", 800),
        )

    def to_dict(self) -> dict:
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
        }


@dataclass
class AppState:
    last_page: str = "index"
    last_card_id: Optional[str] = None
    last_image_index: int = 0
    last_image_filename: Optional[str] = None
    h_flip_enabled: bool = False
    shuffle_enabled: bool = False
    window: WindowState = field(default_factory=WindowState)
    viewer_window: WindowState = field(
        default_factory=lambda: WindowState(width=1280, height=900)
    )

    @classmethod
    def from_dict(cls, d: dict) -> AppState:
        return cls(
            last_page=d.get("lastPage", "index"),
            last_card_id=d.get("lastCardId"),
            last_image_index=d.get("lastImageIndex", 0),
            last_image_filename=d.get("lastImageFilename"),
            h_flip_enabled=d.get("hFlipEnabled", False),
            shuffle_enabled=d.get("shuffleEnabled", False),
            window=WindowState.from_dict(d.get("window", {})),
            viewer_window=WindowState.from_dict(
                d.get("viewerWindow", {"width": 1280, "height": 900})
            ),
        )

    def to_dict(self) -> dict:
        d: dict = {
            "lastPage": self.last_page,
            "lastCardId": self.last_card_id,
            "lastImageIndex": self.last_image_index,
            "hFlipEnabled": self.h_flip_enabled,
            "shuffleEnabled": self.shuffle_enabled,
            "window": self.window.to_dict(),
            "viewerWindow": self.viewer_window.to_dict(),
        }
        if self.last_image_filename is not None:
            d["lastImageFilename"] = self.last_image_filename
        return d


@dataclass
class ProfileData:
    version: str = "1.0"
    updated_at: str = field(default_factory=_now_iso)
    cards: list[Card] = field(default_factory=list)
    tags: list = field(default_factory=list)
    card_tags: list = field(default_factory=list)
    app_state: AppState = field(default_factory=AppState)

    @classmethod
    def from_dict(cls, d: dict) -> ProfileData:
        return cls(
            version=d.get("version", "1.0"),
            updated_at=d.get("updatedAt", _now_iso()),
            cards=[Card.from_dict(c) for c in d.get("cards", [])],
            tags=d.get("tags", []),
            card_tags=d.get("cardTags", []),
            app_state=AppState.from_dict(d.get("appState", {})),
        )

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "updatedAt": self.updated_at,
            "cards": [c.to_dict() for c in self.cards],
            "tags": self.tags,
            "cardTags": self.card_tags,
            "appState": self.app_state.to_dict(),
        }


def load_profile(path: str | Path) -> ProfileData:
    with open(path, encoding="utf-8") as f:
        return ProfileData.from_dict(json.load(f))


def save_profile(path: str | Path, profile: ProfileData) -> None:
    profile.updated_at = _now_iso()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(profile.to_dict(), f, ensure_ascii=False, indent=2)


def create_empty_profile(path: str | Path) -> ProfileData:
    profile = ProfileData()
    save_profile(path, profile)
    return profile
