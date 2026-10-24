# DSP パッケージの uv workspace 統合

## 全体のゴール

別リポジトリで開発していた `sample-loop-detector` と `wav-silence-trimmer`(リポジトリ名 `sample-trimmer`) を
midi-sampling リポジトリへ取り込み、**uv workspace のメンバー**として管理する。

- `[tool.uv.sources]` の相対パス参照(`../...`)や git submodule をやめ、`{ workspace = true }` で解決する
- これにより Renovate がリポジトリ単体で `uv.lock` を更新できるようにする(相対パス参照によるエラーを根本解消)
- パッケージとしての独立性(import 名、optional extra `postprocess`、遅延 import 境界、品質ゲート)は維持する

## 構成

```text
midi-sampling/
├─ pyproject.toml            # [tool.uv.workspace] members = ["packages/*"]
├─ uv.lock                   # workspace 全体で1つ
├─ src/midi_sampling/
└─ packages/
   ├─ sample-loop-detector/
   └─ wav-silence-trimmer/   # ディレクトリ名はパッケージ名に合わせる(旧リポジトリ名 sample-trimmer との不一致を解消)
```

## タスクリスト

- [x] 2リポジトリを `packages/` 配下へ取り込む(`git subtree add` で履歴保持)
- [x] メンバー側の重複・不要ファイルを整理
  - 削除: `uv.lock`(workspace ルートに一本化)、`renovate.json`、`.python-version`、`.prototools`、`.coverage`(誤コミット)、`.claude/settings.json`
  - 維持: `pyproject.toml`、`src/`、`tests/`、`README.md`、`LICENSE`、`NOTICE.md`、`AGENTS.md`/`CLAUDE.md`/`.agents/`(パッケージ固有の仕様・経緯)、`.editorconfig`/`.gitignore`
- [x] ルート `pyproject.toml` に `[tool.uv.workspace]` を追加し、`[tool.uv.sources]` を `{ workspace = true }` へ
- [x] `uv lock` / `uv sync --extra postprocess` が通ること
- [x] テスト
  - [x] midi-sampling: `uv run --extra postprocess pytest`
  - [x] sample-loop-detector: pytest / ruff / mypy strict / coverage 85%
    - mypy は統合前から py.typed 不在で失敗していたため `mypy_path = "src"` を追加。ruff 0.17 が `.agents/` の Markdown を整形対象にしたため `extend-exclude` を追加
  - [x] wav-silence-trimmer: pytest
- [x] ドキュメント更新: README(セットアップ・構成)、`.agents/contexts/progress/progress.md`、`pyproject.toml` コメント、`.agents/specs/postprocess_implementation.md` の参照箇所
- [ ] 旧リポジトリの扱い(archive・移転案内)は人間が判断する。本作業では触らない

## 懸念点・設計方針

- **境界は維持する**: midi-sampling から DSP への依存は `postprocess/stages/` 内の遅延 import のみ、という方針は変えない。統合はリポジトリ単位の話で、パッケージ境界は変えない
- **optional extra は残す**: librosa/numba が重く `<3.14` を要求するため、サンプリングのみの利用者には入れない
- **メンバーのテストは個別に実行**: 各メンバーが `tests/conftest.py` を持つため、ルートの pytest(`testpaths = ["tests"]`) には混ぜない
- **メンバーの dev 依存**: ルートの `uv sync` ではメンバーの dev グループ(mypy, ruff, pytest-cov)は入らない。`uv run --package <name>` で実行する
- **ビルドバックエンドの不統一**(trimmer は hatchling): workspace はメンバーごとのバックエンドを許容するので今回は揃えない
- **`requires-python`**: workspace は全メンバーの積集合で解決される。`>=3.12,<3.14` で現状と変わらない
- 方法B(midi_sampling パッケージへの完全取り込み)は今回は行わない。必要になれば同一リポジトリ内のディレクトリ移動で移行できる
