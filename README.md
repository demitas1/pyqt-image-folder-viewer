# pyqt-image-folder-viewer

ローカルPCの画像フォルダをサムネイル付きカードで管理し、快適に閲覧できるデスクトップアプリケーション。

PyQt6 製。

## 機能

- 画像フォルダをカードとして登録・管理
- サムネイル付きカードのグリッド表示
- 画像ビューア（ナビゲーション、水平反転、シャッフル、ズーム）
- プロファイルファイル（`.ivprofile`）による設定の保存・読み込み
- ライト / ダークテーマ切替
- サムネイルアスペクト比切替（16:9 / 4:3 / 1:1）
- クリップボードへの画像・パスコピー

## 動作環境

- Python 3.10 以上
- PyQt6
- Linux / macOS / Windows（動作確認は Linux メイン）

## セットアップ

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## 起動

```bash
# 通常起動
./start.sh

# 直接起動
QT_SCALE_FACTOR=1.5 .venv/bin/python3 main.py

# デバッグモード（トーストテストパネル表示）
./start_debug.sh
```

`QT_SCALE_FACTOR` は画面 DPI に合わせて調整してください（4K 画面では `1.5`〜`2.0` 推奨）。

## キーボードショートカット

| キー | 動作 |
|------|------|
| `←` / `→` | 前/次の画像 |
| `H` | 水平反転 |
| `R` | シャッフル切替 |
| `+` / `-` | ズームイン / アウト |
| `Space` | コンテキストメニュー |
| `Escape` | 画像一覧に戻る |
| `Q` | アプリ終了 |

## ライセンス

[GNU General Public License v3.0](LICENSE)

本ソフトウェアは PyQt6 を使用しており、GPL v3 の下で配布されます。
