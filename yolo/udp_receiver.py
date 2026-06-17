import argparse
import json
import os
import socket
import sys

# 親ディレクトリの shared をインポートできるようにパスを追加
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from shared.ports import YOLO_TO_DISPLAY_PORTS


def run_receiver():
    parser = argparse.ArgumentParser(description="YOLO結果表示側ダミー受信機")
    parser.add_argument("--host", default="0.0.0.0", help="待受ホスト（既定: 0.0.0.0）")
    parser.add_argument(
        "--drone",
        type=int,
        choices=[1, 2, 3, 4],
        default=1,
        help="対象のドローン番号 (1〜4)。指定すると自動的に対応するポートが選択されます",
    )
    parser.add_argument("--port", type=int, help="待受ポート（指定時は --drone より優先されます）")
    args = parser.parse_args()

    host = args.host
    port = args.port if args.port is not None else YOLO_TO_DISPLAY_PORTS[args.drone]

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((host, port))
    print(
        f"Listening on udp://{host}:{port} (Tello#{args.drone if args.port is None else 'custom'}). Ctrl-C to stop."
    )

    try:
        while True:
            data, addr = sock.recvfrom(65536)
            print(f"\nReceived {len(data)} bytes from {addr}")

            try:
                # JSONとしてパースを試みる
                text = data.decode("utf-8")
                parsed = json.loads(text)
                print(f"Parsed JSON dict: {parsed}")
            except (UnicodeDecodeError, json.JSONDecodeError):
                # JSONでなければそのまま bytes として表示
                print(f"Raw bytes: {data}")
    except KeyboardInterrupt:
        print("\nReceiver stopped.")
    finally:
        sock.close()


if __name__ == "__main__":
    run_receiver()
