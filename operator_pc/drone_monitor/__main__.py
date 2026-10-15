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
import time
import tkinter as tk
from tkinter import messagebox

from shared.ports import BEACON_PORT
from shared.schemas import CAGE_X, CAGE_Y, HOME_POSITIONS

from ..emergency import emergency_all
from .receiver import BeaconReceiver, BeaconStore
from .status import FRESH, GONE, LOST, STALE, is_cage_warning, is_low_battery, staleness_level

# --- 表示パラメータ（仕様詳細ドラフト.md §3.4）-------------------------
SCALE = 100  # px / m（初期値。ペインの大きさに合わせて自動で拡縮する）
MARGIN = 20  # マップ外周の余白(px)
MAP_W = int((CAGE_X[1] - CAGE_X[0]) * SCALE)  # 650（初期キャンバスサイズ用）
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


class MonitorApp:
    """飛行マップ＋全機緊急停止ボタン。

    parent には Tk ルートのほか Frame も渡せる（#34 の統合モニタが右ペインとして埋め込む）。
    """

    def __init__(self, parent: tk.Misc, store: BeaconStore) -> None:
        self.parent = parent
        self.store = store

        self.canvas = tk.Canvas(
            parent,
            width=MAP_W + MARGIN * 2,
            height=MAP_H + MARGIN * 2,
            bg=COLOR_BG,
            highlightthickness=0,
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)
        # 縮尺と原点はキャンバスの実サイズから決める（マップをペインいっぱいに広げる）
        self._scale = float(SCALE)
        self._offset = (float(MARGIN), float(MARGIN))
        self.canvas.bind("<Configure>", self._on_canvas_resize)
        self.status = tk.Label(parent, text="待受中…", font=("sans-serif", 12), fg=COLOR_TEXT)
        self.status.pack(pady=4)

        # 全機緊急停止ボタン（#28 / 検収 F14・A2・P2）。押下→確認→全 Pi へ emergency 並列送信。
        self.emergency_button = tk.Button(
            parent,
            text="全機緊急停止",
            bg="#D32F2F",
            fg="white",
            font=("sans-serif", 14, "bold"),
            command=self._on_emergency,
        )
        self.emergency_button.pack(pady=(6, 12), fill=tk.X, padx=20)
        self._blink = False  # 赤点滅（LOST 段階）用トグル

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

    def _on_canvas_resize(self, event: tk.Event) -> None:
        """キャンバスの実サイズから縮尺を再計算する（アスペクト比維持・中央寄せ）。"""
        span_x = CAGE_X[1] - CAGE_X[0]
        span_y = CAGE_Y[1] - CAGE_Y[0]
        scale = min((event.width - MARGIN * 2) / span_x, (event.height - MARGIN * 2) / span_y)
        self._scale = max(scale, 30.0)  # 極端に潰れないよう下限を設ける
        self._offset = (
            (event.width - span_x * self._scale) / 2,
            (event.height - span_y * self._scale) / 2,
        )
        self._draw_map()

    def _cage_to_screen(self, x: float, y: float) -> tuple[float, float]:
        """ケージ座標(m, 左下原点) → 画面座標(px, 左上原点)。y を上下反転する。"""
        ox, oy = self._offset
        sx = ox + (x - CAGE_X[0]) * self._scale
        sy = oy + (CAGE_Y[1] - y) * self._scale  # y=0(下) が画面下に来るよう反転
        return sx, sy

    def _draw_map(self) -> None:
        """ケージ枠と 1m グリッドを描く（リサイズのたびに引き直す）。"""
        self.canvas.delete("static")
        x0, y0 = self._cage_to_screen(CAGE_X[0], CAGE_Y[1])  # 左上
        x1, y1 = self._cage_to_screen(CAGE_X[1], CAGE_Y[0])  # 右下
        # 1m グリッド
        gx = CAGE_X[0] + 1
        while gx < CAGE_X[1]:
            sx, _ = self._cage_to_screen(gx, 0)
            self.canvas.create_line(sx, y0, sx, y1, fill=COLOR_GRID, tags="static")
            gx += 1
        gy = CAGE_Y[0] + 1
        while gy < CAGE_Y[1]:
            _, sy = self._cage_to_screen(0, gy)
            self.canvas.create_line(x0, sy, x1, sy, fill=COLOR_GRID, tags="static")
            gy += 1
        # ケージ外枠
        self.canvas.create_rectangle(x0, y0, x1, y1, outline=COLOR_CAGE, width=2, tags="static")
        # 離着陸ホームポジションの目印（＋印と機体番号）。定位置に戻ったかの確認と、
        # 機体番号と置き位置の不一致（置き間違い）の検出に使う。
        for num, (hx, hy) in HOME_POSITIONS.items():
            sx, sy = self._cage_to_screen(hx, hy)
            r = 7
            self.canvas.create_line(sx - r, sy, sx + r, sy, fill=COLOR_CAGE, width=2, tags="static")
            self.canvas.create_line(sx, sy - r, sx, sy + r, fill=COLOR_CAGE, width=2, tags="static")
            self.canvas.create_text(
                sx + r + 8,
                sy + r + 4,
                text=str(num),
                font=("sans-serif", 10),
                fill=COLOR_CAGE,
                tags="static",
            )
        self.canvas.tag_lower("static")  # 次の再描画までアイコンを隠さない

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
        self.parent.after(REFRESH_MS, self._refresh)

    def _draw_drone(self, beacon, level: str = FRESH) -> None:
        sx, sy = self._cage_to_screen(beacon.x, beacon.y)

        # 途絶段階で塗り色を変える（3秒→グレー半透明風 / 10秒→赤点滅）
        fill = COLOR_DRONE
        if level == STALE:
            fill = COLOR_STALE
        elif level == LOST:
            fill = COLOR_LOST if self._blink else COLOR_BG  # 点滅

        # ケージ境界に近づいたら赤枠で事前警告（設計 5.4.4(4) の逸脱検知を警告に変更。
        # ケージ外コマンドは制御側が抑止するため、表示側は警告ゾーンで先に知らせる）
        warning = is_cage_warning(beacon.x, beacon.y, beacon.z)
        outline = COLOR_LOST if warning else COLOR_TEXT
        width = 4 if warning else 2

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
        # ラベル（識別子＋バッテリ）。バッテリ 20% 以下は赤太字で警告（検収 A4 と同閾値）
        low_batt = is_low_battery(beacon.battery)
        self.canvas.create_text(
            sx,
            sy - ICON_R - 10,
            text=f"{beacon.id}  {beacon.battery}%",
            font=("sans-serif", 10, "bold") if low_batt else ("sans-serif", 10),
            fill=COLOR_LOST if low_batt else COLOR_TEXT,
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
    root.title("ドローンモニタ")
    MonitorApp(root, store)
    try:
        root.mainloop()
    finally:
        receiver.stop()


if __name__ == "__main__":
    main()
