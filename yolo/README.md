# YOLO PC UDP疎通確認スクリプト

YOLO 推論プロセスと、結果表示アプリ（`yolo_display`）の間における UDP 通信の動作を確認するためのダミースクリプトです。

`shared/ports.py` に定義されている YOLO から結果表示への通信ポート（`YOLO_TO_DISPLAY_PORTS`）を使用して動作します。

- **`udp_receiver.py`**: YOLO結果表示側のダミー受信機
- **`udp_sender.py`**: YOLO推論プロセス側のダミー送信機

## 動作確認手順

ローカルで 2 つのターミナルを起動して実行します。

### 1. 受信側の起動（ターミナル 1）

デフォルトでは、Tello#1 用のポート（`11212`）で待ち受けを開始します。

```bash
uv run python yolo/udp_receiver.py --drone 1
```

### 2. 送信側の起動（ターミナル 2）

デフォルトでは、Tello#1 用のポート（`127.0.0.1:11212`）に向けてダミーデータを送信します。

```bash
uv run python yolo/udp_sender.py --drone 1
```

送信が完了すると、ターミナル 1（受信側）に以下のような出力が表示され、正常に JSON パケットを受信およびパースできたことが確認できます。

```text
Received 5 bytes from ('127.0.0.1', 52345)
Raw bytes: b'hello'

Received 178 bytes from ('127.0.0.1', 52345)
Parsed JSON dict: {'tello_id': 'Tello#1', 'ts': '2026-06-15T21:23:45.678', 'detections': [{'label': 'cat', 'confidence': 0.95, 'bbox': [100, 100, 200, 200]}], 'image_b64': '<dummy_base64_string>'}
```

### 画像相当サイズの送受信確認

Issue #10 の `YoloResult` は `image_b64` に bbox 描画済み JPEG を入れるため、通常のダミー JSON より大きくなります。
実画像を用意せずに、画像入り JSON と同じサイズ帯の UDP datagram を流す場合は以下を使います。

```bash
# ターミナル 1: 50KB 未満の JSON を1件受けて終了
uv run python yolo/udp_receiver.py --drone 1 --max-messages 1 --timeout 5

# ターミナル 2: UDP datagram 全体が 50000 byte の JSON を送る
uv run python yolo/udp_sender.py --drone 1 --skip-hello --json-bytes 50000
```

受信側に `Received 50000 bytes` と `image_b64 length: ... chars` が表示されれば、
実画像 base64 入りの結果 JSON と同じデータ量で送受信できています。
`--image-bytes 37500` のように指定すると、JPEG 圧縮後の画像サイズ相当のバイト列を base64 化して送れます。

## オプション

両スクリプトは以下のコマンドライン引数をサポートしています。

- `--drone [1-4]`: 対象のドローン番号を指定します。指定した番号に応じてポートが自動で切り替わります（1: `11212` / 2: `11213` / 3: `11214` / 4: `11215`）。
- `--port [port]`: 任意のポート番号を直接指定して通信を行いたい場合に使用します（指定時は `--drone` の自動設定より優先されます）。
- `--host [host]`: （送信側のみ）送信先のホストを指定します（既定: `127.0.0.1`）。実機検証時などに別 PC から送信する場合に指定します。
- `--json-bytes [bytes]`: （送信側のみ）送信する JSON datagram 全体のバイト数を指定します。
- `--image-bytes [bytes]`: （送信側のみ）JPEG 相当のバイト数を base64 化して `image_b64` に入れます。
- `--skip-hello`: （送信側のみ）疎通用の `hello` を送らず JSON だけ送ります。
- `--max-messages [count]`: （受信側のみ）指定数を受信したら終了します。
- `--timeout [sec]`: （受信側のみ）受信タイムアウトを指定します。

---

# yolo_proc.py — 受信→推論→送信 を1プロセスで (#10)

Pi から転送された Tello 映像（UDP 生 H.264）を受信し、各フレームを YOLO で推論、
**犬猫（cat/dog）の検知結果**を `shared.schemas.YoloResult` の JSON にして
結果表示（yolo_display）へ UDP 送信する。

```bash
# 本番（映像を受信して 1Hz で結果送信）
uv run python yolo/yolo_proc.py --drone 1
#   udp://@0.0.0.0:11112 で映像受信 → 127.0.0.1:11212 へ結果送信

# 映像ストリーム無しでの単発テスト/デモ（画像1枚を推論して1回送信）
uv run python yolo/yolo_proc.py --drone 1 --image path/to/dog.jpg
```

`udp_receiver.py` を相手に起動すれば送受信を確認できる。主なオプション：
`--video-port` / `--display-host` / `--display-port` / `--model`（既定 `yolov8n.pt`）/
`--conf`（信頼度しきい値）/ `--max-width` `--jpeg-quality`（送信画像サイズ調整、目標 < 50KB）/ `--rate`（送信 Hz）。

### 次の確認: 実画像を YOLO 推論して送る

画像ファイルがある場合は、映像 UDP の前に `--image` で issue #10 の送信部分を確認できます。

```bash
# ターミナル 1
uv run python yolo/udp_receiver.py --drone 1 --max-messages 1 --timeout 20

# ターミナル 2
uv run python yolo/yolo_proc.py --drone 1 --image path/to/cat_or_dog.jpg
```

`yolo_proc.py` 側に `sent result -> ...: ... bytes, image_b64=... chars` が表示されます。
50KB を超える場合は `--max-width` を下げるか `--jpeg-quality` を下げて調整します。

### ダミー映像を UDP 11112 に流して確認する

実機や Pi 側の映像転送がまだ無い場合は、`udp_video_sender.py` で UDP 映像入力を代用できます。
初回は `imageio-ffmpeg` が入るように `uv sync --package yolo_proc` を実行してください。

```bash
# 初回のみ
uv sync --package yolo_proc

# ターミナル 1: 結果 JSON の受信
uv run python yolo/udp_receiver.py --drone 1

# ターミナル 2: UDP 11112 を読む yolo_proc
uv run python yolo/yolo_proc.py --drone 1

# ターミナル 3: ダミー映像を UDP 11112 に送る
uv run python yolo/udp_video_sender.py --drone 1
```

猫/犬画像を使って UDP 経由でも検知まで確認したい場合は、送信側に画像を指定します。

```bash
uv run python yolo/udp_video_sender.py --drone 1 --image path/to/cat_or_dog.jpg
```

## 注意（WSL2 開発環境）

WSL2（mirrored networking）では **1472 byte を超える UDP datagram が落ちる**ため、
画像入り（base64 JPEG ≈ 数十 KB）の YoloResult は WSL2 上の loopback では届かない。
検知ロジック・JSON 送受信自体は正常（小さいパケットや実機/ネイティブ環境では問題なし）。
本番の中央ノートPC（ネイティブ）の loopback は MTU 65536 のため画像入りでも送れる。
