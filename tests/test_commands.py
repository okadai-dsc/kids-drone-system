"""pi.tellomon.commands の純粋ロジックのテスト（#27 / 検収 A1）。"""

from __future__ import annotations

from pi.tellomon.commands import build_command, needs_confirmation


def test_no_arg_commands():
    assert build_command("command") == "command"
    assert build_command("takeoff") == "takeoff"
    assert build_command("land") == "land"
    assert build_command("streamon") == "streamon"
    assert build_command("streamoff") == "streamoff"


def test_emergency_is_no_arg_sdk_command():
    # 緊急停止は emergency（モータ即停止）。takeoff/land と同列で引数なし。
    assert build_command("emergency") == "emergency"
    assert build_command("emergency", 50) == "emergency"  # param は無視


def test_with_arg_commands():
    assert build_command("forward", 100) == "forward 100"
    assert build_command("up", 50) == "up 50"
    assert build_command("cw", 90) == "cw 90"
    assert build_command("flip", "l") == "flip l"


def test_streamwrite_and_unknown_return_none():
    assert build_command("streamwrite") is None
    assert build_command("nonexistent") is None


def test_needs_confirmation_only_for_emergency():
    assert needs_confirmation("emergency") is True
    assert needs_confirmation("land") is False
    assert needs_confirmation("takeoff") is False
