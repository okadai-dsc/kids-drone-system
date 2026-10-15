"""ドローンモニタの表示判定（純粋ロジック。tkinter 非依存）。

設計書 v0.5 5.4.4 に対応（#34 / 検収 F13）:
  - ビーコン途絶の段階表示: 3秒→半透明 / 10秒→赤点滅 / 30秒→非表示
  - ケージ逸脱警告: 座標がケージ境界に近づいたら赤枠強調（逸脱前の事前警告）
  - 低バッテリ警告: 20% 以下でバッテリ表示を赤太字

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


# ケージ逸脱警告ゾーン（ケージ境界の一回り内側）。制御側（tellomon）がケージ外に
# 出るコマンドを抑止するため、表示側は境界に「近づいた」時点で事前に警告する。
WARN_MARGIN_XY = 0.5  # 水平方向の警告マージン(m)
WARN_MARGIN_Z_TOP = 0.2  # 高度上限の警告マージン(m)。下限(床側)はマージンなし
WARN_X = (CAGE_X[0] + WARN_MARGIN_XY, CAGE_X[1] - WARN_MARGIN_XY)  # 0.5〜6.0
WARN_Y = (CAGE_Y[0] + WARN_MARGIN_XY, CAGE_Y[1] - WARN_MARGIN_XY)  # 0.5〜3.0
WARN_Z = (CAGE_Z[0], CAGE_Z[1] - WARN_MARGIN_Z_TOP)  # 0〜1.8

# バッテリ残量の警告しきい値（%）。Pi 側 tellomon（検収 A4）と同じ値。
# コンポーネントを独立させるため pi パッケージからは import しない。
LOW_BATTERY_THRESHOLD = 20


def is_cage_warning(x: float, y: float, z: float) -> bool:
    """座標が警告ゾーン（X:0.5-6.0, Y:0.5-3.0, Z:0-1.8）の外なら True（赤枠強調の条件）。

    ケージ範囲外はもちろん、範囲内でも境界に近づいた時点で警告する。
    """
    return not (
        WARN_X[0] <= x <= WARN_X[1] and WARN_Y[0] <= y <= WARN_Y[1] and WARN_Z[0] <= z <= WARN_Z[1]
    )


def is_low_battery(battery_pct: int) -> bool:
    """バッテリ残量が 20% 以下なら True（%表示の赤太字化の条件）。"""
    return battery_pct <= LOW_BATTERY_THRESHOLD
