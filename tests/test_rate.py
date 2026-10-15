"""shared.rate の純粋ロジックのテスト（#32 / 検収 P1）。"""

from __future__ import annotations

import pytest

from shared.rate import interval_for_rate, should_send


def test_interval_for_rate():
    assert interval_for_rate(5.0) == pytest.approx(0.2)  # 5fps → 0.2s
    assert interval_for_rate(1.0) == pytest.approx(1.0)
    assert interval_for_rate(30.0) == pytest.approx(1 / 30)


def test_interval_for_rate_rejects_non_positive():
    for bad in (0, -1.0):
        with pytest.raises(ValueError):
            interval_for_rate(bad)


def test_should_send_boundary():
    # last_sent=0.0 起点で減算誤差を避けて境界を確認（interval=0.2 = 5fps）
    assert should_send(now=0.0, last_sent=0.0, interval_sec=0.2) is False  # 経過0
    assert should_send(now=0.1, last_sent=0.0, interval_sec=0.2) is False  # 0.1s
    assert should_send(now=0.2, last_sent=0.0, interval_sec=0.2) is True  # ちょうど
    assert should_send(now=0.5, last_sent=0.0, interval_sec=0.2) is True


def test_should_send_first_frame_with_zero_last_sent():
    # last_sent=0.0 開始時は経過十分 → 送る
    assert should_send(now=123.4, last_sent=0.0, interval_sec=0.2) is True
