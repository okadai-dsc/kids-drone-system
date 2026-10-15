"""pi.tellomon.beacon.build_beacon のテスト（#31 / 検収 F4）。"""

from __future__ import annotations

from pi.tellomon.beacon import build_beacon
from shared.schemas import CAGE_X, CAGE_Y


def test_position_from_status_dead_reckoning():
    b = build_beacon(
        3, {"x": 1.2, "y": 2.3, "height_cm": 150, "yaw": 90, "battery": 78, "flight_time": 120}
    )
    assert b.id == "Tello#3"
    assert b.x == 1.2
    assert b.y == 2.3
    assert b.z == 1.5  # height_cm/100
    assert b.yaw == 90
    assert b.battery == 78
    assert b.flight_time == 120


def test_position_falls_back_to_cage_center_when_absent():
    b = build_beacon(1, {"height_cm": 0})
    assert b.x == round((CAGE_X[0] + CAGE_X[1]) / 2, 2)  # 3.25
    assert b.y == round((CAGE_Y[0] + CAGE_Y[1]) / 2, 2)  # 1.75


def test_position_clamped_to_cage():
    b = build_beacon(2, {"x": 99.0, "y": -5.0, "height_cm": 0})
    assert b.x == CAGE_X[1]  # 6.5
    assert b.y == CAGE_Y[0]  # 0.0


def test_altitude_clamped_to_2m():
    b = build_beacon(1, {"x": 1.0, "y": 1.0, "height_cm": 999})
    assert b.z == 2.0


def test_yaw_wraps_modulo_360():
    b = build_beacon(1, {"x": 1.0, "y": 1.0, "yaw": 450})
    assert b.yaw == 90


def test_roundtrip_json():
    from shared.schemas import Beacon

    b = build_beacon(4, {"x": 2.0, "y": 1.0, "height_cm": 100, "yaw": 0, "battery": 50})
    assert Beacon.from_json(b.to_json()) == b
