"""UDP 11231 のビーコンを受信して 1 行ずつ表示する確認用ツール。

#5 drone_monitor 本体が無い段階での疎通確認に使う。
#5 開発中の確認や、#2 の実機ビーコン到達確認（ノートPC 上で起動）にも流用する。

使い方:
    uv run python -m shared.tools.dump_beacon                  # 0.0.0.0:11231 で待受
    uv run python -m shared.tools.dump_beacon --port 11231
"""

from __future__ import annotations

import argparse
import socket

from shared.ports import BEACON_PORT
from shared.schemas import Beacon


def main() -> None:
    parser = argparse.ArgumentParser(description="ビーコン受信ダンプ")
    parser.add_argument("--host", default="0.0.0.0", help="待受ホスト（既定: 0.0.0.0）")
    parser.add_argument(
        "--port", type=int, default=BEACON_PORT, help=f"待受ポート（既定: {BEACON_PORT}）"
    )
    args = parser.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((args.host, args.port))
    print(f"listening on {args.host}:{args.port} for beacons. Ctrl-C to stop.")

    try:
        while True:
            data, addr = sock.recvfrom(4096)
            try:
                b = Beacon.from_json(data.decode("utf-8"))
            except (ValueError, TypeError) as e:
                print(f"[skip] unparseable from {addr[0]}: {e}")
                continue
            print(
                f"{b.id}  x={b.x:>4.1f} y={b.y:>4.1f} z={b.z:>4.1f} "
                f"yaw={b.yaw:>3d} batt={b.battery:>3d}% t={b.flight_time}s  ({b.ts})"
            )
    except KeyboardInterrupt:
        print("\nstopped.")
    finally:
        sock.close()


if __name__ == "__main__":
    main()
