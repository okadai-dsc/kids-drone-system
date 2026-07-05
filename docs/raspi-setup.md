# Raspberry Pi セットアップガイド（Buster 標準）

本番で Raspberry Pi（4台）が担う役割と、Pi 1台を動く状態にするまでの設定手順をまとめる。

Pi の役割は次の2つ（[../README.md](../README.md) のシステム構成参照）：

1. **tellomon**（[../pi/tellomon/](../pi/tellomon/)）：Tello 制御・映像の YOLO PC 転送・ビーコン送信・Scratch 向け HTTP API（`:8001`）
2. **Scratch GUI の静的配信**（`:8601`）：子供が触る UI。ビルド済み `build/` を配信するだけ

> **今回の実機は全台 Raspberry Pi OS Buster（32-bit / armv7l）**。本ガイドは Buster を標準ルートとして書く。
> 64-bit / Bookworm の Pi を使う場合のみ [付録A](#付録abookworm--64-bit-の場合uv-ルート) を参照。

## 全体チェックリスト

| # | やること | 節 |
|---|---|---|
| 1 | 環境確認（Buster であることの確認）| §1 |
| 2 | ネットワーク設定（固定IP・Tello Wi-Fi）| §2 |
| 3 | パッケージ導入（apt source 切替 + OpenCV / Tk）| §3 |
| 4 | リポジトリ取得と起動確認 | §4 |
| 5 | Scratch GUI の配備（静的配信）| §5 |
| 6 | 起動手順（毎回の運用）| §6 |

---

## 1. 環境確認

まず Pi の環境を確認する：

```bash
uname -m
python3 --version
cat /etc/os-release
```

期待する出力（今回の実機）：

| コマンド | 期待値 |
|---|---|
| `uname -m` | `armv7l`（32-bit）|
| `python3 --version` | `Python 3.7.x` |
| `cat /etc/os-release` | `VERSION_CODENAME=buster` |

この通りなら **§2 からそのまま進む**。`aarch64` / `bookworm` が出た場合だけ [付録A](#付録abookworm--64-bit-の場合uv-ルート) のルートを使う。

> **なぜ Pi では uv / venv を使わないのか**
> このプロジェクトの uv 環境は Python 3.12 前提（`requires-python = ">=3.12"`）で、Buster の Python 3.7 では lock を再現できない。さらに armv7l 向けの `opencv-python` wheel は PyPI に存在しない。
> 一方 tellomon の外部依存は **`cv2` と `tkinter` の2つだけ**（`shared/` は標準ライブラリのみ）で、どちらも apt で入る。pip でインストールするものが何も無いため、venv を作る意味もない。**system の `python3` で直接実行する**のが最もシンプルで壊れにくい。

---

## 2. ネットワーク設定（固定IP・Tello Wi-Fi）

Pi は **2系統** のネットワークにつながる。IP・ポートの正本は [../shared/ports.py](../shared/ports.py)。

| 系統 | 相手 | アドレス |
|---|---|---|
| Wi-Fi（2.4GHz）| Tello EDU（AP モード）| Tello 側は `192.168.10.1` 固定 |
| 有線 LAN | 中央ノートPC（`192.168.0.100`）| Pi#1〜#4 → `192.168.0.11`〜`.14`、予備機 Pi#10 → `192.168.0.20`（固定IP）|

設定内容：

1. **有線 LAN に固定IPを設定する**（Pi#N → `192.168.0.1N`、予備機は `.20`）。サブネット（前半3つ）を中央PCと必ず揃える。手順・考え方は [network-setup.md](network-setup.md) 参照。
2. **Wi-Fi を Tello の AP（`TELLO-XXXXXX`）に接続する**。Tello の電源を入れると SSID が出る。SSID は機体ごとに異なるので、各 Pi は**自分の担当機の SSID** にだけ接続する（設計書 §4.1）。
3. **UDP の疎通を確認する**（ビーコン `:11231`、映像転送 `:11112`〜`:11115`）。確認方法は [network-setup.md](network-setup.md) の「疎通確認の手順」参照。

---

## 3. パッケージ導入（apt）

### 3-1. apt source を legacy / archive に切り替える

Buster は EOL のため、通常の `raspbian.raspberrypi.org` を向いたままだと `apt update` が **`buster Release 404 Not Found`** で失敗する。**必ず既存ファイルをバックアップしてから**書き換えること。

```bash
sudo cp /etc/apt/sources.list /etc/apt/sources.list.bak
sudo cp /etc/apt/sources.list.d/raspi.list /etc/apt/sources.list.d/raspi.list.bak

echo "deb http://legacy.raspbian.org/raspbian buster main contrib non-free rpi" | sudo tee /etc/apt/sources.list
echo "deb http://archive.raspberrypi.org/debian buster main" | sudo tee /etc/apt/sources.list.d/raspi.list

sudo apt clean
sudo apt update
```

`apt update` がエラーなく完了すれば OK。

### 3-2. OpenCV と Tk を apt で入れる

```bash
sudo apt install -y python3-opencv python3-tk
```

- `python3-numpy` は `python3-opencv` の依存として自動で入る
- `python3-tk` は tellomon の GUI に**必須**（Desktop 版イメージなら導入済みのことが多いが、明示しておく）
- Pillow（PIL）は tellomon では使わないので不要

動作確認：

```bash
python3 -c "import cv2, tkinter; print('cv2', cv2.__version__)"
```

`cv2 4.1.0`（apt 版）が出れば準備完了。

---

## 4. リポジトリ取得と起動確認

```bash
git clone https://github.com/okadai-dsc/kids-drone-system.git
cd kids-drone-system
```

**インストール作業はこれで終わり**（`uv sync` / `pip install` / venv 作成は一切不要。`pyproject.toml` も Pi では使わないため、改変不要）。

起動確認（**必ずリポジトリのルートから**実行する。`--drone N` は Pi の号機番号に合わせる）：

```bash
python3 -m pi.tellomon --drone 2
```

Tk の GUI ウィンドウが開けば、この Pi のセットアップは完了。

> リポジトリのルートから `python3 -m` で起動することで、`pi/` と `shared/` がそのまま import される（プロジェクト自体のインストールは不要）。

---

## 5. Scratch GUI の配備（静的配信）

ビルドは開発機で行い、Pi には成果物（`build/`）を置いて配信するだけ（ビルド手順は [development.md](development.md) 参照）。

```bash
# 開発機の scratch-gui/build/ を Pi にコピーしてから
cd build && python3 -m http.server 8601
```

> `http.server` は Python 標準ライブラリなので、Buster の Python 3.7 でもそのまま動く。

子供のブラウザで `http://localhost:8601/` を開き、拡張ライブラリから「Drone Control Blocks」を選ぶ。ブロック実行 → tellomon の `http://localhost:8001/` 経由で Tello に届く。

---

## 6. 起動手順（毎回の運用）

1. Tello の電源を入れ、Pi の Wi-Fi を Tello の AP（`TELLO-XXXXXX`）に接続する
2. tellomon を起動する（リポジトリのルートから。`--drone N` は Pi の号機番号）：
   ```bash
   cd ~/kids-drone-system
   python3 -m pi.tellomon --drone 2
   ```
3. Scratch GUI を配信する：`cd build && python3 -m http.server 8601`
4. ブラウザで `http://localhost:8601/` を開き、Scratch の「つなぐ（command）」→「streamon」の順に実行
5. 中央PC 側でモニタ・YOLO が受信できているか確認する（[demo.md](demo.md) の判定表参照）

---

## トラブルシューティング早見表

| エラー / 症状 | 原因 | 対処 |
|---|---|---|
| `apt update` で `buster Release 404 Not Found` | Buster が EOL で通常の apt リポジトリから消えた | apt source を `legacy.raspbian.org` / `archive.raspberrypi.org` に変更（§3-1）|
| `ModuleNotFoundError: No module named 'pi'`（または `'shared'`）| リポジトリのルート以外から実行している | `cd ~/kids-drone-system` してから `python3 -m pi.tellomon ...`（§4）|
| `ModuleNotFoundError: No module named 'tkinter'` | Lite 版イメージ等で Tk が無い | `sudo apt install -y python3-tk`（§3-2）|
| `opencv-python ... doesn't have a source distribution or wheel for the current platform`（`manylinux_2_28_armv7l`）| pip / uv でインストールしようとした（armv7l 向け PyPI wheel は存在しない）| pip / uv は使わず apt の `python3-opencv` を使う（§3-2）|
| `uv run` 後に `ModuleNotFoundError: No module named 'cv2'` | `uv run` が `requires-python >=3.12` に従い Python 3.12 の venv を作り、apt の `cv2` が見えなくなった | **Buster の Pi では uv を使わない**。system の `python3` で直接実行する（§4）|
| Scratch GUI サーバーログの `GET /static/assets/... 200` や `/webapisample 404` | Scratch GUI 側の通常のアクセスログ | 異常ではない。ドローン Python 実行のエラーとは無関係。`^C Keyboard interrupt received, exiting.` も Ctrl+C でサーバーを止めただけ |

---

## 4台展開のヒント

1台目のセットアップが完了したら、**SD カードをまるごとクローン**して残り3台に配るのが最速。クローン後に変えるのは次の2点だけ：

- ホスト名（例：`pi1` → `pi2`）
- 有線 LAN の固定IP 末尾（`192.168.0.11` → `.12` 等）

起動時の `--drone N` は号機ごとに変えて実行する。

---

## 付録A：Bookworm / 64-bit の場合（uv ルート）

`uname -m` が `aarch64`（Raspberry Pi OS Bookworm 等）の場合は、開発機と同じ uv 環境がそのまま使える。

```bash
git clone https://github.com/okadai-dsc/kids-drone-system.git
cd kids-drone-system
uv sync
uv run python -m pi.tellomon --drone 2
```

> 長期運用するなら Buster より 64-bit / Bookworm への移行を推奨（apt が legacy/archive 頼みにならず、開発機と環境を統一できる）。今回の出展は手持ちが Buster のため §1〜§6 の apt ルートで延命する。

---

## 関連ドキュメント

- システム構成：[../README.md](../README.md)
- 開発ガイド（Scratch ビルド手順ほか）：[development.md](development.md)
- ネットワーク設定メモ（固定IP・疎通確認）：[network-setup.md](network-setup.md)
- 1台 E2E 検証の手順・判定：[demo.md](demo.md)
