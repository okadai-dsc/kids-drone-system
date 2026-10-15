# 開発ガイド

## ローカル開発用

```bash
# 1. clone
git clone https://github.com/okadai-dsc/kids-drone-system.git
cd kids-drone-system

# 2. Python 環境（Python 3.12 + uv workspace）
uv sync

# 3. pre-commit のインストール（初回のみ）
uv run pre-commit install

# 4. lint / format（保存時自動整形を推奨）
uv run ruff check .
uv run ruff format .
```

- パッケージ管理は **uv** に統一。`pip` や `requirements.txt` は使わない
- スタイルは **Ruff**（設定は [../pyproject.toml](../pyproject.toml)）。エディタの保存時自動整形を有効にすると楽
- **pre-commit**：`git commit` するたびに自動で Ruff（lint + format）が走り、整形が必要なら止まる。慌てずに再 add → 再 commit
- **CI**：PR を出すと GitHub Actions で同じ Ruff チェックが走る（[../.github/workflows/lint.yml](../.github/workflows/lint.yml)）。赤になっても焦らずローカルで `uv run ruff format .` してから push

## ブランチ構造

| ブランチ | 用途 |
|---|---|
| `main` | **リリース版**。出展で使う安定版だけがマージされる |
| `develop` | **開発本流**。feature ブランチのマージ先（デフォルトブランチ）|
| `<issue>-<短い説明>` | **個別作業**（例：`8-yolo-setup`、`12-tk-skeleton`）|

通常フロー：

```
<issue>-* ── PR ──→ develop ── (マイルストーン到達時) ──→ main
```

## 開発ルール

- **`main` / `develop` への直接 push は禁止**。必ず PR 経由でマージする
- PR の宛先は基本的に **`develop`**。マイルストーン (M1〜M4) 到達時のみ `develop → main`
- PR は他の担当者の approve を待ってからマージ
- ブランチ名：`<issue番号>-<短い説明>`（例：`8-yolo-setup`）
- Commit メッセージは簡潔に。日本語 OK
- 困ったら親 Issue にコメント、30 分で詰まったら相談

> 自動強制ができない（GitHub Free + Private リポの制約）ため、ルールでカバーします。リポを Public 化したら branch protection を有効にする予定。

## Scratch（drone 拡張）のセットアップ

子供が触る UI は Scratch（LLK 公式 clone + drone 拡張）。drone 拡張の改造は `okadai-dsc` に fork 済み。

- **方針：ビルドは開発機で行い、Pi には成果物（`build/`）を配って静的配信するだけ**（Pi 4台で毎回ビルドしない）。
- fork：[okadai-dsc/scratch-vm](https://github.com/okadai-dsc/scratch-vm)・[okadai-dsc/scratch-gui](https://github.com/okadai-dsc/scratch-gui) の **`drone` ブランチ**に drone 拡張が入っている。
- 拡張 ID は `webapisample`。ブロックのコマンドは tellomon の HTTP サーバ（`http://localhost:8001/`、CORS 対応済み）に一致（[../pi/tellomon/](../pi/tellomon/)）。実飛行での連携確認は別途。

### 開発機でビルド

```bash
# 1. fork の drone ブランチを clone（vm と gui を隣り合わせに置く）
git clone -b drone https://github.com/okadai-dsc/scratch-vm.git
git clone -b drone https://github.com/okadai-dsc/scratch-gui.git

# 2. node は v22 系。ビルドは openssl-legacy-provider が必要
#    （nvm 等で v22 を使用）

# 3. vm を先に用意し、gui から参照（link）できるようにする
cd scratch-vm  && npm install && npm link && cd ..
cd scratch-gui && npm install && npm link scratch-vm
#    （gui の node_modules/scratch-vm が改造版 vm を指す＝drone 拡張がバンドルに入る）

# 4. 本番バンドルをビルド
NODE_OPTIONS=--openssl-legacy-provider npm run build
#    → scratch-gui/build/ が生成される。build/lib.min.js に drone 拡張
#      （webapisample / localhost:8001 / Drone Control）が焼き込まれる
```

### Pi 配備（静的配信のみ）

```bash
# 開発機の scratch-gui/build/ を Pi にコピーして静的配信するだけ
cd build && python3 -m http.server 8601    # もしくは nginx 等
```

子供のブラウザで `http://localhost:8601/` を開き、拡張ライブラリから「Drone Control Blocks」を選ぶ。tellomon（`pi/tellomon`）を起動しておけば、ブロック実行 → `localhost:8001` 経由で Tello に届く。

> 検証メモ：node v22.22.2 + `NODE_OPTIONS=--openssl-legacy-provider` で vm / gui とも `webpack --bail` ビルド成功（2026-06-08 時点）。

## 関連ドキュメント

- システム構成：[../README.md](../README.md)
- Raspberry Pi セットアップ（Buster / armv7l troubleshooting 含む）：[raspi-setup.md](raspi-setup.md)
- 仕様詳細：[開発者補足/仕様詳細ドラフト.md](開発者補足/仕様詳細ドラフト.md)
- ポート一覧：[開発者補足/ポート一覧.md](開発者補足/ポート一覧.md)
- 開発計画（Week 単位）：[開発者補足/開発計画.md](開発者補足/開発計画.md)
