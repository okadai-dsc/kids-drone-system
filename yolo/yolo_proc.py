"""yolo_proc: 映像受信 → YOLO 推論 → 検知結果送信 を1プロセスで動かす (#10)。

Pi から転送された Tello 映像（UDP 生 H.264）を受信し、各フレームを YOLO で推論、
犬猫（cat/dog）の検知結果を JSON（shared.schemas.YoloResult）にして
結果表示（yolo_display）へ UDP 送信する。

実行例（中央ノートPC、リポジトリルートから）:
    uv run python yolo/yolo_proc.py --drone 1
        → udp://@0.0.0.0:11112 で映像受信、127.0.0.1:11212 へ結果送信

映像ストリーム無しでの単発テスト/デモ:
    uv run python yolo/yolo_proc.py --drone 1 --image path/to/cat.jpg
        → 画像1枚を推論して結果を1回送信して終了

#9 の udp_receiver.py（ダミー受信機）を相手に送受信を確認できる。
"""

import argparse
import base64
import os
import socket
import sys
import time
from collections import deque

import cv2
from ultralytics import YOLO

# 親ディレクトリの shared をインポートできるようにパスを追加（#9 の流儀に合わせる）
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from shared.ports import PI_TO_YOLO_VIDEO_PORTS, YOLO_TO_DISPLAY_PORTS  # noqa: E402
from shared.rate import interval_for_rate, should_send  # noqa: E402
from shared.schemas import DETECT_LABELS, Detection, YoloResult, drone_id, now_iso  # noqa: E402

# 検知枠の色（cat/dog で色分け。BGR）
_BOX_COLORS = {"cat": (0, 200, 0), "dog": (0, 160, 255)}
_UDP_PACKET_TARGET_BYTES = 50_000

try:
    import psutil
except ImportError:
    psutil = None


