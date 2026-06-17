import argparse
import os
import socket
import sys
import time
from datetime import datetime

# 親ディレクトリの shared をインポートできるようにパスを追加
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from shared.ports import YOLO_TO_DISPLAY_PORTS
from shared.schemas import Detection, YoloResult, drone_id


def run_sender():
    parser = argparse.ArgumentParser(description="YOLO結果ダミー送信機")
    parser.add_argument("--host", default="127.0.0.1", help="送信先ホスト（既定: 127.0.0.1）")
    parser.add_argument(
        "--drone",
        type=int,
        choices=[1, 2, 3, 4],
        default=1,
        help="対象のドローン番号 (1〜4)。指定すると自動的に対応するポートとIDが選択されます",
    )
    parser.add_argument(
        "--port", type=int, help="送信先ポート（指定時は --drone より優先されます）"
    )
    args = parser.parse_args()

    host = args.host
    port = args.port if args.port is not None else YOLO_TO_DISPLAY_PORTS[args.drone]
    tello_name = drone_id(args.drone)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    dest = (host, port)

    print(f"Target: {host}:{port} for {tello_name}")

    # 1. テキスト "hello" を1回送る
    print("Sending 'hello'...")
    sock.sendto(b"hello", dest)

    time.sleep(1)

    # 2. shared/schemas.py の検知結果 JSON 形式の文字列を送る
    result = YoloResult(
        tello_id=tello_name,
        ts=datetime.now().isoformat(timespec="milliseconds"),
        detections=[Detection(label="cat", confidence=0.95, bbox=[100, 100, 200, 200])],
        image_b64="<dummy_base64_string>",
    )

    json_data = result.to_json()
    print(f"Sending JSON data: {json_data}")
    sock.sendto(json_data.encode("utf-8"), dest)

    sock.close()
    print("Done.")


if __name__ == "__main__":
    run_sender()
