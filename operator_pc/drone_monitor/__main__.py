"""ドローンモニタ本体（Tkinter）。

    uv run python -m operator_pc.drone_monitor              # 0.0.0.0:11231 で待受
    uv run python -m operator_pc.drone_monitor --host 127.0.0.1

別ターミナルで `uv run python -m shared.tools.fake_beacon` を流すと
4 台分のアイコンがマップ上を動く。
"""

from __future__ import annotations

import argparse
import math
import time
import tkinter as tk

from shared.ports import BEACON_PORT
from shared.schemas import CAGE_X, CAGE_Y

from .receiver import BeaconReceiver, BeaconStore
from .status import FRESH, GONE, LOST, STALE, is_outside_cage, staleness_level

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
COLOR_STALE = "#BDBDBD"  # 3秒途絶（半透明風グレー）
COLOR_LOST = "#E53935"  # 10秒途絶（赤点滅）/ ケージ逸脱の赤枠


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

        self._blink = False  # 赤点滅（LOST 段階）用トグル

        self._draw_map()
        self._refresh()

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
        self._blink = not self._blink  # 赤点滅（LOST）用トグル
        items = self.store.snapshot_with_age(time.monotonic())
        shown = 0
        for _bid, (beacon, age) in sorted(items.items()):
            level = staleness_level(age)
            if level == GONE:
                continue  # 30秒経過 → 非表示
            self._draw_drone(beacon, level)
            shown += 1
        self.status.config(text=f"受信中: {shown} 台" if shown else "ビーコン待受中…")
        self.root.after(REFRESH_MS, self._refresh)

    def _draw_drone(self, beacon, level: str = FRESH) -> None:
        sx, sy = cage_to_screen(beacon.x, beacon.y)

        # 途絶段階で塗り色を変える（3秒→グレー半透明風 / 10秒→赤点滅）
        fill = COLOR_DRONE
        if level == STALE:
            fill = COLOR_STALE
        elif level == LOST:
            fill = COLOR_LOST if self._blink else COLOR_BG  # 点滅

        # ケージ逸脱なら赤枠で強調（設計 5.4.4(4)）
        outside = is_outside_cage(beacon.x, beacon.y, beacon.z)
        outline = COLOR_LOST if outside else COLOR_TEXT
        width = 4 if outside else 2

        # 機体アイコン（円）
        self.canvas.create_oval(
            sx - ICON_R,
            sy - ICON_R,
            sx + ICON_R,
            sy + ICON_R,
            fill=fill,
            outline=outline,
            width=width,
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
