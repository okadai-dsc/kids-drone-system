# kids-drone-system

子供向け体験イベント **「おもしろ体験でぇ～」**（2026/7/24-25 開催）の出展システム。

子供が Scratch で Tello ドローンを操作し、ドローンの空撮映像を YOLO で犬猫検知 → 中央モニタに位置と検知結果をリアルタイム表示する。

## システム構成

```mermaid
flowchart LR
    T["Tello EDU<br/>4台"] <-.->|"Wi-Fi 2.4GHz"| P["Raspberry Pi 4台<br/>Scratch + tellomon.py"]
    P ==>|"ビデオ<br/>:11112〜11115"| Y["YOLO<br/>4インスタンス"]
    Y -->|"検知結果<br/>:11212〜11215"| D["YOLO結果表示<br/>(中央画面)"]
    P -.->|"ビーコン :11231"| M["ドローンモニタ<br/>(中央画面)"]

    subgraph LAN["ノートPC 192.168.0.100"]
        Y
        D
        M
    end

    classDef tello fill:#e3f2fd,stroke:#1976d2,stroke-width:2px
    classDef pi fill:#fff9c4,stroke:#f9a825,stroke-width:2px
    classDef pc fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px
    class T tello
    class P pi
    class Y,D,M pc
```

- **同時稼働 4 台**（Tello EDU / Raspberry Pi 各4台、YOLO PC 1台、中央ノートPC 1台）
- 操作 UI は Scratch のみ（子供が触る唯一の UI）
- 中央モニタは「全機俯瞰」用、個別 UI は作らない

詳細は [docs/figures/system-arch.mmd](docs/figures/system-arch.mmd) と運用配置図 [docs/figures/operation-layout.mmd](docs/figures/operation-layout.mmd) 参照。

## ディレクトリ構成

| ディレクトリ | 役割 |
|---|---|
| `pi/tellomon/` | Pi 側の Tello 制御プログラム（映像転送・ビーコン送信・HTTP API）|
| `yolo_pc/yolo_proc/` | YOLO PC 側の推論プロセス（YOLOv8）|
| `operator_pc/drone_monitor/` | 中央ノートPC のドローンモニタ |
| `operator_pc/yolo_display/` | 中央ノートPC の YOLO 結果表示 |
| `shared/` | ポート番号・JSON フォーマット等の共通定義 |
| `Scratch/` | 子供向け UI（LLK 公式 clone + drone 拡張 / **git 管理外**）|
| `docs/` | 設計書・計画書 |

> `Scratch/` は LLK 公式リポジトリの clone のため `.gitignore` で除外しています。改修要否は 6/30 時点で判断し、必要なら部 org に fork して submodule 化します。


## ライセンス

[MIT](LICENSE)
