"""送信レート（間引き）の純粋ロジック（標準ライブラリのみ）。

yolo_proc が映像フレームを一定 Hz に間引いて結果送信するためのタイミング判定。
cv2/ultralytics に依存しないので単体テストできる（#32 / 検収 P1）。
"""

from __future__ import annotations


def interval_for_rate(rate_hz: float) -> float:
    """送信レート(Hz)から送信間隔(秒)を返す。0 以下は不正。"""
    if rate_hz <= 0:
        raise ValueError("rate_hz は 0 より大きい値を指定してください")
    return 1.0 / rate_hz


def should_send(now: float, last_sent: float, interval_sec: float) -> bool:
    """前回送信からの経過が interval 以上なら True（このフレームで送るべき）。"""
    return now - last_sent >= interval_sec
