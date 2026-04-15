# PyQt 移行ガイド

本ドキュメントは Tauri/React 実装から PyQt6 実装へ移行するための参考資料です。
エンドユーザーから見た動作仕様を中心に記述し、UI フリーズ問題（サムネイルピッカー）の
根本的な解決を目的とした実装の雛形作成に使用することを想定しています。

---

## 1. アプリ概要

ローカルPCの画像フォルダを「カード」として登録・管理し、快適に閲覧できるデスクトップアプリ。

**主な機能：**
- フォルダをカードとして登録し、サムネイル付きグリッドで一覧表示
- カードをクリックして画像ビューアを開く
- ビューア内で画像を順次閲覧（ナビゲーション・H-Flip・シャッフル・ズーム）
- 設定をプロファイルファイル（`.ivprofile`）に保存・復元

---

## 2. データ構造

### 2.1 プロファイルファイル（`.ivprofile`）

任意の場所に保存できる JSON ファイル。アプリの主要データを保持する。

```json
{
  "version": "1.0",
  "updatedAt": "2026-04-07T12:00:00Z",
  "cards": [
    {
      "id": "uuid-string",
      "title": "カードタイトル",
      "folderPath": "/path/to/folder",
      "thumbnail": "/path/to/thumbnail/image.jpg",
      "sortOrder": 0,
      "createdAt": "2026-04-07T12:00:00Z",
      "updatedAt": "2026-04-07T12:00:00Z",
      "recursive": false,
      "viewerState": {
        "lastImageIndex": 3,
        "lastImageFilename": "image004.jpg",
        "hFlipEnabled": false,
        "shuffleEnabled": false
      }
    }
  ],
  "tags": [],
  "cardTags": [],
  "appState": {
    "lastPage": "index",
    "lastCardId": null,
    "lastImageIndex": 0,
    "hFlipEnabled": false,
    "shuffleEnabled": false,
    "window": {
      "x": 100,
      "y": 100,
      "width": 1200,
      "height": 800
    }
  }
}
```

**フィールド説明：**

| フィールド | 説明 |
|-----------|------|
| `cards[].id` | UUID（一意識別子）|
| `cards[].thumbnail` | サムネイル元画像のファイルパス（null = 未設定）|
| `cards[].recursive` | サブディレクトリを含めて画像を検索するか |
| `cards[].viewerState` | カード固有のビューア状態（前回終了時の位置・設定）|
| `appState.lastPage` | 前回終了時のページ（`"index"` または `"viewer"`）|
| `appState.window` | ウィンドウ位置・サイズ |

### 2.2 アプリ共通設定（`app_config.json`）

OSのアプリデータディレクトリに保存される設定ファイル。

```json
{
  "version": "1.0",
  "recentProfiles": [
    {
      "path": "/path/to/profile.ivprofile",
      "name": "プロファイル名",
      "lastOpenedAt": "2026-04-07T12:00:00Z"
    }
  ],
  "maxRecentProfiles": 10,
  "theme": "dark",
  "focusOnStartup": true,
  "thumbnailAspectRatio": "16:9"
}
```

**保存場所：**
- Linux: `~/.local/share/<app-name>/app_config.json`
- macOS: `~/Library/Application Support/<app-name>/app_config.json`
- Windows: `%APPDATA%\<app-name>\app_config.json`

PyQt では `QStandardPaths.AppDataLocation` で取得できる。

---

## 3. 画面構成

```
起動
 │
 ├─ 前回プロファイルあり → 自動オープン → IndexPage
 │
 └─ 前回プロファイルなし → StartupPage
                              │
                              ├─ 既存プロファイルを開く → IndexPage
                              └─ 新規作成 → IndexPage

IndexPage
 └─ カードをクリック → ViewerPage
                         └─ ESC / 戻るボタン → IndexPage
```

---

## 4. 各画面の動作仕様

### 4.1 起動フロー

1. `app_config.json` を読み込む
2. `recentProfiles` の先頭（最後に開いたプロファイル）を自動オープン試行
3. 成功 → IndexPage を表示（ウィンドウ位置・サイズを `appState.window` から復元）
4. 失敗または履歴なし → StartupPage を表示

**前回ViewerPageで終了していた場合：**
IndexPage 表示後、`appState.lastPage === "viewer"` かつ `lastCardId` が有効であれば
自動的に ViewerPage へ遷移する。

### 4.2 StartupPage

**表示内容：**
- 「プロファイルを開く」ボタン → ファイルダイアログで `.ivprofile` を選択
- 「新規作成」ボタン → 保存ダイアログでパスを指定して空のプロファイルを作成
- 最近使用したプロファイル一覧（クリックで開く、×ボタンで履歴から削除）

