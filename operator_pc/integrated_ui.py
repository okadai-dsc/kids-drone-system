"""統合モニタ（#34 / 設計書 5.4 図5.4-1・検収 F12・F13）。

検知タイル(2×2)＋飛行マップ＋全機緊急停止ボタンを 1 画面に統合する。
左ペイン = YOLO 検知タイル（yolo_display と共通実装）、
右ペイン = 飛行マップ＋全機緊急停止（drone_monitor と共通実装）。

    uv run python -m operator_pc.integrated_ui           # 本番: UDP 待受あり
    uv run python -m operator_pc.integrated_ui --no-udp  # UI 確認のみ（Pi 不要）

別ターミナルで `uv run python -m shared.tools.fake_beacon` を流すと
マップ上のアイコンが動く（単体スモークは docs/yolopc-setup.md §4 参照）。
"""

from __future__ import annotations

import argparse
import queue
import tkinter as tk

from shared.ports import BEACON_PORT, YOLO_TO_DISPLAY_PORTS
from shared.schemas import YoloResult

from .drone_monitor.__main__ import MonitorApp
from .drone_monitor.receiver import BeaconReceiver, BeaconStore
from .yolo_display.__main__ import COLOR_BG, YoloDisplayApp
from .yolo_display.receiver import YoloResultReceiver


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="統合モニタ（検知タイル＋飛行マップ＋全機緊急停止）"
    )
    parser.add_argument("--host", default="0.0.0.0", help="UDP 待受ホスト（既定: 0.0.0.0）")
    parser.add_argument(
        "--beacon-port",
        type=int,
        default=BEACON_PORT,
        help=f"ビーコン待受ポート（既定: {BEACON_PORT}）",
    )
    parser.add_argument(
        "--yolo-ports",
        default=",".join(str(YOLO_TO_DISPLAY_PORTS[n]) for n in range(1, 5)),
        help="YOLO 結果待受ポートのカンマ区切り",
    )
    parser.add_argument("--no-udp", action="store_true", help="UDP受信を起動しない（UI確認用）")
    return parser.parse_args()


def build_ui(
    root: tk.Tk,
    inbox: queue.Queue[YoloResult],
    store: BeaconStore,
    yolo_receiver: YoloResultReceiver | None = None,
) -> tuple[YoloDisplayApp, MonitorApp]:
    """1 画面に左右ペインを組み、両アプリを埋め込む（設計 図5.4-1）。"""
    root.title("統合モニタ")
    root.configure(bg=COLOR_BG)
    # 画面からはみ出さない範囲で最大化に近いサイズにする（開発機と本番機で解像度が違う）
    width = min(1800, root.winfo_screenwidth() - 40)
    height = min(800, root.winfo_screenheight() - 80)
    root.geometry(f"{width}x{height}")
    root.minsize(1100, 620)

    left = tk.Frame(root, bg=COLOR_BG)
    left.grid(row=0, column=0, sticky="nsew")
    right = tk.Frame(root, bg=COLOR_BG)
    right.grid(row=0, column=1, sticky="ns", padx=(0, 12))
    root.rowconfigure(0, weight=1)
    root.columnconfigure(0, weight=1)  # タイル側だけ伸縮（マップは固定縮尺 1m=100px）
    root.columnconfigure(1, weight=0)

    yolo_app = YoloDisplayApp(left, inbox, receiver=yolo_receiver)
    monitor_app = MonitorApp(right, store)
    root.protocol("WM_DELETE_WINDOW", yolo_app.close)
    return yolo_app, monitor_app


def main() -> None:
    args = _parse_args()

    inbox: queue.Queue[YoloResult] = queue.Queue()
    store = BeaconStore()
    yolo_receiver: YoloResultReceiver | None = None
    beacon_receiver: BeaconReceiver | None = None
    if not args.no_udp:
        ports = [int(p.strip()) for p in args.yolo_ports.split(",") if p.strip()]
        yolo_receiver = YoloResultReceiver(inbox, host=args.host, ports=ports)
        yolo_receiver.start()
        beacon_receiver = BeaconReceiver(store, host=args.host, port=args.beacon_port)
        beacon_receiver.start()

    root = tk.Tk()
    yolo_app, _monitor_app = build_ui(root, inbox, store, yolo_receiver=yolo_receiver)
    try:
        root.mainloop()
    finally:
        yolo_app.close()  # yolo_receiver の停止も担う
        if beacon_receiver is not None:
            beacon_receiver.stop()


if __name__ == "__main__":
    main()
