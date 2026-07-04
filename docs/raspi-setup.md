# Raspberry Pi セットアップガイド（Pi 側で必要な設定のすべて）

本番で Raspberry Pi（4台）が担う役割と、Pi 1台を動く状態にするまでの設定手順をまとめる。

Pi の役割は次の2つ（[../README.md](../README.md) のシステム構成参照）：

1. **tellomon**（[../pi/tellomon/](../pi/tellomon/)）：Tello 制御・映像の YOLO PC 転送・ビーコン送信・Scratch 向け HTTP API（`:8001`）
2. **Scratch GUI の静的配信**（`:8601`）：子供が触る UI。ビルド済み `build/` を配信するだけ

## 全体チェックリスト

| # | やること | 節 |
|---|---|---|
| 1 | 環境確認（OS / アーキテクチャ / Python）| §1 |
| 2 | ネットワーク設定（固定IP・Tello Wi-Fi）| §2 |
| 3 | リポジトリ取得と Python 環境（標準ルート）| §3 |
| 4 | **Buster / armv7l の場合の互換セットアップ** | §4 |
| 5 | Scratch GUI の配備（静的配信）| §5 |
| 6 | 起動手順（毎回の運用）| §6 |

---

## 1. 環境確認

まず Pi の環境を確認し、§3（標準）と §4（Buster 互換）のどちらのルートかを決める。

```bash
uname -m
python3 --version
uv --version
cat /etc/os-release
```

| `uname -m` | OS | ルート |
|---|---|---|
| `aarch64`（64-bit）| Bookworm 等の新しい OS | **§3 標準ルート**（`uv sync` が使える）|
| `armv7l`（32-bit）| Buster 等の古い OS | **§4 Buster / armv7l troubleshooting**（apt 版 OpenCV + venv 直接実行）|

> `armv7l` の場合、PyPI に `opencv-python` の対応 wheel が存在しないため、通常の `uv sync` / `uv run` は失敗する。§4 の手順に従うこと。

---

## 2. ネットワーク設定（固定IP・Tello Wi-Fi）

Pi は **2系統** のネットワークにつながる。IP・ポートの正本は [../shared/ports.py](../shared/ports.py)。

| 系統 | 相手 | アドレス |
|---|---|---|
| Wi-Fi（2.4GHz）| Tello EDU（AP モード）| Tello 側は `192.168.10.1` 固定 |
| 有線 LAN | 中央ノートPC（`192.168.0.100`）| Pi#1〜#4 → `192.168.0.11`〜`.14`（固定IP）|

設定内容：

1. **有線 LAN に固定IPを設定する**（Pi#N → `192.168.0.1N`）。サブネット（前半3つ）を中央PCと必ず揃える。手順・考え方は [network-setup.md](network-setup.md) 参照。
2. **Wi-Fi を Tello の AP（`TELLO-XXXXXX`）に接続する**。Tello の電源を入れると SSID が出る。
3. **UDP の疎通を確認する**（ビーコン `:11231`、映像転送 `:11112`〜`:11115`）。確認方法は [network-setup.md](network-setup.md) の「疎通確認の手順」参照。

---

## 3. リポジトリ取得と Python 環境（標準ルート：Bookworm / 64-bit）

```bash
git clone https://github.com/okadai-dsc/kids-drone-system.git
cd kids-drone-system
uv sync
```

起動確認（`--drone N` は Pi の号機番号に合わせる）：

```bash
uv run python -m pi.tellomon --drone 2
```

これが通ればこの節で完了。**`opencv-python` のインストールで失敗する場合は §4 へ。**

---

## 4. Raspberry Pi OS Buster / armv7l troubleshooting

Raspberry Pi OS **Buster**（32-bit ARM、`uname -m` が `armv7l`）では §3 の標準ルートが通らない。
このセクションの手順で **apt 版パッケージ + `.venv/bin/python` 直接実行**に切り替える。

> ⚠️ これは**延命対応**。可能なら Raspberry Pi OS **64-bit / Bookworm** への移行を推奨。Buster は apt リポジトリも legacy/archive 頼みで、依存関係やセキュリティ更新の面で長期運用には向かない。

### 何が起きるか（症状）

- `uv run python -m pi.tellomon --drone 2` 実行時、PyPI の `opencv-python==4.13.0.92` のインストールに失敗する。エラーは「現在の platform（`manylinux_2_28_armv7l`）向けの wheel / source distribution が存在しない」というもの。**armv7l 向けの `opencv-python` wheel は PyPI に存在しない**ため、apt 版 OpenCV を使う。
- `pillow==12.0.0` も Buster + 32-bit ARM ではソースビルドが `command '/usr/bin/cc' failed` で失敗する。同様に apt 版を使う。
- Buster 標準の `/usr/bin/python3` は **Python 3.7.3** で、プロジェクトの `requires-python = ">=3.12"` と合わない。そのため `uv run` による sync は使えず、venv を明示的に作って直接実行する。

### 4-1. apt source を legacy / archive に切り替える

Buster は EOL のため、通常の `raspbian.raspberrypi.org` を向いたままだと `apt update` が **`buster Release 404 Not Found`** で失敗する。**必ず既存ファイルをバックアップしてから**書き換えること。

