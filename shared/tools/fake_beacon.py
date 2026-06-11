"""4台分のダミービーコンを 1Hz で UDP 11231 へ送る確認用スクリプト。

受信側本体（#5 drone_monitor）が無い段階でも、dump_beacon.py とペアで
「ビーコンが実際に飛んでいる」ことを確認できる。

使い方:
    uv run python -m shared.tools.fake_beacon                 # 127.0.0.1:11231 へ
    uv run python -m shared.tools.fake_beacon --host 192.168.0.100   # 実機検証時
"""

from __future__ import annotations

import argparse
import math
import socket
import time

from shared.ports import BEACON_PORT, NUM_DRONES
from shared.schemas import CAGE_X, CAGE_Y, CAGE_Z, Beacon, drone_id, now_iso


def make_beacon(n: int, t: float) -> Beacon:
    """機体 n の、経過時間 t 秒での見せかけ状態を作る。

    乱数は使わず t から滑らかに動かす（機体ごとに位相をずらす）。
    ケージ内（CAGE_X/Y/Z）を周回するように x/y/z/yaw を生成する。
    """
    x_lo, x_hi = CAGE_X
    y_lo, y_hi = CAGE_Y
    z_lo, z_hi = CAGE_Z
    phase = n * (2 * math.pi / NUM_DRONES)  # 機体ごとに開始位置をずらす
    w = 0.3  # 角速度（rad/s）。ゆっくり周回

    cx, cy = (x_lo + x_hi) / 2, (y_lo + y_hi) / 2
    rx, ry = (x_hi - x_lo) / 2 * 0.7, (y_hi - y_lo) / 2 * 0.7
    x = cx + rx * math.cos(w * t + phase)
    y = cy + ry * math.sin(w * t + phase)
    z = (z_lo + z_hi) / 2 + (z_hi - z_lo) / 4 * math.sin(0.2 * t + phase)
    yaw = int((math.degrees(w * t + phase)) % 360)

    battery = max(0, 100 - int(t) // 5)  # 5 秒で 1% 減る程度
    flight_time = int(t)
    return Beacon(
        id=drone_id(n),
        ts=now_iso(),
        x=round(x, 2),
        y=round(y, 2),
        z=round(z, 2),
        yaw=yaw,
        battery=battery,
        flight_time=flight_time,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="ダミービーコン送信（4台・1Hz）")
    parser.add_argument("--host", default="127.0.0.1", help="送信先ホスト（既定: 127.0.0.1）")
    parser.add_argument(
        "--port", type=int, default=BEACON_PORT, help=f"送信先ポート（既定: {BEACON_PORT}）"
    )
    parser.add_argument("--rate", type=float, default=1.0, help="送信レート Hz（既定: 1.0）")
    args = parser.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    interval = 1.0 / args.rate
    dest = (args.host, args.port)
    print(
        f"send dummy beacons -> {args.host}:{args.port} @ {args.rate}Hz ({NUM_DRONES} drones). Ctrl-C to stop."
    )

    t = 0.0
    try:
        while True:
            for n in range(1, NUM_DRONES + 1):
                beacon = make_beacon(n, t)
                sock.sendto(beacon.to_json().encode("utf-8"), dest)
            t += interval
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nstopped.")
    finally:
        sock.close()


if __name__ == "__main__":
    main()