**動作：**
- プロファイルを開く/作成すると IndexPage へ遷移
- 履歴のパスが存在しない場合はエラー表示（自動削除はしない）

### 4.3 IndexPage

**表示内容：**
- ヘッダー：プロファイル名セレクター・設定ボタン・カード追加ボタン
- メイン：カードのグリッド（サムネイル＋タイトル）

**カード表示：**
- 各カードはサムネイル画像（アスペクト比は設定可能：16:9 / 4:3 / 1:1）とタイトルを表示
- サムネイル画像は `cards[].thumbnail` のパスから生成（120px または 480px）
- `thumbnail` が null の場合は画像アイコンを表示
- フォルダが存在しないカードはエラー状態として表示（アイコン変更・タイトルに警告）

**カード操作：**

| 操作 | 動作 |
|------|------|
| クリック | ViewerPage へ遷移（エラー状態のカードは無効）|
| ドラッグ＆ドロップ | カードの並び替え（`sortOrder` を更新して即時保存）|
| 右クリックメニュー or コンテキスト | 編集・削除 |

**カード追加モーダル：**
- タイトル（テキスト入力）
- フォルダパス（テキスト入力 + フォルダ選択ダイアログボタン）
- サムネイル画像（画像ピッカーモーダル or ファイルダイアログ）
- サブディレクトリを含む（チェックボックス）

**カード編集モーダル：**
- 追加と同じフィールドを編集可能

**プロファイル管理（ヘッダー）：**
- プロファイル名ドロップダウン：最近使ったプロファイルの切り替え
- 「別名保存」：現在のプロファイルを別ファイルに保存
- 保存はカード操作時に自動実行（追加・編集・削除・並び替え）

**設定パネル（歯車ボタン）：**
- テーマ切替（light / dark）
- サムネイルアスペクト比切替（16:9 / 4:3 / 1:1）

**キーボードショートカット：**

| キー | 動作 |
|------|------|
| `←→↑↓` | カード選択移動 |
| `Enter` | 選択カードを開く（ViewerPage へ）|
| `Delete` | 選択カードを削除（確認ダイアログ）|
| `Ctrl+N` | カード追加モーダルを開く |
| `Ctrl+S` | 手動保存 |

### 4.4 ViewerPage

**表示内容：**
- ヘッダー：「戻る」ボタン・カードタイトル・現在のファイル名・ズーム率・H/Rトグルボタン
- メイン：画像表示エリア（ズーム・H-Flip 対応）
- フッター：現在位置表示（`N / 総数`）・ショートカットヒント

**画像読み込み：**
1. `folderPath` 内の画像ファイルを一覧取得（拡張子: jpg, jpeg, png, gif, webp, bmp）
2. `recursive: true` の場合はサブディレクトリも再帰検索
3. `cards[].viewerState.lastImageIndex` の位置から再開
4. `lastImageFilename` が一致しない場合は警告トーストを表示してインデックス 0 から再開
5. フォルダが存在しない場合はエラートーストを表示して IndexPage へ自動遷移

**ナビゲーション：**
- 前後の画像へ移動
- シャッフルモード：画像一覧をランダム順に並び替えた仮想インデックスで移動
- 画像をクリックすると次の画像へ

**H-Flip：**
- 水平反転表示のトグル（CSS `transform: scaleX(-1)` 相当）
- 状態はカード単位で保存

**ズーム：**
- 初期表示：ウィンドウサイズにフィットするズーム率を自動計算
- ズームイン（`+`）：ウィンドウサイズを `×1.2` に拡大（モニター最大サイズでキャップ）
- ズームアウト（`-`）：ウィンドウサイズを `×0.8` に縮小（最小 200px）
- ズームリセット（`0`）：現在のウィンドウサイズで再フィット計算
- ウィンドウを手動リサイズした際もフィットズームを再計算

**状態保存タイミング：**
- 画像移動・H-Flip・シャッフル変更のたびに `viewerState` をプロファイルへ保存
- IndexPage へ戻る際に `appState.lastPage = "index"` を保存

**キーボードショートカット：**

| キー | 動作 |
|------|------|
| `←` | 前の画像 |
| `→` | 次の画像 |
| `H` | H-Flip トグル |
| `R` | シャッフル トグル |
| `+` / `=` | ズームイン |
| `-` | ズームアウト |
| `0` | ズームリセット |
| `Space` | コンテキストメニュー表示（画面中央）|
| `Q` / `Escape` | IndexPage へ戻る |

