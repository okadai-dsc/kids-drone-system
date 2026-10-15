"""pi.tellomon.safety の純粋ロジックのテスト（#29 / 検収 A3・A4）。"""

from __future__ import annotations

from pi.tellomon.safety import is_low_battery, parse_tello_status, should_autoland


def test_parse_status_basic():
    s = "pitch:0;roll:0;yaw:90;vgx:3;vgy:4;vgz:0;h:120;bat:78;time:50;"
    d = parse_tello_status(s)
    assert d["height_cm"] == 120
    assert d["battery"] == 78
    assert d["flight_time"] == 50
    assert d["yaw"] == 90
    assert d["speed_cm_s"] == 5  # sqrt(3^2+4^2)


def test_parse_status_missing_keys_default_zero():
    d = parse_tello_status("bat:55;")
    assert d["battery"] == 55
    assert d["height_cm"] == 0
    assert d["yaw"] == 0
    assert d["speed_cm_s"] == 0


def test_parse_status_ignores_garbage():
    d = parse_tello_status("bat:xx;h:90;;:;")
    assert d["battery"] == 0  # 数値化不可は無視
    assert d["height_cm"] == 90


def test_should_autoland_3s_boundary_at_200ms_interval():
    # 200ms tick。15 tick = 3.0s でちょうど発火、14 tick(2.8s) は未発火。
    assert should_autoland(14, 200) is False
    assert should_autoland(15, 200) is True
    assert should_autoland(20, 200) is True


def test_should_autoland_custom_timeout():
    # 1000ms tick: 2 tick=2s 未発火, 3 tick=3s 発火, 5 tick=5s 発火
    assert should_autoland(2, 1000, timeout_s=3.0) is False
    assert should_autoland(3, 1000, timeout_s=3.0) is True
    assert should_autoland(5, 1000, timeout_s=3.0) is True


def test_is_low_battery_threshold():
    assert is_low_battery(20) is True  # 20% 以下
    assert is_low_battery(19) is True
    assert is_low_battery(21) is False
    assert is_low_battery(100) is False
