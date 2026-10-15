"""operator_pc.drone_monitor.status の純粋ロジックのテスト（#34 / 検収 F13）。"""

from __future__ import annotations

from operator_pc.drone_monitor.status import (
    FRESH,
    GONE,
    LOST,
    STALE,
    is_cage_warning,
    is_low_battery,
    staleness_level,
)
from shared.schemas import HOME_POSITIONS


def test_staleness_level_thresholds():
    assert staleness_level(0.0) == FRESH
    assert staleness_level(2.9) == FRESH
    assert staleness_level(3.0) == STALE  # 3秒→半透明
    assert staleness_level(9.9) == STALE
    assert staleness_level(10.0) == LOST  # 10秒→赤点滅
    assert staleness_level(29.9) == LOST
    assert staleness_level(30.0) == GONE  # 30秒→非表示
    assert staleness_level(120.0) == GONE


def test_cage_warning_inside_safe_zone():
    assert is_cage_warning(0.5, 0.5, 0.0) is False  # 警告ゾーン境界ちょうどは安全側
    assert is_cage_warning(6.0, 3.0, 1.8) is False
    assert is_cage_warning(3.25, 1.75, 1.0) is False  # ケージ中央


def test_cage_warning_near_boundary():
    assert is_cage_warning(0.4, 1.0, 1.0) is True  # x 左端に接近
    assert is_cage_warning(6.1, 1.0, 1.0) is True  # x 右端に接近
    assert is_cage_warning(1.0, 0.4, 1.0) is True  # y 手前（観客席側）に接近
    assert is_cage_warning(1.0, 3.1, 1.0) is True  # y 奥に接近
    assert is_cage_warning(1.0, 1.0, 1.9) is True  # 高度上限に接近
    assert is_cage_warning(7.0, 1.0, 1.0) is True  # ケージ外も警告


def test_low_battery_threshold():
    assert is_low_battery(100) is False
    assert is_low_battery(21) is False
    assert is_low_battery(20) is True  # 20% ちょうども警告（検収 A4 と同じ <= 判定）
    assert is_low_battery(0) is True


def test_home_positions_within_safe_zone():
    """ホームポジション（配置図）が警告ゾーン内にあること（閾値との整合性ガード）。"""
    for x, y in HOME_POSITIONS.values():
        assert is_cage_warning(x, y, 0.0) is False
