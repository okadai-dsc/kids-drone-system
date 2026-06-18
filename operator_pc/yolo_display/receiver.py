"""UDP receiver for YOLO result display."""

from __future__ import annotations

import queue
import socket
import threading

from shared.ports import YOLO_TO_DISPLAY_PORTS
from shared.schemas import YoloResult


class YoloResultReceiver:
    """Receive YOLO result JSON from multiple UDP ports into a thread-safe queue."""

    def __init__(
        self,
        outbox: queue.Queue[YoloResult],
        host: str = "0.0.0.0",
        ports: list[int] | None = None,
    ) -> None:
        self.outbox = outbox
        self.host = host
        self.ports = ports or [YOLO_TO_DISPLAY_PORTS[n] for n in range(1, 5)]
        self._sockets: list[socket.socket] = []
        self._threads: list[threading.Thread] = []
        self._running = False

    def start(self) -> None:
        self._running = True
        for port in self.ports:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind((self.host, port))
            sock.settimeout(0.5)
            self._sockets.append(sock)
            thread = threading.Thread(target=self._loop, args=(sock,), daemon=True)
            self._threads.append(thread)
            thread.start()

    def _loop(self, sock: socket.socket) -> None:
        while self._running:
            try:
                data, _addr = sock.recvfrom(65536)
            except TimeoutError:
                continue
            except OSError:
                break
            try:
                result = YoloResult.from_json(data.decode("utf-8"))
            except (UnicodeDecodeError, ValueError, TypeError, KeyError):
                continue
            self.outbox.put(result)

    def stop(self) -> None:
        self._running = False
        for sock in self._sockets:
            sock.close()
        for thread in self._threads:
            thread.join(timeout=1.0)
        self._sockets.clear()
        self._threads.clear()