```bash
sudo cp /etc/apt/sources.list /etc/apt/sources.list.bak
sudo cp /etc/apt/sources.list.d/raspi.list /etc/apt/sources.list.d/raspi.list.bak

echo "deb http://legacy.raspbian.org/raspbian buster main contrib non-free rpi" | sudo tee /etc/apt/sources.list
echo "deb http://archive.raspberrypi.org/debian buster main" | sudo tee /etc/apt/sources.list.d/raspi.list

sudo apt clean
sudo apt update
```

### 4-2. OpenCV / Pillow / NumPy を apt で入れる

```bash
sudo apt install -y python3-opencv python3-pil python3-numpy
```

> tellomon は GUI に tkinter も使う。Raspberry Pi OS Desktop なら標準で入っているが、`import tkinter` が失敗する場合は `sudo apt install -y python3-tk` を追加。

### 4-3. pyproject.toml の依存の扱い

Buster / armv7l 向け運用では、PyPI 版の `opencv-python` / `pillow` を**インストール対象に入れない**。ルートの [../pyproject.toml](../pyproject.toml) の `dependencies` で該当行をコメントアウトする：

```toml
dependencies = [
    # opencv-python==...   # Buster/armv7l では apt の python3-opencv を使う
    # pillow==...          # Buster/armv7l では apt の python3-pil を使う
]
```

platform marker で「armv7l のときだけ除外」と書くこともできる：

```toml
dependencies = [
    'opencv-python; platform_machine != "armv7l"',
    'pillow; platform_machine != "armv7l"',
]
```

> ⚠️ ただし、この marker を書いても **Buster の Python 3.7 と `requires-python = ">=3.12"` の不一致は解消しない**。Buster では次の 4-4 の venv + 直接実行を使うこと。

### 4-4. venv を作る（システムの python3 + system-site-packages）

apt で入れた `cv2` / `PIL` が見える venv を明示的に作る。ポイントは `--python /usr/bin/python3`（Buster の 3.7.3 を使う）と `--system-site-packages`（apt パッケージを参照する）。

```bash
cd ~/kids-drone-system
rm -rf .venv
uv venv --python /usr/bin/python3 --system-site-packages
```

動作確認：

```bash
.venv/bin/python -c "import sys; print(sys.version)"
.venv/bin/python -c "import cv2; print('cv2', cv2.__version__)"
.venv/bin/python -c "from PIL import Image; print('Pillow OK')"
```

`3.7.3`、`cv2 4.1.0`（apt 版）、`Pillow OK` が出れば準備完了。

### 4-5. 実行する

`uv run` ではなく **venv の python を直接**使う：

```bash
.venv/bin/python -m pi.tellomon --drone 2
```

### ⚠️ 注意：Buster では `uv run` を使わない

- Buster 環境では **`uv run python -m ...` を使わない**こと。
- `uv run` は sync 時にプロジェクトの `requires-python = ">=3.12"` に従って **Python 3.12 の `.venv` を再作成**する。その venv からは apt で入れた `cv2` / `PIL` が見えなくなり、**`ModuleNotFoundError: No module named 'cv2'` が再発**する。
- `uv run --no-sync` なら venv を作り直さないため確認用には使える（`cv2 4.1.0` の import を確認済み）。ただし運用では **`.venv/bin/python` 直接実行が安全**。

### 遭遇したエラーと対処の早見表

| エラー / 症状 | 原因 | 対処 |
|---|---|---|
| `opencv-python ... doesn't have a source distribution or wheel for the current platform`（`manylinux_2_28_armv7l`）| armv7l 向けの PyPI wheel が存在しない | apt の `python3-opencv` を使う（4-1〜4-2）|
| `apt update` で `buster Release 404 Not Found` | Buster が EOL で通常の apt リポジトリから消えた | apt source を `legacy.raspbian.org` / `archive.raspberrypi.org` に変更（4-1）|
| `pillow ... command '/usr/bin/cc' failed` | Buster + 32-bit ARM で新しい Pillow のソースビルドが通らない | PyPI ビルドを避け、apt の `python3-pil` を使う（4-2）|
| `uv run` 後に `ModuleNotFoundError: No module named 'cv2'` | `uv run` が `requires-python >=3.12` に従い Python 3.12 の venv を再作成し、apt の `cv2` が見えなくなった | `.venv/bin/python` を直接使う（4-4〜4-5）。venv が壊れたら 4-4 で作り直す |
| Scratch GUI サーバーログの `GET /static/assets/... 200` や `/webapisample 404` | Scratch GUI 側の通常のアクセスログ | 異常ではない。ドローン Python 実行のエラーとは無関係。`^C Keyboard interrupt received, exiting.` も Ctrl+C でサーバーを止めただけ |

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
2. tellomon を起動する（`--drone N` は Pi の号機番号）
   - 標準ルート（§3）：`uv run python -m pi.tellomon --drone 2`
   - Buster 互換ルート（§4）：`.venv/bin/python -m pi.tellomon --drone 2`
3. Scratch GUI を配信する：`cd build && python3 -m http.server 8601`
4. ブラウザで `http://localhost:8601/` を開き、Scratch の「つなぐ（command）」→「streamon」の順に実行
5. 中央PC 側でモニタ・YOLO が受信できているか確認する（[demo.md](demo.md) の判定表参照）

---

## 関連ドキュメント

- システム構成：[../README.md](../README.md)
- 開発ガイド（Scratch ビルド手順ほか）：[development.md](development.md)
- ネットワーク設定メモ（固定IP・疎通確認）：[network-setup.md](network-setup.md)
- 1台 E2E 検証の手順・判定：[demo.md](demo.md)