**コンテキストメニュー（右クリック / Space）：**
- 「コピー」：現在の画像をクリップボードにコピー
- 「パスをコピー」：現在の画像のファイルパスをテキストでクリップボードにコピー
- 「水平反転: ON/OFF」
- 「シャッフル: ON/OFF」
- 「ズームイン / アウト / リセット」
- 「インデックスに戻る」
- 「終了」

### 4.5 画像ピッカーモーダル

IndexPage のカード追加・編集時に使用するサムネイル選択モーダル。

**動作仕様：**
- 初期表示：前回選択したフォルダ（または `thumbnail` のフォルダ）を開く
- フォルダ内の画像ファイルと子フォルダをグリッド表示
- フォルダタイルをクリックでそのフォルダへ移動
- 「..」タイルをクリックで親フォルダへ移動
- 画像タイルをクリックで選択（選択済みは青枠表示）
- 「決定」ボタンで選択画像のパスを返す
- サムネイル表示は本実装の最重要課題（Tauri 版で未解決）

**PyQt での実装方針（詳細は後述）：**
- `QListView` + `QAbstractItemModel` + `QStyledItemDelegate`
- `QThreadPool` で画像デコードを並列実行
- 完了時 `Signal` で UI スレッドに通知 → `QListView` を部分更新

---

## 5. PyQt 実装指針

### 5.1 推奨構成

```
app/
├── main.py                 # エントリーポイント（QApplication）
├── config.py               # AppConfig の読み書き（JSON）
├── profile.py              # ProfileData の読み書き（JSON）
├── models/
│   ├── card.py             # Card データクラス
│   └── profile_data.py     # ProfileData データクラス
├── windows/
│   ├── startup_window.py   # StartupPage 相当
│   ├── main_window.py      # IndexPage 相当（QMainWindow）
│   └── viewer_window.py    # ViewerPage 相当（QMainWindow or QWidget）
├── widgets/
│   ├── card_grid.py        # カードグリッド（QListView + カスタムモデル）
│   ├── card_delegate.py    # カードの描画（QStyledItemDelegate）
│   ├── image_picker.py     # 画像ピッカーモーダル（QDialog）
│   └── thumbnail_loader.py # サムネイルローダー（QThreadPool + Signal）
└── utils/
    ├── image_utils.py      # 画像処理（サムネイル生成）
    └── file_utils.py       # ファイル操作
```

### 5.2 サムネイルローダー（最重要）

Tauri 版の UI フリーズ問題を解決する中核実装。

```python
from PyQt6.QtCore import QRunnable, QObject, pyqtSignal, QThreadPool
from PyQt6.QtGui import QPixmap, QImage
from PIL import Image  # or use QImage directly

class ThumbnailSignals(QObject):
    ready = pyqtSignal(str, QPixmap)   # (path, pixmap)
    failed = pyqtSignal(str)            # (path,)

class ThumbnailTask(QRunnable):
    def __init__(self, path: str, size: int = 120):
        super().__init__()
        self.path = path
        self.size = size
        self.signals = ThumbnailSignals()

    def run(self):
        # このメソッドは QThreadPool のワーカースレッドで実行される
        # → メインスレッドをブロックしない
        try:
            img = QImage(self.path)
            if img.isNull():
                self.signals.failed.emit(self.path)
                return
            scaled = img.scaled(
                self.size, self.size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            pixmap = QPixmap.fromImage(scaled)
            self.signals.ready.emit(self.path, pixmap)
        except Exception:
            self.signals.failed.emit(self.path)

class ThumbnailLoader:
    def __init__(self):
        self._pool = QThreadPool.globalInstance()
        self._pool.setMaxThreadCount(4)
        self._cache: dict[str, QPixmap] = {}

    def request(self, path: str, callback, size: int = 120):
        if path in self._cache:
            callback(path, self._cache[path])
            return
        task = ThumbnailTask(path, size)
        task.signals.ready.connect(lambda p, px: self._on_ready(p, px, callback))
        self._pool.start(task)

    def _on_ready(self, path, pixmap, callback):
        self._cache[path] = pixmap
        callback(path, pixmap)
```

**ポイント：**
- `QImage.scaled()` は Qt の C++ コード → GIL が解放され真の並列実行
- `Signal` によるスレッド間通信はシリアライズなし（`QPixmap` オブジェクトを参照渡し）
- メインスレッドは `callback` の呼び出しのみ（軽量）

### 5.3 カードグリッド（ドラッグ＆ドロップ）

```python
from PyQt6.QtWidgets import QListView
from PyQt6.QtCore import Qt

class CardGridView(QListView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setViewMode(QListView.ViewMode.IconMode)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setDragDropMode(QListView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setSpacing(8)
```

