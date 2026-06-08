# 開発ガイド

## ローカル開発

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

## 関連ドキュメント

- システム構成：[../README.md](../README.md)
- 仕様詳細：[開発者補足/仕様詳細ドラフト.md](開発者補足/仕様詳細ドラフト.md)
- ポート一覧：[開発者補足/ポート一覧.md](開発者補足/ポート一覧.md)
- 開発計画（Week 単位）：[開発者補足/開発計画.md](開発者補足/開発計画.md)
