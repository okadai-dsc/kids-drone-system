"""ケージ制御と想定位置の積算（純粋ロジック。cv2/tkinter/socket 非依存）。

設計書 v0.5 5.1(5) / 検収 F5・F6・S2・S3 に対応。
離陸時の位置・方向を起点に、Tello の移動/回転コマンドから機体の想定位置を
dead-reckoning で積算し、ケージ（飛行可能範囲）からの逸脱を判定・抑止する。

座標系（shared.schemas より）:
  - ケージ左下を (0,0)、単位 m。x:0〜6.5（横）, y:0〜3.5（縦）, z:0〜2.0（高度）
  - yaw: degree, 0=Y軸正方向、時計回り（0→+Y, 90→+X, 180→-Y, 270→-X）

Tello SDK コマンドの単位:
  - forward/back/left/right/up/down の param は cm（本モジュールで m に換算）
  - cw/ccw の param は degree

本体（__main__.py）はこの純関数を呼ぶだけにし、GUI 描画やソケット送信は本体側で行う。
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

from shared.schemas import CAGE_X, CAGE_Y, CAGE_Z

# 水平移動コマンドと、機首方向(yaw=0,+Y)を基準にした進行方向のオフセット角(度)。
# 進行方向ベクトルは (sin(yaw+offset), cos(yaw+offset))。
_MOVE_OFFSET_DEG = {
    "forward": 0,
    "back": 180,
    "right": 90,
    "left": 270,
}
_UP_DOWN = {"up": 1, "down": -1}
_TURN_SIGN = {"cw": 1, "ccw": -1}  # cw=時計回り(+), ccw=反時計回り(-)

# 想定位置を変化させる（=ケージ判定対象の）コマンド一覧。
CAGE_MOTION = frozenset(_MOVE_OFFSET_DEG) | frozenset(_UP_DOWN) | frozenset(_TURN_SIGN)


@dataclass(frozen=True)
class DroneState:
    """機体の想定状態（m, degree）。"""

    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    yaw: int = 0  # 0〜359


def _heading_vector(yaw_deg: float) -> tuple[float, float]:
    """yaw(度, 0=+Y, 時計回り) の進行方向単位ベクトル (dx, dy) を返す。"""
    rad = math.radians(yaw_deg)
    return math.sin(rad), math.cos(rad)


def apply_command(state: DroneState, opcode: str, param: float) -> DroneState:
    """1 コマンドを想定状態に積算して新しい DroneState を返す（純関数）。

    対象 opcode: forward/back/left/right（cm）, up/down（cm）, cw/ccw（degree）。
    それ以外（takeoff/land/streamon 等）は状態を変えずそのまま返す。
    """
    if opcode in _MOVE_OFFSET_DEG:
        dist_m = float(param) / 100.0
        dx_unit, dy_unit = _heading_vector(state.yaw + _MOVE_OFFSET_DEG[opcode])
        return replace(state, x=state.x + dist_m * dx_unit, y=state.y + dist_m * dy_unit)

    if opcode in _UP_DOWN:
        return replace(state, z=state.z + _UP_DOWN[opcode] * float(param) / 100.0)

    if opcode in _TURN_SIGN:
        new_yaw = (state.yaw + _TURN_SIGN[opcode] * int(param)) % 360
        return replace(state, yaw=new_yaw)

    return state


def is_within_cage(state: DroneState) -> bool:
    """想定位置がケージ範囲内なら True。"""
    return (
        CAGE_X[0] <= state.x <= CAGE_X[1]
        and CAGE_Y[0] <= state.y <= CAGE_Y[1]
        and CAGE_Z[0] <= state.z <= CAGE_Z[1]
    )


def clamp_to_cage(state: DroneState) -> DroneState:
    """想定位置をケージ範囲に丸めた DroneState を返す。"""
    return replace(
        state,
        x=min(max(state.x, CAGE_X[0]), CAGE_X[1]),
        y=min(max(state.y, CAGE_Y[0]), CAGE_Y[1]),
        z=min(max(state.z, CAGE_Z[0]), CAGE_Z[1]),
    )


def would_exceed(state: DroneState, opcode: str, param: float) -> bool:
    """そのコマンドを実行するとケージ外（高度2m超含む）に出る場合 True（抑止対象）。"""
    return not is_within_cage(apply_command(state, opcode, param))