ドラッグ＆ドロップで並び替えた後、モデル側で `sortOrder` を更新してプロファイルを保存。

### 5.4 画像ビューア

```python
from PyQt6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsPixmapItem
from PyQt6.QtGui import QPixmap, QTransform

class ImageView(QGraphicsView):
    def __init__(self):
        super().__init__()
        self._scene = QGraphicsScene()
        self.setScene(self._scene)
        self._item = QGraphicsPixmapItem()
        self._scene.addItem(self._item)
        self._h_flip = False
        self._zoom = 1.0

    def set_image(self, path: str):
        pixmap = QPixmap(path)
        self._update_display(pixmap)

    def set_h_flip(self, enabled: bool):
        self._h_flip = enabled
        self._apply_transform()

    def set_zoom(self, zoom: float):
        self._zoom = zoom
        self._apply_transform()

    def _apply_transform(self):
        t = QTransform()
        t.scale(-self._zoom if self._h_flip else self._zoom, self._zoom)
        self.setTransform(t)
```

### 5.5 ウィンドウ状態の保存・復元

```python
from PyQt6.QtCore import QSettings, QByteArray

class MainWindow(QMainWindow):
    def save_window_state(self, profile: ProfileData):
        geo = self.geometry()
        profile.app_state.window = WindowState(
            x=geo.x(), y=geo.y(),
            width=geo.width(), height=geo.height()
        )

    def restore_window_state(self, profile: ProfileData):
        w = profile.app_state.window
        self.resize(w.width, w.height)
        if w.x is not None and w.y is not None:
            self.move(w.x, w.y)
```

### 5.6 データの読み書き

`.ivprofile` は JSON ファイルなので既存ファイルをそのまま読み書き可能。
`dataclasses` + `dacite`、または `pydantic` を使うと型安全に扱える。

```python
import json
from dataclasses import dataclass, field, asdict
from typing import Optional
import uuid
from datetime import datetime, timezone

@dataclass
class CardViewerState:
    last_image_index: int = 0
    last_image_filename: Optional[str] = None
    h_flip_enabled: bool = False
    shuffle_enabled: bool = False

@dataclass
class Card:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    folder_path: str = ""
    thumbnail: Optional[str] = None
    sort_order: int = 0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    recursive: bool = False
    viewer_state: Optional[CardViewerState] = None
```

**注意：** `.ivprofile` の JSON キーは `camelCase`（`folderPath` 等）。
Python の `snake_case` との変換が必要。

```python
def load_profile(path: str) -> ProfileData:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    # camelCase → snake_case 変換が必要
    # pydantic v2 の model_config = ConfigDict(alias_generator=to_camel) が便利
    ...
```

---

## 6. 現行 Tauri 版との互換性

### 6.1 維持すべき仕様

- `.ivprofile` ファイル形式（JSON・フィールド名）の完全互換
- `app_config.json` の保存場所と形式

これにより Tauri 版と PyQt 版で同じプロファイルファイルを共有できる。

### 6.2 Tauri 版で未実装の機能

- **画像ピッカーのサムネイル表示**：Tauri 版では矩形のみ表示中。PyQt 版で初めて完全実装する。

### 6.3 不要になる概念

| Tauri/React の概念 | PyQt での対応 |
|-------------------|--------------|
| Tauri IPC (`invoke()`) | Python 関数の直接呼び出し |
| Zustand ストア | QObject のメンバー変数 + Signal/Slot |
| React Router | QStackedWidget or 複数 QWindow の切り替え |
| Tailwind CSS | Qt Style Sheet (QSS) |
| `convertFileSrc()` | `QPixmap(path)` で直接ロード |

---

## 7. 実装優先順位（雛形フェーズ）

雛形実装として以下の順序を推奨します：

1. **データモデル**：`Card`・`ProfileData`・`AppConfig` のデータクラスと JSON 読み書き
2. **StartupPage**：プロファイル選択ダイアログ（シンプルな `QDialog`）
3. **IndexPage 骨格**：カードグリッド（サムネイルなし・タイトルのみ）
4. **サムネイルローダー**：`QThreadPool` 版の実装と動作確認（最重要検証）
5. **画像ピッカーモーダル**：サムネイル付きグリッド（`QListView` + カスタムデリゲート）
6. **ViewerPage 骨格**：画像表示・前後ナビゲーション
7. **ズーム・H-Flip**：`QGraphicsView` を使った変換
8. **状態保存・復元**：ウィンドウ位置・ビューア状態
9. **ドラッグ＆ドロップ**：カード並び替え
10. **プロファイル管理**：切り替え・新規作成・別名保存
