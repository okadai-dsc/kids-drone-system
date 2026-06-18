import argparse
import base64
import os
import socket
import sys
import time

# 親ディレクトリの shared をインポートできるようにパスを追加
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from shared.ports import YOLO_TO_DISPLAY_PORTS
from shared.schemas import Detection, YoloResult, drone_id, now_iso


def _dummy_image_b64(image_bytes: int) -> str:
    """JPEG 相当サイズのダミーバイト列を base64 化する。"""
    if image_bytes <= 0:
        return "<dummy_base64_string>"
    return base64.b64encode(bytes(image_bytes)).decode("ascii")


def _fit_json_bytes(result: YoloResult, target_bytes: int) -> str:
    """UDP datagram 全体が target_bytes になるよう image_b64 を詰める。"""
    if target_bytes <= 0:
        return result.to_json()

    result.image_b64 = ""
    json_data = result.to_json()
    min_len = len(json_data.encode("utf-8"))
    if target_bytes < min_len:
        raise ValueError(f"--json-bytes は最低 {min_len} 以上が必要です")

    while True:
        diff = target_bytes - len(json_data.encode("utf-8"))
        if diff == 0:
            return json_data
        if diff < 0:
            raise ValueError(f"--json-bytes のサイズ調整に失敗しました: {target_bytes}")
        # 追加する文字は ASCII なので、1文字 == 1 byte。
        result.image_b64 += "A" * diff
        json_data = result.to_json()


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
    parser.add_argument(
        "--image-bytes",
        type=int,
        default=0,
        help="画像JPEG相当のバイト数。base64化して image_b64 に入れます",
    )
    parser.add_argument(
        "--json-bytes",
        type=int,
        default=0,
        help="送信するJSON datagram全体の目標バイト数（--image-bytes より優先）",
    )
    parser.add_argument("--count", type=int, default=1, help="JSON送信回数")
    parser.add_argument("--interval", type=float, default=1.0, help="送信間隔（秒）")
    parser.add_argument("--skip-hello", action="store_true", help="先頭の hello 送信を省略")
    args = parser.parse_args()

    host = args.host
    port = args.port if args.port is not None else YOLO_TO_DISPLAY_PORTS[args.drone]
    tello_name = drone_id(args.drone)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    dest = (host, port)

    print(f"Target: {host}:{port} for {tello_name}")

    if not args.skip_hello:
        print("Sending 'hello'...")
        sock.sendto(b"hello", dest)
        time.sleep(args.interval)

    for i in range(args.count):
        result = YoloResult(
            tello_id=tello_name,
            ts=now_iso(),
            detections=[Detection(label="cat", confidence=0.95, bbox=[100, 100, 200, 200])],
            image_b64=_dummy_image_b64(args.image_bytes),
        )

        json_data = _fit_json_bytes(result, args.json_bytes)
        packet = json_data.encode("utf-8")
        print(
            f"Sending JSON #{i + 1}/{args.count}: "
            f"{len(packet)} bytes (image_b64={len(result.image_b64)} chars)"
        )
        sock.sendto(packet, dest)
        if i + 1 < args.count:
            time.sleep(args.interval)

    sock.close()
    print("Done.")


if __name__ == "__main__":
    run_sender()
