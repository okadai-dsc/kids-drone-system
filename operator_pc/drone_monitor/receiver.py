"""ビーコン受信部（UI から分離。socket スレッドでビーコンを購読する）。

UI（Tkinter）が無くても単体で動作確認できるよう、受信ロジックをここに分けている。
"""

from __future__ import annotations

import socket
import threading
import time

from shared.ports import BEACON_PORT
from shared.schemas import Beacon


class BeaconStore:
    """ドローンごとの最新ビーコンと受信時刻を保持するスレッドセーフな箱。

    受信スレッドが update()、UI スレッドが snapshot()/snapshot_with_age() を呼ぶ。
    受信時刻は途絶段階の判定（#34 / 設計 5.4.4）に使う。
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._latest: dict[str, Beacon] = {}
        self._recv_time: dict[str, float] = {}  # id -> 受信時刻(monotonic 秒)

    def update(self, beacon: Beacon, recv_time: float | None = None) -> None:
        if recv_time is None:
            recv_time = time.monotonic()
        with self._lock:
            self._latest[beacon.id] = beacon
            self._recv_time[beacon.id] = recv_time

    def snapshot(self) -> dict[str, Beacon]:
        """現在の最新ビーコンのコピーを返す（UI 描画用）。"""
        with self._lock:
            return dict(self._latest)

    def snapshot_with_age(self, now: float) -> dict[str, tuple[Beacon, float]]:
        """id -> (Beacon, 経過秒数) を返す。経過秒数で途絶段階を判定する。"""
        with self._lock:
            return {
                bid: (beacon, now - self._recv_time.get(bid, now))
                for bid, beacon in self._latest.items()
            }


class BeaconReceiver:
    """UDP ビーコンを受信して BeaconStore を更新するデーモンスレッド。"""

    def __init__(
        self,
        store: BeaconStore,
        host: str = "0.0.0.0",
        port: int = BEACON_PORT,
    ) -> None:
        self.store = store
        self.host = host
        self.port = port
        self._sock: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._running = False

    def start(self) -> None:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.bind((self.host, self.port))
        self._sock.settimeout(0.5)  # stop() を取りこぼさないため定期的に抜ける
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        assert self._sock is not None
        while self._running:
            try:
                data, _addr = self._sock.recvfrom(4096)
            except TimeoutError:
                continue
            except OSError:
                break
            try:
                self.store.update(Beacon.from_json(data.decode("utf-8")))
            except (ValueError, TypeError):
                continue  # 壊れたパケットは無視

    def stop(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=1.0)
        if self._sock is not None:
            self._sock.close()
            self._sock = None
