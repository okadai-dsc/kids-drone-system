# 中央ノートPC（YOLO PC）セットアップガイド

本番で中央ノートPC（`192.168.0.100`、1台）が担う役割と、1台を動く状態にするまでの設定手順をまとめる。

中央ノートPC の役割は次の3つ（[../README.md](../README.md) のシステム構成参照）：

1. **yolo_proc ×4**（[../yolo/](../yolo/)）：Pi から転送された映像（UDP `:11112`〜`:11115`）を受信 → YOLO で犬猫検知 → 結果 JSON を送信（`:11212`〜`:11215`）
2. **YOLO 結果表示（yolo_display）**（[../operator_pc/yolo_display/](../operator_pc/yolo_display/)）：検知結果を Tello#1〜#4 の 4 区画でタイル表示
3. **ドローンモニタ（drone_monitor）**（[../operator_pc/drone_monitor/](../operator_pc/drone_monitor/)）：ビーコン（`:11231`）を受信して飛行マップ表示。**全機緊急着陸**もここから

> 2 と 3 は本番では **統合モニタ**（[../operator_pc/integrated_ui.py](../operator_pc/integrated_ui.py)、#34 / 設計 図5.4-1）として **1 画面・1 プロセス**で起動する（左=検知タイル、右=マップ＋全機緊急停止）。従来どおり個別起動も可能（切り分け用）。

> このマシンは **Windows ネイティブの Python** で動かす（WSL2 不可）。WSL2 は 1472 byte を超える UDP datagram を落とすため、画像入りの検知結果 JSON（数十KB）が届かない。ネイティブの loopback（MTU 65536）なら問題ない。

## 全体チェックリスト

| # | やること | 節 |
|---|---|---|
| 1 | 環境確認（Windows / uv）| §1 |
| 2 | ネットワーク設定（固定IP・ファイアウォール・Avast）| §2 |
| 3 | リポジトリ取得と Python 環境（uv 標準ルート）| §3 |
| 4 | 単体スモークテスト（Pi・Tello 不要）| §4 |
| 5 | 起動手順（毎回の運用）| §5 |

---

## 1. 環境確認

PowerShell で確認する：

```powershell
uv --version
```

uv が無ければインストールする（Python 本体は `uv sync` が自動で用意するので個別インストール不要）：

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

> このプロジェクトは **uv に統一**（`pip` / `requirements.txt` は使わない）。開発機と同じ環境がそのまま使える。Pi（Buster）だけが例外で apt ルート（[raspi-setup.md](raspi-setup.md)）。

---

## 2. ネットワーク設定（固定IP・ファイアウォール）

IP・ポートの正本は [../shared/ports.py](../shared/ports.py)。

| 項目 | 値 |
|---|---|
| 有線 LAN 固定IP | `192.168.0.100`（Pi#1〜#4 = `.11`〜`.14`、予備機 = `.20` と同一サブネット）|
| 受信 UDP（映像、Pi から）| `11112`〜`11115` |
| 受信 UDP（ビーコン、Pi から）| `11231` |
| loopback のみ（yolo_proc → 表示）| `11212`〜`11215`（外部開放不要）|

設定内容：

1. **有線 LAN に固定IP `192.168.0.100` を設定する**。手順・考え方は [network-setup.md](network-setup.md) 参照。ルーターのポート開放は不要（同一LAN内通信のため）。
2. **Windows ファイアウォールで inbound UDP を許可する**（管理者 PowerShell）：

   ```powershell
   New-NetFirewallRule -DisplayName "KidsDrone UDP" -Direction Inbound `
     -Protocol UDP -LocalPort 11112-11115,11231 -Action Allow
   ```

3. **⚠️ Avast 等のセキュリティソフトに注意**：このPCで **Avast が Tello 映像（inbound UDP）をブロックした実績がある**。映像が届かない場合はまず Avast を疑い、python.exe を例外に追加するか、検証中は一時停止する。
4. Pi を接続したら疎通を確認する。確認方法は [network-setup.md](network-setup.md) の「疎通確認の手順」参照。

---

## 3. リポジトリ取得と Python 環境

```powershell
git clone https://github.com/okadai-dsc/kids-drone-system.git
cd kids-drone-system
uv sync
```

`uv sync` がエラーなく完了すれば OK（Python 3.12 と依存パッケージが `.venv` に入る）。

---

## 4. 単体スモークテスト（Pi・Tello 不要）

このマシン単体で「YOLO PC は完成」と判定できる確認。上から順に実行する。

### 4-1. YOLO 結果表示の UI 確認

```powershell
uv run python yolo_display.py --no-udp
```

4 区画の画面が開き、右上の `JSON読込` でリポジトリルートの `fake_detection.json` を読むと `Tello#1` の `ねこ` セルが緑になり 3 秒でグレーに戻れば OK。

