# YOLO 結果表示（yolo_display）

中央ノートPCで YOLO 検知結果を表示する Tkinter アプリです。

## 起動

```bash
uv sync
uv run python yolo_display.py
```

モジュールとしても起動できます。

```bash
uv run python -m operator_pc.yolo_display
```

UDP を使わず UI だけ確認する場合:

```bash
uv run python yolo_display.py --no-udp
```

## 画面

- 画面中央: Tello#1〜#4 の bbox 描画済み画像を 4 区画で表示
- 各画像区画の右上: `未検知` / `ねこ` / `いぬ` の小さな状態ラベル
- 初期状態: グレーの状態ラベル + 通常枠
- 検知状態: 緑の状態ラベル + 緑枠
- 検知後 3 秒で状態ラベルと枠が通常表示へ戻る

## ダミー JSON 確認

アプリ右上の `JSON読込` を押すと、リポジトリルートの `fake_detection.json` を読み込みます。
`Tello#1` の `ねこ` セルが緑になり、3 秒後にグレーへ戻れば OK です。

## UDP 確認

既定では `11212〜11215` を待ち受けます。

```bash
uv run python yolo_display.py
```

別ターミナルで YOLO 結果 JSON を送ります。

```bash
uv run python yolo/udp_sender.py --drone 1
```

`detections` に `cat` または `dog` が含まれていれば、対応するセルが緑になります。
`image_b64` に JPEG base64 が含まれていれば、対応する Tello の画像区画に表示されます。

待受ポートを指定したい場合:

```bash
uv run python yolo_display.py --ports 11212,11213
```

## 仕様

- 検知色: `#4CAF50`
- 通常色: `#9E9E9E`
- 警告色: `#FF9800`
- 異常色: `#F44336`
- 画像区画タイトル: 16pt
- 状態ラベル: 13pt
- 状態表示/ボタン: 14pt 以上
- 表示語: `ねこ` / `いぬ`
