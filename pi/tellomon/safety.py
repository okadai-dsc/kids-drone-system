"""安全機能の純粋ロジック（#29 / 検収 A3・A4）。socket/GUI 非依存。

- parse_tello_status: Tello ステータス文字列のパース（StatusRecever から抽出）。
- should_autoland: 通信断（status 途絶）が一定秒数を超えたら自動着陸すべきかの判定。
- is_low_battery: バッテリ残量が閾値以下かの判定（%表示の赤枠化に使う）。

通信断時の自動措置は land（安全に降ろす）。手動の緊急停止のみ emergency（モータ即停止）。
"""

from __future__ import annotations

LOW_BATTERY_THRESHOLD = 20  # % 以下で警告（検収 A4）
AUTOLAND_TIMEOUT_S = 3.0  # status 途絶がこの秒数を超えたら自動着陸（検収 A3）


def parse_tello_status(data: str) -> dict:
    """Tello のステータス文字列 "h:120;bat:78;time:50;yaw:90;vgx:0;..." を dict 化する。

    返すキー: height_cm / battery / flight_time / yaw / speed_cm_s。
    欠損キーは 0。数値化できない値は無視（0 のまま）。
    """
    fields: dict[str, int] = {}
    for token in data.split(";"):
        if ":" not in token:
            continue
        key, _, val = token.partition(":")
        try:
            fields[key.strip()] = int(float(val))
        except ValueError:
            continue

    vgx = fields.get("vgx", 0)
    vgy = fields.get("vgy", 0)
    vgz = fields.get("vgz", 0)
    speed = int((vgx * vgx + vgy * vgy + vgz * vgz) ** 0.5)
    return {
        "height_cm": fields.get("h", 0),
        "battery": fields.get("bat", 0),
        "flight_time": fields.get("time", 0),
        "yaw": fields.get("yaw", 0),
        "speed_cm_s": speed,
    }


def should_autoland(
    health_ticks: int, interval_ms: int, timeout_s: float = AUTOLAND_TIMEOUT_S
) -> bool:
    """status 未受信が継続した tick 数から、自動着陸すべきか判定する。

    health_ticks: 最後に status を受信してからの経過 tick 数（受信で 0 にリセットされる想定）。
    interval_ms: 1 tick の間隔（ms）。
    経過秒数 = health_ticks * interval_ms / 1000 が timeout_s 以上で True。
    """
    return health_ticks * interval_ms / 1000.0 >= timeout_s


def is_low_battery(battery_pct: int, threshold: int = LOW_BATTERY_THRESHOLD) -> bool:
    """バッテリ残量が閾値以下なら True（%表示を赤枠化する条件）。"""
    return battery_pct <= threshold
