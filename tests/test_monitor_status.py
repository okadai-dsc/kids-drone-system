"""operator_pc.drone_monitor.status の純粋ロジックのテスト（#34 / 検収 F13）。"""

from __future__ import annotations

from operator_pc.drone_monitor.status import (
    FRESH,
    GONE,
    LOST,
    STALE,
    is_outside_cage,
    staleness_level,
)


def test_staleness_level_thresholds():
    assert staleness_level(0.0) == FRESH
    assert staleness_level(2.9) == FRESH
    assert staleness_level(3.0) == STALE  # 3秒→半透明
    assert staleness_level(9.9) == STALE
    assert staleness_level(10.0) == LOST  # 10秒→赤点滅
    assert staleness_level(29.9) == LOST
    assert staleness_level(30.0) == GONE  # 30秒→非表示
    assert staleness_level(120.0) == GONE


def test_is_outside_cage_inside():
    assert is_outside_cage(0.0, 0.0, 0.0) is False
    assert is_outside_cage(6.5, 3.5, 2.0) is False
    assert is_outside_cage(3.25, 1.75, 1.0) is False


def test_is_outside_cage_outside():
    assert is_outside_cage(6.6, 1.0, 1.0) is True  # x 超過
    assert is_outside_cage(1.0, -0.1, 1.0) is True  # y 下限割れ
    assert is_outside_cage(1.0, 1.0, 2.1) is True  # 高度 2m 超