def detect(model, frame, conf):
    """1フレームを推論し、(検知リスト, 枠を描画した画像) を返す。

    cat/dog（DETECT_LABELS）のみ対象。bbox は画像座標系 [x1,y1,x2,y2]。
    """
    result = model(frame, verbose=False)[0]
    detections = []
    annotated = frame.copy()
    for box in result.boxes:
        label = model.names[int(box.cls)]
        confidence = float(box.conf)
        if label not in DETECT_LABELS or confidence < conf:
            continue
        x1, y1, x2, y2 = (int(v) for v in box.xyxy[0])
        detections.append(
            Detection(label=label, confidence=round(confidence, 2), bbox=[x1, y1, x2, y2])
        )
        color = _BOX_COLORS.get(label, (0, 200, 0))
        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
        cv2.putText(
            annotated,
            f"{label} {confidence:.2f}",
            (x1, max(0, y1 - 6)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            color,
            2,
        )
    return detections, annotated


def encode_jpeg_b64(frame, max_width, quality):
    """JPEG に圧縮して base64 文字列を返す（UDP 送信のため小さく保つ）。"""
    h, w = frame.shape[:2]
    if w > max_width:
        scale = max_width / w
        frame = cv2.resize(frame, (max_width, int(h * scale)))
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        return ""
    return base64.b64encode(buf).decode("ascii")


def build_result(drone_num, detections, annotated, max_width, quality):
    return YoloResult(
        tello_id=drone_id(drone_num),
        ts=now_iso(),
        detections=detections,
        image_b64=encode_jpeg_b64(annotated, max_width, quality),
    )


def send_result(sock, dest, result):
    packet = result.to_json().encode("utf-8")
    sock.sendto(packet, dest)
    suffix = ""
    if len(packet) > _UDP_PACKET_TARGET_BYTES:
        suffix = f" WARNING: over {_UDP_PACKET_TARGET_BYTES} byte target"
    print(
        f"sent result -> {dest}: {len(packet)} bytes, "
        f"image_b64={len(result.image_b64)} chars{suffix}"
    )


class Metrics:
    def __init__(self, interval_sec):
        self.interval_sec = interval_sec
        self.started = time.monotonic()
        self.last_report = self.started
        self.read_times = deque()
        self.infer_times = deque()
        self.sent_count = 0
        self.reopen_count = 0
        self.process = psutil.Process(os.getpid()) if psutil is not None else None

    def mark_read(self, now):
        self._append_recent(self.read_times, now)

    def mark_infer(self, now):
        self._append_recent(self.infer_times, now)

    def mark_sent(self):
        self.sent_count += 1

    def mark_reopen(self):
        self.reopen_count += 1

    def maybe_report(self, now, drone_num, video_port, display_port):
        if self.interval_sec <= 0 or now - self.last_report < self.interval_sec:
            return
        elapsed = now - self.started
        read_fps = len(self.read_times) / min(elapsed, self.interval_sec)
        infer_fps = len(self.infer_times) / min(elapsed, self.interval_sec)
        memory = "rss_mb=unknown"
        if self.process is not None:
            memory = f"rss_mb={self.process.memory_info().rss / 1024 / 1024:.1f}"
        print(
            "metrics "
            f"drone={drone_id(drone_num)} rx={video_port} tx={display_port} "
            f"elapsed_sec={elapsed:.1f} read_fps={read_fps:.2f} "
            f"infer_fps={infer_fps:.2f} sent={self.sent_count} "
            f"reopens={self.reopen_count} {memory}"
        )
        self.last_report = now

    def _append_recent(self, values, now):
        values.append(now)
        cutoff = now - self.interval_sec
        while values and values[0] < cutoff:
            values.popleft()


def _parse_args():
    parser = argparse.ArgumentParser(description="yolo_proc: 映像受信→YOLO推論→結果送信 (#10)")
    parser.add_argument("--drone", type=int, choices=[1, 2, 3, 4], default=1, help="ドローン番号")
    parser.add_argument("--video-host", default="0.0.0.0", help="映像受信の待受ホスト")
    parser.add_argument(
        "--video-port",
        "--rx",
        dest="video_port",
        type=int,
        help="映像受信ポート（既定: --drone から自動）",
    )
    parser.add_argument("--display-host", default="127.0.0.1", help="結果送信先ホスト")
    parser.add_argument(
        "--display-port",
        "--tx",
        dest="display_port",
        type=int,
        help="結果送信ポート（既定: --drone から自動）",
    )
    parser.add_argument("--model", default="yolov8n.pt", help="YOLO モデル")
    parser.add_argument("--conf", type=float, default=0.4, help="検知の信頼度しきい値")
    parser.add_argument("--max-width", type=int, default=480, help="送信画像の最大幅(px)")
    parser.add_argument("--jpeg-quality", type=int, default=60, help="JPEG 品質(1-100)")
    parser.add_argument(
        "--rate", type=float, default=5.0, help="結果送信レート Hz（既定 5Hz / 検収 P1）"
    )
    parser.add_argument("--metrics-interval", type=float, default=10.0, help="メトリクス出力間隔秒")
    parser.add_argument(
        "--duration", type=float, default=0.0, help="指定秒数で終了（0ならCtrl-Cまで継続）"
    )
    parser.add_argument("--image", help="（テスト用）映像の代わりに画像1枚を推論して1回送信")
    return parser.parse_args()


def main():
    args = _parse_args()
    interval = interval_for_rate(args.rate)  # rate<=0 はここで ValueError
    if args.metrics_interval < 0:
        raise ValueError("--metrics-interval は 0 以上を指定してください")

    video_port = args.video_port or PI_TO_YOLO_VIDEO_PORTS[args.drone]
    display_port = args.display_port or YOLO_TO_DISPLAY_PORTS[args.drone]
    dest = (args.display_host, display_port)

    print(f"loading model: {args.model}")
    model = YOLO(args.model)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # --- テストモード: 画像1枚 → 推論 → 1回送信 → 終了 ---
    if args.image:
        frame = cv2.imread(args.image)
        if frame is None:
            print(f"画像を読み込めません: {args.image}")
            return
        detections, annotated = detect(model, frame, args.conf)
        result = build_result(args.drone, detections, annotated, args.max_width, args.jpeg_quality)
        send_result(sock, dest, result)
        labels = [d.label for d in detections]
        print(f"detections={labels}")
        sock.close()
        return

    # --- 本番モード: UDP 映像を受信し続けて 1Hz で結果送信 ---
    url = f"udp://@{args.video_host}:{video_port}"
    print(f"opening video: {url}  -> sending results to {dest} @ {args.rate}Hz")
    cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
    metrics = Metrics(args.metrics_interval)
    started = time.monotonic()
    last_sent = 0.0
    try:
        while True:
            if args.duration > 0 and time.monotonic() - started >= args.duration:
                print("\nduration reached.")
                break
            ok, frame = cap.read()
            now = time.monotonic()
            if not ok:
                # 受信できない時は開き直して継続（#11 で堅牢化）
                cap.release()
                cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
                metrics.mark_reopen()
                metrics.maybe_report(now, args.drone, video_port, display_port)
                continue
            metrics.mark_read(now)
            if not should_send(now, last_sent, interval):
                metrics.maybe_report(now, args.drone, video_port, display_port)
                continue  # 指定レートに間引き（フレームは読み捨てて最新を使う）
            last_sent = now
            detections, annotated = detect(model, frame, args.conf)
            metrics.mark_infer(time.monotonic())
            result = build_result(
                args.drone, detections, annotated, args.max_width, args.jpeg_quality
            )
            send_result(sock, dest, result)
            metrics.mark_sent()
            metrics.maybe_report(time.monotonic(), args.drone, video_port, display_port)
            print(
                f"{result.ts}  {drone_id(args.drone)}  detections={[d.label for d in detections]}"
            )
    except KeyboardInterrupt:
        print("\nstopped.")
    finally:
        cap.release()
        sock.close()


if __name__ == "__main__":
    main()
