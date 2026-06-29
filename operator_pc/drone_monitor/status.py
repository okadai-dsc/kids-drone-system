"""ドローンモニタの表示判定（純粋ロジック。tkinter 非依存）。

設計書 v0.5 5.4.4 に対応（#34 / 検収 F13）:
  - ビーコン途絶の段階表示: 3秒→半透明 / 10秒→赤点滅 / 30秒→非表示
  - ケージ逸脱: 座標がケージ範囲外なら赤枠強調

UI（Tkinter）から分離してテスト可能にする。drone_monitor 本体はこの判定を使って描画する。
"""

from __future__ import annotations

from shared.schemas import CAGE_X, CAGE_Y, CAGE_Z

# 途絶段階のしきい値（秒）
STALE_SEC = 3.0  # これ以上で半透明（グレー）
LOST_SEC = 10.0  # これ以上で赤点滅
GONE_SEC = 30.0  # これ以上で非表示

# 途絶レベル
FRESH = "fresh"  # 通常表示
STALE = "stale"  # 半透明（グレー）
LOST = "lost"  # 赤点滅
GONE = "gone"  # 非表示


def staleness_level(age_s: float) -> str:
    """最後にビーコンを受けてからの経過秒数から表示段階を返す。"""
    if age_s >= GONE_SEC:
        return GONE
    if age_s >= LOST_SEC:
        return LOST
    if age_s >= STALE_SEC:
        return STALE
    return FRESH


def is_outside_cage(x: float, y: float, z: float) -> bool:
    """座標がケージ範囲外（X:0-6.5, Y:0-3.5, Z:0-2.0）なら True（赤枠強調の条件）。"""
    return not (
        CAGE_X[0] <= x <= CAGE_X[1] and CAGE_Y[0] <= y <= CAGE_Y[1] and CAGE_Z[0] <= z <= CAGE_Z[1]
    )
