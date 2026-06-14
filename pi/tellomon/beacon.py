"""ビーコン送信部（tellomon 本体から分離。cv2/tkinter に依存しない）。

Tello status から得た最新値を 1Hz に間引いて、JSON ビーコンを
ノートPC(UDP 11231) へ送る。本体（__main__.py）が無くても単体で検証できる。
"""

from __future__ import annotations

import socket
import threading
import time
from collections.abc import Callable

from shared.ports import BEACON_PORT, NOTE_PC_IP
from shared.schemas import CAGE_X, CAGE_Y, CAGE_Z, Beacon, drone_id, now_iso

# ケージ中央（x/y の仮値に使う）
_CAGE_CENTER_X = (CAGE_X[0] + CAGE_X[1]) / 2
_CAGE_CENTER_Y = (CAGE_Y[0] + CAGE_Y[1]) / 2


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def build_beacon(drone_num: int, status: dict) -> Beacon:
    """Tello status の最新値からビーコンを組み立てる（純粋関数）。

    status は {"battery","height_cm","flight_time","yaw"} を想定。
    起動直後など値が無いキーは 0 とみなす。

    x/y（ケージ内 m 座標）は Tello から取得できないため、当面は
    ケージ中央の固定値を入れる。
    TODO: 屋内測位（外部カメラ/UWB 等）が決まったら実値に差し替える（別 issue）。
    """
    height_cm = status.get("height_cm", 0)
    return Beacon(
        id=drone_id(drone_num),
        ts=now_iso(),
        x=round(_CAGE_CENTER_X, 2),
        y=round(_CAGE_CENTER_Y, 2),
        z=round(_clamp(height_cm / 100, CAGE_Z[0], CAGE_Z[1]), 2),
        yaw=int(status.get("yaw", 0)) % 360,
        battery=int(status.get("battery", 0)),
        flight_time=int(status.get("flight_time", 0)),
    )


class BeaconSender:
    """status_provider() から最新 status を取り、1Hz でビーコンを UDP 送信する。

    status_provider: 引数なしで最新 status dict を返す callable
    （tellomon 本体では `lambda: status_recever.latest` を渡す）。
    """

    def __init__(
        self,
        drone_num: int,
        status_provider: Callable[[], dict],
        host: str = NOTE_PC_IP,
        port: int = BEACON_PORT,
        rate: float = 1.0,
    ) -> None:
        self.drone_num = drone_num
        self.status_provider = status_provider
        self.host = host
        self.port = port
        self.interval = 1.0 / rate
        self._sock: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._running = False

    def start(self) -> None:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        assert self._sock is not None
        dest = (self.host, self.port)
        while self._running:
            beacon = build_beacon(self.drone_num, self.status_provider())
            try:
                self._sock.sendto(beacon.to_json().encode("utf-8"), dest)
            except OSError:
                pass  # 送信先が未起動でも送信側は落とさない
            time.sleep(self.interval)

    def stop(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=1.0)
        if self._sock is not None:
            self._sock.close()
            self._sock = None
