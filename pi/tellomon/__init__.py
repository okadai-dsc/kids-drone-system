"""Pi 上の Tello 制御プログラム（tellomon）。

既存 tello/tellomon.py を移植。Scratch からの HTTP 制御（:8001）を受け、
Tello へコマンド送信／映像を YOLO PC へ転送し、状態ビーコンをノートPCへ送る。
`uv run python -m pi.tellomon [--drone N]` で起動（リポジトリルートから）。
"""
