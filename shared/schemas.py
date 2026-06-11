"""ビーコン / YOLO 検知結果の JSON スキーマ（通信契約）。

出典: docs/開発者補足/仕様詳細ドラフト.md §1（ビーコン）・§2.5（YOLO 結果）。
標準ライブラリのみで完結させる（送受信は各コンポーネントが socket で行う）。

子供向け UI の配色（同 §4.2）は表示側（#5/#4）の関心なので、ここには持たない。
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime

# --- ケージ範囲（逸脱判定に使用。単位 m）-----------------------------
# ケージ左下を (0, 0) とする。出典: 仕様詳細ドラフト.md §3.3。
CAGE_X = (0.0, 6.5)
CAGE_Y = (0.0, 3.5)
CAGE_Z = (0.0, 2.0)

# --- 検知対象ラベル（YOLO）-------------------------------------------
DETECT_LABELS = ("cat", "dog")


def drone_id(n: int) -> str:
    """機体番号から識別子文字列を作る。drone_id(3) -> 'Tello#3'。"""
    return f"Tello#{n}"


def now_iso() -> str:
    """現在時刻を ISO8601（ミリ秒まで）で返す。ビーコン/結果の ts に使う。"""
    return datetime.now().isoformat(timespec="milliseconds")


@dataclass
class Beacon:
    """ドローン状態ビーコン（Pi → ドローンモニタ、UDP 11231、1Hz）。

    仕様詳細ドラフト.md §1.2 の項目定義に対応。
    """

    id: str  # "Tello#1"〜"Tello#4"
    ts: str  # ISO8601
    x: float  # m, 0.0〜6.5（横）
    y: float  # m, 0.0〜3.5（縦）
    z: float  # m, 0.0〜2.0（高度）
    yaw: int  # degree, 0〜359（0=Y軸正方向、時計回り）
    battery: int  # %, 0〜100
    flight_time: int  # sec, 連続飛行時間

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, data: str) -> Beacon:
        return cls(**json.loads(data))


@dataclass
class Detection:
    """YOLO 検知 1 件。bbox は画像座標系 [x1, y1, x2, y2]。"""

    label: str
    confidence: float
    bbox: list[int]


@dataclass
class YoloResult:
    """YOLO 検知結果（YOLOインスタンス → 結果表示、UDP 11212〜11215）。

    仕様詳細ドラフト.md §2.5 のフォーマットに対応。
    """

    tello_id: str
    ts: str
    detections: list[Detection] = field(default_factory=list)
    image_b64: str = ""  # bbox 描画済み JPEG の base64（目標 < 50KB）

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, data: str) -> YoloResult:
        obj = json.loads(data)
        detections = [Detection(**d) for d in obj.get("detections", [])]
        return cls(
            tello_id=obj["tello_id"],
            ts=obj["ts"],
            detections=detections,
            image_b64=obj.get("image_b64", ""),
        )
