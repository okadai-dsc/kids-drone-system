"""YOLO result display app.

Run from the repository root:
    uv run python yolo_display.py
    uv run python -m operator_pc.yolo_display
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import os
import queue
import time
import tkinter as tk
from dataclasses import dataclass
from tkinter import font as tkfont

from PIL import Image, ImageTk

from shared.ports import YOLO_TO_DISPLAY_PORTS
from shared.schemas import DETECT_LABELS, Detection, YoloResult, drone_id, now_iso

from .receiver import YoloResultReceiver

NUM_DRONES = 4
EXPIRE_SEC = 3.0
POLL_MS = 50

COLOR_BG = "#FAFAFA"
COLOR_DETECTED = "#4CAF50"
COLOR_NORMAL = "#9E9E9E"
COLOR_WARNING = "#FF9800"
COLOR_ERROR = "#F44336"
COLOR_TEXT = "#212121"
COLOR_INACTIVE_TEXT = "#616161"
COLOR_PANEL = "#FFFFFF"
COLOR_BORDER = "#E0E0E0"

FALLBACK_FONTS = ("Noto Sans CJK JP", "メイリオ", "Hiragino Sans", "Yu Gothic UI", "sans-serif")
LABEL_TEXT = {"cat": "ねこ", "dog": "いぬ"}


@dataclass
class CellState:
    label: str
    last_detected: float = 0.0


class YoloDisplayApp:
    """検知タイル（2×2）表示。

    parent には Tk ルートのほか Frame も渡せる（#34 の統合モニタが左ペインとして埋め込む）。
    """

    def __init__(
        self,
        parent: tk.Misc,
        inbox: queue.Queue[YoloResult],
        receiver: YoloResultReceiver | None = None,
    ) -> None:
        self.parent = parent
        self.inbox = inbox
        self.receiver = receiver
        self.cells: dict[tuple[str, str], CellState] = {}
        self.labels: dict[tuple[str, str], tk.Label] = {}
        self.image_panels: dict[str, tk.Frame] = {}
        self.image_labels: dict[str, tk.Label] = {}
        self.image_titles: dict[str, tk.Label] = {}
        self.image_badges: dict[str, tk.Label] = {}
        self.image_photos: dict[str, ImageTk.PhotoImage] = {}
        self._closed = False

        parent.configure(bg=COLOR_BG)

        self.font_cell = (self._pick_font(), 14, "bold")
        self.font_header = (self._pick_font(), 18, "bold")
        self.font_status = (self._pick_font(), 14)
        self.font_image_title = (self._pick_font(), 16, "bold")
        self.font_badge = (self._pick_font(), 13, "bold")
        self.font_button = (self._pick_font(), 14)

        self._build_layout()
        self._poll_inbox()
        self._expire_cells()

    def _pick_font(self) -> str:
        available = set(tkfont.families())
        for family in FALLBACK_FONTS:
            if not available or family in available:
                return family
        return "sans-serif"

    def _build_layout(self) -> None:
        top = tk.Frame(self.parent, bg=COLOR_BG)
        top.pack(fill=tk.X, padx=20, pady=(16, 8))

        title = tk.Label(
            top,
            text="YOLO 結果表示",
            font=self.font_header,
            bg=COLOR_BG,
            fg=COLOR_TEXT,
        )
        title.pack(side=tk.LEFT)

        image_grid = tk.Frame(self.parent, bg=COLOR_BG)
        image_grid.pack(fill=tk.BOTH, expand=True, padx=20, pady=(6, 10))
        for row in range(2):
            image_grid.rowconfigure(row, weight=1, uniform="image-row")
        for col in range(2):
            image_grid.columnconfigure(col, weight=1, uniform="image-col")

        for drone_num in range(1, NUM_DRONES + 1):
            tello_id = drone_id(drone_num)
            panel = tk.Frame(
                image_grid,
                bg=COLOR_PANEL,
                highlightthickness=4,
                highlightbackground=COLOR_BORDER,
            )
            panel.grid(
                row=(drone_num - 1) // 2,
                column=(drone_num - 1) % 2,
                sticky="nsew",
                padx=6,
                pady=6,
            )
            header = tk.Frame(panel, bg=COLOR_PANEL)
            header.pack(fill=tk.X, padx=10, pady=(8, 4))
            title = tk.Label(
                header, text=tello_id, font=self.font_image_title, bg=COLOR_PANEL, fg=COLOR_TEXT
            )
            title.pack(side=tk.LEFT)
            badge = tk.Label(
                header,
                text="未検知",
                font=self.font_badge,
                bg=COLOR_NORMAL,
                fg=COLOR_INACTIVE_TEXT,
                padx=10,
                pady=2,
            )
            badge.pack(side=tk.RIGHT)
            image_label = tk.Label(
                panel,
                text="bbox画像なし",
                font=self.font_status,
                bg=COLOR_PANEL,
                fg=COLOR_INACTIVE_TEXT,
            )
            image_label.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
            self.image_panels[tello_id] = panel
            self.image_titles[tello_id] = title
            self.image_badges[tello_id] = badge
            self.image_labels[tello_id] = image_label

            for label in DETECT_LABELS:
                self.cells[(tello_id, label)] = CellState(label=label)

        self.status = tk.Label(
            self.parent,
            text="UDP 11212〜11215 待受中",
            font=self.font_status,
            bg=COLOR_BG,
            fg=COLOR_TEXT,
        )
        self.status.pack(fill=tk.X, padx=20, pady=(0, 12))

    def apply_result(self, result: YoloResult) -> None:
        now = time.monotonic()
        detected_labels = {d.label for d in result.detections if d.label in LABEL_TEXT}
        for label in detected_labels:
            key = (result.tello_id, label)
            if key not in self.cells:
                continue
            self.cells[key].last_detected = now
        if result.tello_id in self.image_panels:
            self._set_drone_detected(result.tello_id, detected_labels)

        # 検知の有無に関わらず、フレーム画像が来ていれば常時表示する（ライブ映像として）
        if result.image_b64:
            self._show_image(result.tello_id, result.image_b64)

        labels = " / ".join(LABEL_TEXT[label] for label in sorted(detected_labels)) or "未検知"
        self.status.configure(text=f"{result.tello_id}: {labels}  {result.ts}")

    def load_json(self, path: str) -> None:
        if not os.path.exists(path):
            self.status.configure(text=f"{path} がありません", fg=COLOR_ERROR)
            return
        try:
            with open(path, encoding="utf-8") as f:
                data = f.read()
            self.apply_result(YoloResult.from_json(data))
            self.status.configure(fg=COLOR_TEXT)
        except (OSError, json.JSONDecodeError, TypeError, KeyError, ValueError) as exc:
            self.status.configure(text=f"JSON読込エラー: {exc}", fg=COLOR_ERROR)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self.receiver is not None:
            self.receiver.stop()
        try:
            self.parent.winfo_toplevel().destroy()
        except tk.TclError:
            pass

    def _poll_inbox(self) -> None:
        while True:
            try:
                result = self.inbox.get_nowait()
            except queue.Empty:
                break
            self.apply_result(result)
        self.parent.after(POLL_MS, self._poll_inbox)

    def _expire_cells(self) -> None:
        now = time.monotonic()
        for key, state in self.cells.items():
            if state.last_detected and now - state.last_detected >= EXPIRE_SEC:
                state.last_detected = 0.0
                tello_id, _label = key
                self._refresh_drone_indicator(tello_id)
        self.parent.after(100, self._expire_cells)

    def _set_drone_detected(self, tello_id: str, detected_labels: set[str]) -> None:
        text = " / ".join(LABEL_TEXT[label] for label in sorted(detected_labels))
        self.image_panels[tello_id].configure(highlightbackground=COLOR_DETECTED)
        self.image_badges[tello_id].configure(text=text, bg=COLOR_DETECTED, fg=COLOR_TEXT)

    def _refresh_drone_indicator(self, tello_id: str) -> None:
        active_labels = {
            label
            for label in DETECT_LABELS
            if self.cells.get((tello_id, label)) and self.cells[(tello_id, label)].last_detected
        }
        if active_labels:
            self._set_drone_detected(tello_id, active_labels)
            return
        self.image_panels[tello_id].configure(highlightbackground=COLOR_BORDER)
        self.image_badges[tello_id].configure(
            text="未検知", bg=COLOR_NORMAL, fg=COLOR_INACTIVE_TEXT
        )

    def _show_image(self, tello_id: str, image_b64: str) -> None:
        if tello_id not in self.image_labels:
            return
        try:
            raw = base64.b64decode(image_b64)
            image = Image.open(io.BytesIO(raw))
            image.thumbnail((480, 240))
            self.image_photos[tello_id] = ImageTk.PhotoImage(image)
        except (ValueError, OSError) as exc:
            self.status.configure(text=f"画像デコードエラー: {exc}", fg=COLOR_WARNING)
            return
        self.image_labels[tello_id].configure(
            image=self.image_photos[tello_id],
            text="",
            bg=COLOR_PANEL,
        )
        self.status.configure(fg=COLOR_TEXT)

    def _dummy_result(self, drone_num: int, label: str) -> YoloResult:
        return YoloResult(
            tello_id=drone_id(drone_num),
            ts=now_iso(),
            detections=[Detection(label=label, confidence=0.99, bbox=[10, 10, 100, 100])],
            image_b64="",
        )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="YOLO 結果表示")
    parser.add_argument("--host", default="0.0.0.0", help="UDP 待受ホスト")
    parser.add_argument(
        "--ports",
        default=",".join(str(YOLO_TO_DISPLAY_PORTS[n]) for n in range(1, 5)),
        help="UDP 待受ポートのカンマ区切り",
    )
    parser.add_argument("--no-udp", action="store_true", help="UDP受信を起動しない")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    ports = [int(p.strip()) for p in args.ports.split(",") if p.strip()]
    inbox: queue.Queue[YoloResult] = queue.Queue()
    receiver = None if args.no_udp else YoloResultReceiver(inbox, host=args.host, ports=ports)
    if receiver is not None:
        receiver.start()

    root = tk.Tk()
    root.title("YOLO 結果表示")
    root.geometry("1120x760")
    root.minsize(980, 680)
    app = YoloDisplayApp(root, inbox, receiver=receiver)
    root.protocol("WM_DELETE_WINDOW", app.close)
    try:
        root.mainloop()
    finally:
        app.close()


if __name__ == "__main__":
    main()