### 4-2. loopback UDP 疎通

2 つのターミナルで：

```powershell
# ターミナル 1
uv run python yolo/udp_receiver.py --drone 1

# ターミナル 2
uv run python yolo/udp_sender.py --drone 1
```

ターミナル 1 に `Parsed JSON dict: {...}` が出れば OK。

### 4-3. YOLO 推論（★会場入り前に必ずオンラインで1回実行）

`yolov8n.pt`（モデルファイル）は git 管理外のため、**初回実行時に ultralytics がインターネットから自動ダウンロード**する。会場がオフラインだと当日詰むので、この確認は必ず事前にオンライン環境で済ませること。

```powershell
# ターミナル 1
uv run python yolo/udp_receiver.py --drone 1 --max-messages 1 --timeout 20

# ターミナル 2（猫か犬の画像を1枚用意する）
uv run python yolo/yolo_proc.py --drone 1 --image path\to\cat_or_dog.jpg
```

yolo_proc 側に `sent result -> ...` が出て、受信側に `detections`（`cat` / `dog`）入り JSON が表示されれば OK。リポジトリルートに `yolov8n.pt` ができていることも確認する。

### 4-4. 統合モニタとダミービーコン

```powershell
# ターミナル 1
uv run python -m operator_pc.integrated_ui

# ターミナル 2
uv run python -m shared.tools.fake_beacon
```

1 画面に検知タイル（2×2）＋飛行マップ＋「全機緊急停止」ボタンが表示され、マップ上で 4 台分のアイコンが動けば OK。**ここまで通れば YOLO PC のセットアップは完了。**

> 切り分け用に個別起動も可能：`uv run python -m operator_pc.drone_monitor` / `uv run python yolo_display.py`

> Pi・実機をつないだ通し確認（映像転送 → 検知 → 表示）の手順と判定は [demo.md](demo.md) 参照。

---

## 5. 起動手順（毎回の運用）

リポジトリのルートで、ターミナルを分けて起動する：

```powershell
# ① YOLO 推論 ×4（号機ごとに1プロセス。検収 P1 = 5fps 以上なので --rate 5）
uv run python yolo/yolo_proc.py --drone 1 --rate 5
uv run python yolo/yolo_proc.py --drone 2 --rate 5
uv run python yolo/yolo_proc.py --drone 3 --rate 5
uv run python yolo/yolo_proc.py --drone 4 --rate 5

# ② 統合モニタ（検知タイル＋飛行マップ＋全機緊急停止 を 1 画面で）
uv run python -m operator_pc.integrated_ui
```

- 映像は Pi 側で Scratch の「streamon」が実行されて初めて流れてくる（それまで yolo_proc は待機）
- 連続稼働時のメトリクスの見方（`read_fps` / `infer_fps` / `rss_mb`）は [../yolo/README.md](../yolo/README.md) 参照

---

## トラブルシューティング早見表

| エラー / 症状 | 原因 | 対処 |
|---|---|---|
| Pi から映像が届かない（yolo_proc が無反応）| ①Pi 側で `streamon` 未実行 ②ファイアウォール ③**Avast のブロック（実績あり）** | ① Scratch で streamon ② §2-2 のルール確認 ③ Avast に python 例外追加 or 一時停止 |
| 検知結果が yolo_display に出ない（WSL 上で実行している）| WSL2 は UDP > 1472B を落とす。画像入り JSON は届かない | **Windows ネイティブで実行する**（本ガイドの前提）|
| 初回 `yolo_proc` 実行でモデルのダウンロードに失敗 | オフライン環境で `yolov8n.pt` が無い | オンライン環境で §4-3 を実行して事前ダウンロード |
| Pi 側の IP・自分の IP が想定と違う | 実ネットワークと [../shared/ports.py](../shared/ports.py) の不一致 | ports.py を1箇所修正する（正本主義）|
| `Address already in use` 等でポートが開けない | 同じ `--drone N` のプロセス二重起動 | 既存プロセスを終了してから起動し直す |

---

## 関連ドキュメント

- システム構成：[../README.md](../README.md)
- Raspberry Pi セットアップ（Buster 標準ルート）：[raspi-setup.md](raspi-setup.md)
- ネットワーク設定メモ（固定IP・疎通確認）：[network-setup.md](network-setup.md)
- 1台 E2E デモの手順・判定：[demo.md](demo.md)
- YOLO まわりの詳細な検証手順（連続稼働・2多重ほか）：[../yolo/README.md](../yolo/README.md)

> **検証状況**：この文書はまだ実機での通し検証を行っていない。上から実行して詰まった箇所は文書に反映し、完走したらここに検証日を記録すること。
