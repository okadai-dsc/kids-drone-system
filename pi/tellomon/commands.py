"""Tello コマンド文字列の組み立て（純粋ロジック。socket/GUI 非依存）。

do_GET / check_queue が受ける opcode・param から、Tello SDK に送る
コマンド文字列を一元的に生成する。`emergency`（Stop motors immediately、検収 A1/A2）も
takeoff/land と同列の SDK コマンドとしてここで扱う。

`streamwrite`（画面キャプチャ）は Tello へ送らないアプリ内コマンドなので None を返す。
未知の opcode も None。
"""

from __future__ import annotations

# 引数なしの SDK コマンド
_NO_ARG = frozenset({"command", "takeoff", "land", "emergency", "streamon", "streamoff"})
# 引数（距離 cm / 角度 deg / 方向）を伴う SDK コマンド
_WITH_ARG = frozenset(
    {"up", "down", "cw", "ccw", "forward", "back", "left", "right", "flip", "downvision"}
)

# 押下時に確認ダイアログを挟むべき危険コマンド（誤操作防止。検収 A1）
CONFIRM_REQUIRED = frozenset({"emergency"})


def build_command(opcode: str, param: str | int = "") -> str | None:
    """opcode/param から Tello へ送る SDK コマンド文字列を返す。

    送る必要のないアプリ内コマンド（streamwrite）や未知 opcode は None。
    """
    if opcode in _NO_ARG:
        return opcode
    if opcode in _WITH_ARG:
        return f"{opcode} {param}"
    return None


def needs_confirmation(opcode: str) -> bool:
    """押下時に確認ダイアログが必要な opcode なら True。"""
    return opcode in CONFIRM_REQUIRED
