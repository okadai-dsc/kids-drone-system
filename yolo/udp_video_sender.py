"""Dummy UDP video sender for yolo_proc (#10).

Generates a simple video stream, or loops a still image, and sends it to the
Pi -> YOLO UDP video port. This is only for local integration testing.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time

import cv2
import numpy as np

# 親ディレクトリの shared をインポートできるようにパスを追加
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from shared.ports import PI_TO_YOLO_VIDEO_PORTS  # noqa: E402


def _parse_args():
    parser = argparse.ArgumentParser(description="ダミー映像を UDP で yolo_proc に送信")
    parser.add_argument("--host", default="127.0.0.1", help="送信先ホスト")
    parser.add_argument("--drone", type=int, choices=[1, 2, 3, 4], default=1, help="ドローン番号")
    parser.add_argument("--port", type=int, help="送信先ポート（既定: --drone から自動）")
    parser.add_argument("--image", help="指定画像を動画フレームとして繰り返し送信")
    parser.add_argument("--width", type=int, default=640, help="送信フレーム幅")
    parser.add_argument("--height", type=int, default=360, help="送信フレーム高さ")
    parser.add_argument("--fps", type=float, default=15.0, help="送信FPS")
    parser.add_argument("--seconds", type=float, default=0.0, help="送信秒数（0ならCtrl-Cまで継続）")
    return parser.parse_args()


def _load_image(path, width, height):
    frame = cv2.imread(path)
    if frame is None:
        raise ValueError(f"画像を読み込めません: {path}")
    return cv2.resize(frame, (width, height))


def _make_pattern(width, height, frame_index):
    frame = np.full((height, width, 3), (30, 30, 30), dtype=np.uint8)
    x = int((frame_index * 8) % max(1, width - 120))
    cv2.rectangle(frame, (x, 90), (x + 120, 210), (0, 180, 255), -1)
    cv2.putText(
        frame,
        f"dummy frame {frame_index}",
        (24, 48),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        (255, 255, 255),
        2,
    )
    return frame


def _ffmpeg_exe():
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        return ffmpeg
    try:
        import imageio_ffmpeg
    except ImportError as exc:
        raise RuntimeError(
            "ffmpeg が見つかりません。`uv add --project yolo imageio-ffmpeg` "
            "または OS 側に ffmpeg をインストールしてください。"
        ) from exc
    return imageio_ffmpeg.get_ffmpeg_exe()


def _open_ffmpeg_writer(url, width, height, fps):
    command = [
        _ffmpeg_exe(),
        "-hide_banner",
        "-loglevel",
        "warning",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "bgr24",
        "-s",
        f"{width}x{height}",
        "-r",
        str(fps),
        "-i",
        "-",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-tune",
        "zerolatency",
        "-pix_fmt",
        "yuv420p",
        "-f",
        "mpegts",
        url,
    ]
    return subprocess.Popen(command, stdin=subprocess.PIPE)


def main():
    args = _parse_args()
    port = args.port if args.port is not None else PI_TO_YOLO_VIDEO_PORTS[args.drone]
    url = f"udp://{args.host}:{port}?pkt_size=1316"
    size = (args.width, args.height)

    writer = _open_ffmpeg_writer(url, args.width, args.height, args.fps)

    image_frame = _load_image(args.image, *size) if args.image else None
    interval = 1.0 / args.fps
    started = time.monotonic()
    frame_index = 0
    print(f"Streaming dummy video to {url} ({args.width}x{args.height} @ {args.fps}fps)")

    try:
        while True:
            if args.seconds > 0 and time.monotonic() - started >= args.seconds:
                break
            frame = image_frame.copy() if image_frame is not None else _make_pattern(*size, frame_index)
            writer.stdin.write(frame.tobytes())
            frame_index += 1
            time.sleep(interval)
    except BrokenPipeError as exc:
        raise RuntimeError("ffmpeg への映像書き込みに失敗しました") from exc
    except KeyboardInterrupt:
        print("\nDummy video sender stopped.")
    finally:
        if writer.stdin:
            writer.stdin.close()
        writer.wait(timeout=5)
        print(f"Sent {frame_index} frames.")


if __name__ == "__main__":
    main()
