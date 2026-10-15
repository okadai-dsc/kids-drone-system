# デモ手順（M2 / 1台 E2E 実飛行デモ）

中間レビュー用。Scratch → 実飛行 → YOLO 検知 → 中央UI 表示 を 1 台で通す手順。

> 関連 issue: #6（C6 E2E 結合）／ ポート定義: [shared/ports.py](../shared/ports.py)

## 構成と役割

リハ構成（手元に **開発PC + YOLO PC + Tello#1**、Raspberry Pi 無し）では、開発PC を Pi#1 の代役にする。

| マシン | 役割 | 起動するもの |
|---|---|---|
| **開発PC**（Windows + WSL2） | Pi#1 代役 | ① Tello WiFi 接続 → ② tellomon → ③ Scratch（子供UI） |
| **YOLO PC**（`192.168.0.100`） | 中央ノートPC | ④ yolo_proc ⑤ YOLO結果表示（ダミー） ⑥ ドローンモニタ |
| **Tello#1** | 機体 | WiFi AP `192.168.10.1` |

ネットワーク前提：開発PC は **Tello WiFi（192.168.10.x）** と **YOLO PC への有線LAN（192.168.0.x）** の 2 系統に接続する。YOLO PC は `192.168.0.100`。

---

## 開発PC で起動するもの

### 事前準備（WSL2 から Tello を制御するため）

WSL2（mirrored networking）では Hyper-V ファイアウォールが LAN→WSL2 の inbound UDP を既定でブロックするため、管理者 PowerShell で許可する（再起動で消える場合あり）。

```powershell
New-NetFirewallHyperVRule -Name "TelloUDP" -Direction Inbound `
  -VMCreatorId '{40E0AC32-46A5-438A-A0B2-2B479E8F2E90}' `
  -Protocol UDP -LocalPorts 8889,8890,11111
```

Windows を Tello の WiFi AP（`TELLO-XXXXXX`）に接続したうえで、WSL から疎通確認：

```bash
ping -c2 192.168.10.1   # 応答が返れば OK
```

### ① tellomon（リポジトリルートから）

Tk GUI が開く（WSLg もしくは X サーバが必要）。

```bash
uv run python -m pi.tellomon --drone 1
```

### ② Scratch（子供UI）

セットアップは [docs/development.md](development.md) を参照。ドローン拡張のブロックが tellomon の `http://<開発PCのIP>:8001/...` を叩く。

---

## YOLO PC で起動するもの（`192.168.0.100`、3 ターミナル）

```bash
# ④ YOLO 推論（:11112 で映像受信 → 検知 → 127.0.0.1:11212 へ結果送信）
uv run python yolo/yolo_proc.py --drone 1

# ⑤ YOLO 結果表示（ダミー受信機。yolo_display は未マージのため代用）
uv run python yolo/udp_receiver.py --drone 1

# ⑥ ドローンモニタ（:11231 でビーコン受信、マップにアイコン表示）
uv run python -m operator_pc.drone_monitor
```

---

## デモの流れ & 成功条件

| # | 操作 | 成功の判定 |
|---|---|---|
| 1 | Scratch「つなぐ（command）」 | tellomon GUI にバッテリ等の status 表示、`ok` 応答 |
| 2 | Scratch「streamon」 | tellomon のモニタ窓に Tello カメラ映像が出る |
| 3 | （②の映像転送が有効）| **YOLO PC の yolo_proc が毎秒ログ出力**（例 `... Tello#1 detections=[]`）＝生 H.264 デコード成功 |
| 4 | Tello カメラに**猫／犬の写真**を見せる | yolo_proc ログが `detections=['cat']` ／ `['dog']` |
| 5 | — | ⑤ ダミー受信機に JSON（`detections` 入り）が表示 |
| 6 | — | ⑥ モニタに drone#1 アイコンが表示・移動（ビーコン受信） |
| 7 | Scratch takeoff → forward → land | 実機が指示通り飛ぶ |

**最重要の成功条件** = #3（YOLO PC で生 H.264 が opencv でデコードできる）と #4（犬猫検知が出る）。これが issue #6 のリスク項目そのもの。

---

## 注意点・既知の制約

- **映像転送は streamon 連動**：tellomon は `streamon` 受信時に YOLO PC への転送を有効化（`streamoff` で停止）。`streamon` を押さないと YOLO PC に映像は流れない。
- **転送先 YOLO PC の IP は `NOTE_PC_IP = 192.168.0.100` 固定**：YOLO PC の IP が異なる場合は [shared/ports.py](../shared/ports.py) を 1 箇所修正する。
- **WSL2 の UDP > 1472B ドロップ**：⑤の結果表示は画像入り JSON が大きいため、**YOLO PC（ネイティブ、loopback MTU 65536）で動かせば問題なし**。WSL 機で受けると画像入りパケットは落ちる。
- **`yolo_display` は develop 未マージ**（`4-yolo-display` ブランチ）。本番表示はダミー受信機 `yolo/udp_receiver.py` で代用。
- **フォールバック**：opencv が生 H.264 を読めない場合は ffmpeg を中継させる（issue #6 リスク欄）。まずは素の opencv 読み取りを試す。
