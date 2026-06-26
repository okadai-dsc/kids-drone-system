"""ドローンモニタ本体（Tkinter）。

    uv run python -m operator_pc.drone_monitor              # 0.0.0.0:11231 で待受
    uv run python -m operator_pc.drone_monitor --host 127.0.0.1

別ターミナルで `uv run python -m shared.tools.fake_beacon` を流すと
4 台分のアイコンがマップ上を動く。
"""

from __future__ import annotations

import argparse
import math
import threading
import tkinter as tk
from tkinter import messagebox

from shared.ports import BEACON_PORT
from shared.schemas import CAGE_X, CAGE_Y

from ..emergency import emergency_all
from .receiver import BeaconReceiver, BeaconStore

# --- 表示パラメータ（仕様詳細ドラフト.md §3.4: 1m = 100px）-------------
SCALE = 100  # px / m
MARGIN = 20  # マップ外周の余白(px)
MAP_W = int((CAGE_X[1] - CAGE_X[0]) * SCALE)  # 650
MAP_H = int((CAGE_Y[1] - CAGE_Y[0]) * SCALE)  # 350
ICON_R = 14  # アイコン半径(px)
REFRESH_MS = 200  # 再描画間隔

# 配色（仕様詳細ドラフト.md §4.2）
COLOR_BG = "#FAFAFA"
COLOR_CAGE = "#9E9E9E"
COLOR_GRID = "#E0E0E0"
COLOR_DRONE = "#42A5F5"
COLOR_TEXT = "#212121"


def cage_to_screen(x: float, y: float) -> tuple[float, float]:
    """ケージ座標(m, 左下原点) → 画面座標(px, 左上原点)。y を上下反転する。"""
    sx = MARGIN + (x - CAGE_X[0]) * SCALE
    sy = MARGIN + (CAGE_Y[1] - y) * SCALE  # y=0(下) が画面下に来るよう反転
    return sx, sy


class MonitorApp:
    def __init__(self, root: tk.Tk, store: BeaconStore) -> None:
        self.root = root
        self.store = store
        root.title("ドローンモニタ")

        self.canvas = tk.Canvas(
            root,
            width=MAP_W + MARGIN * 2,
            height=MAP_H + MARGIN * 2,
            bg=COLOR_BG,
            highlightthickness=0,
        )
        self.canvas.pack()
        self.status = tk.Label(root, text="待受中…", font=("sans-serif", 12), fg=COLOR_TEXT)
        self.status.pack(pady=4)

        # 全機緊急停止ボタン（#28 / 検収 F14・A2・P2）。押下→確認→全 Pi へ emergency 並列送信。
        self.emergency_button = tk.Button(
            root,
            text="全機緊急停止",
            bg="#D32F2F",
            fg="white",
            font=("sans-serif", 14, "bold"),
            command=self._on_emergency,
        )
        self.emergency_button.pack(pady=6, fill=tk.X, padx=20)

        self._draw_map()
        self._refresh()

    def _on_emergency(self) -> None:
        """全機緊急停止ボタン押下時: 確認ダイアログ後に全 Pi へ並列送信する。"""
        if not messagebox.askyesno("全機緊急停止", "全ドローンを緊急停止します。よろしいですか？"):
            return

        def _run() -> None:
            results = emergency_all()
            ok = sum(1 for v in results.values() if v)
            self.status.configure(text=f"全機緊急停止: {ok}/{len(results)} 機へ送信")

        # UI を固めないよう別スレッドで送信（送信自体も内部で並列）。
        threading.Thread(target=_run, daemon=True).start()

    def _draw_map(self) -> None:
        """ケージ枠と 1m グリッドを描く（一度だけ）。"""
        x0, y0 = cage_to_screen(CAGE_X[0], CAGE_Y[1])  # 左上
        x1, y1 = cage_to_screen(CAGE_X[1], CAGE_Y[0])  # 右下
        # 1m グリッド
        gx = CAGE_X[0] + 1
        while gx < CAGE_X[1]:
            sx, _ = cage_to_screen(gx, 0)
            self.canvas.create_line(sx, y0, sx, y1, fill=COLOR_GRID)
            gx += 1
        gy = CAGE_Y[0] + 1
        while gy < CAGE_Y[1]:
            _, sy = cage_to_screen(0, gy)
            self.canvas.create_line(x0, sy, x1, sy, fill=COLOR_GRID)
            gy += 1
        # ケージ外枠
        self.canvas.create_rectangle(x0, y0, x1, y1, outline=COLOR_CAGE, width=2)

    def _refresh(self) -> None:
        """最新ビーコンでアイコンを再描画する（REFRESH_MS ごと）。"""
        self.canvas.delete("drone")  # 前回のアイコンだけ消す（マップ枠は残す）
        beacons = self.store.snapshot()
        for beacon in sorted(beacons.values(), key=lambda b: b.id):
            self._draw_drone(beacon)
        n = len(beacons)
        self.status.config(text=f"受信中: {n} 台" if n else "ビーコン待受中…")
        self.root.after(REFRESH_MS, self._refresh)

    def _draw_drone(self, beacon) -> None:
        sx, sy = cage_to_screen(beacon.x, beacon.y)
        # 機体アイコン（円）
        self.canvas.create_oval(
            sx - ICON_R,
            sy - ICON_R,
            sx + ICON_R,
            sy + ICON_R,
            fill=COLOR_DRONE,
            outline=COLOR_TEXT,
            width=2,
            tags="drone",
        )
        # 機首方向（yaw=0 は +Y=画面上、時計回り）
        rad = math.radians(beacon.yaw)
        hx = sx + ICON_R * math.sin(rad)
        hy = sy - ICON_R * math.cos(rad)
        self.canvas.create_line(sx, sy, hx, hy, fill=COLOR_TEXT, width=2, tags="drone")
        # ラベル（識別子＋バッテリ）
        self.canvas.create_text(
            sx,
            sy - ICON_R - 10,
            text=f"{beacon.id}  {beacon.battery}%",
            font=("sans-serif", 10),
            fill=COLOR_TEXT,
            tags="drone",
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="ドローンモニタ")
    parser.add_argument("--host", default="0.0.0.0", help="待受ホスト（既定: 0.0.0.0）")
    parser.add_argument(
        "--port", type=int, default=BEACON_PORT, help=f"待受ポート（既定: {BEACON_PORT}）"
    )
    args = parser.parse_args()

    store = BeaconStore()
    receiver = BeaconReceiver(store, host=args.host, port=args.port)
    receiver.start()

    root = tk.Tk()
    MonitorApp(root, store)
    try:
        root.mainloop()
    finally:
        receiver.stop()


if __name__ == "__main__":
    main()
