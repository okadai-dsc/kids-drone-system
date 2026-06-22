"""pi.tellomon.cage の純粋ロジックのテスト（#30 / 検収 F5・F6・S2・S3）。"""

from __future__ import annotations

import math

import pytest

from pi.tellomon.cage import (
    DroneState,
    apply_command,
    clamp_to_cage,
    is_within_cage,
    would_exceed,
)


def test_forward_moves_along_plus_y_when_yaw_zero():
    # yaw=0 は +Y 方向。forward 100cm → y が +1.0m。
    s = apply_command(DroneState(x=3.0, y=1.0, z=1.0, yaw=0), "forward", 100)
    assert s.x == pytest.approx(3.0)
    assert s.y == pytest.approx(2.0)
    assert s.z == pytest.approx(1.0)


def test_forward_moves_along_plus_x_when_yaw_90():
    # yaw=90 は +X 方向（時計回り）。forward 200cm → x が +2.0m。
    s = apply_command(DroneState(x=1.0, y=1.0, z=1.0, yaw=90), "forward", 200)
    assert s.x == pytest.approx(3.0)
    assert s.y == pytest.approx(1.0, abs=1e-9)


def test_back_right_left_directions_when_yaw_zero():
    base = DroneState(x=3.0, y=2.0, z=1.0, yaw=0)
    assert apply_command(base, "back", 100).y == pytest.approx(1.0)
    assert apply_command(base, "right", 100).x == pytest.approx(4.0)
    assert apply_command(base, "left", 100).x == pytest.approx(2.0)


def test_up_down_changes_altitude():
    base = DroneState(z=1.0)
    assert apply_command(base, "up", 50).z == pytest.approx(1.5)
    assert apply_command(base, "down", 30).z == pytest.approx(0.7)


def test_turn_wraps_modulo_360():
    assert apply_command(DroneState(yaw=350), "cw", 20).yaw == 10
    assert apply_command(DroneState(yaw=10), "ccw", 20).yaw == 350


def test_non_motion_opcode_is_noop():
    base = DroneState(x=1.0, y=2.0, z=1.0, yaw=45)
    for op in ("takeoff", "land", "streamon", "emergency"):
        assert apply_command(base, op, 0) == base


def test_is_within_cage_bounds():
    assert is_within_cage(DroneState(x=0.0, y=0.0, z=0.0))
    assert is_within_cage(DroneState(x=6.5, y=3.5, z=2.0))
    assert not is_within_cage(DroneState(x=6.6, y=1.0, z=1.0))
    assert not is_within_cage(DroneState(x=1.0, y=1.0, z=2.1))  # 高度2m超


def test_clamp_to_cage():
    c = clamp_to_cage(DroneState(x=-1.0, y=9.0, z=5.0))
    assert (c.x, c.y, c.z) == (0.0, 3.5, 2.0)


def test_would_exceed_suppresses_out_of_cage_move():
    # x=6.0 で +X(yaw=90) に 100cm 前進 → x=7.0 > 6.5 → 抑止対象
    s = DroneState(x=6.0, y=1.0, z=1.0, yaw=90)
    assert would_exceed(s, "forward", 100) is True
    # 同じ位置で 40cm なら x=6.4 → 範囲内 → 抑止しない
    assert would_exceed(s, "forward", 40) is False


def test_would_exceed_altitude_limit():
    s = DroneState(x=1.0, y=1.0, z=1.8, yaw=0)
    assert would_exceed(s, "up", 30) is True  # z=2.1 > 2.0
    assert would_exceed(s, "up", 20) is False  # z=2.0 ちょうど


def test_yaw_then_forward_diagonal():
    # yaw=45 で forward 100cm → x,y それぞれ sin45/cos45 * 1.0
    s = apply_command(DroneState(x=2.0, y=1.0, z=1.0, yaw=45), "forward", 100)
    assert s.x == pytest.approx(2.0 + math.sqrt(0.5))
    assert s.y == pytest.approx(1.0 + math.sqrt(0.5))
