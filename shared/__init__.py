"""kids-drone-system 共通定義パッケージ。

各コンポーネント（pi/tellomon, yolo_pc/yolo_proc, operator_pc/*）から
`from shared.ports import ...` / `from shared.schemas import ...` で参照する。
リポジトリルートから起動する前提（カレントが sys.path に乗る）。
"""
