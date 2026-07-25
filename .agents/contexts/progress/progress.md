# 現在の状態(2026-07-26 更新)

## 現状
- `sampling_implementation.md` 実装完了(CLI `run` / `audit`)。詳細は `archives/2026-07-22-sampling-initial.md`
- `postprocess_implementation.md` 実装完了(`src/midi_sampling/postprocess/`、CLI `postprocess`)
  - `sampling_implementation.md` §23 の「ポストプロセス後の派生マニフェスト」「トリミング・ループ処理とのマニフェスト統合」を解消
  - 実装プランは `.agents/plans/postprocess.md`
- `tests/` 221 件、全て成功(実デバイス不使用)

## 未完了
- `export`(KONTAKT `*.nki` / SFZ / UVI Falcon `*.uvip` 生成) — 未着手。置き場所も未決定
- `audit` のポストプロセスステージ対応 — 派生マニフェストは3種ハッシュを持つので判定は実装可能な状態

## 重要な判断・制約(なぜそうなっているか)
- 波形処理は取り込まず、別リポジトリの汎用WAVライブラリへ optional extra で依存する。境界は「サンプリング vs ポストプロセス」ではなく「純粋DSPライブラリ vs ワークフロー」。DSP側の単体リリースと独自品質ゲート(loop-detector は mypy strict / coverage 85%)を保つため
  - `wav-silence-trimmer`(../sample-trimmer)、`sample-loop-detector`(../sample-loop-detector)
- **中間ファイルに `.wav.part` を使わない**。`.work/` 配下に置き必ず `.wav` 拡張子とする
  - libsndfile は書込時に拡張子でフォーマット推定するため。サンプリング側で実際に踏んだ罠を設計で回避する
  - `.part.wav` も不可。残骸が通常のWAVとして glob に拾われ §14 の意図を壊す
  - `StageContext.validate()` が入出力パスの `.wav` を強制し、テストでも検証
- DSPパッケージの import は `postprocess/stages/` 配下の**関数内**に限定。未導入時は `PostprocessDependencyError` で `pip install 'midi-sampling[postprocess]'` を案内
- ステージ設定は明示フィールドで写経し `dict` 素通しをしない。未知キーがサイレントに無視されるのを防ぐため
- `midi_unity_note: from_manifest` が統合の核。`mapping.root_note` が既知なので音高推定のオクターブ誤りが構造的に起きない
- 派生マニフェストは3種ハッシュを持つ: `source_manifest_sha256` / `resolved_definition_sha256` / `postprocess_settings_sha256`。将来の audit が `source_changed` と `settings_changed` を判別できる
- `mapping` は source からコピーしファイル名から逆解析しない。パッチ生成が派生マニフェスト1枚で完結する
- `source` ディレクトリは読むだけ。resolver / executor いずれも書き込まない(テストでバイト列比較して検証)
- `MidiSamplingError` を全体の基底とし `SamplingError` / `PostprocessError` をその派生に。CLI は `MidiSamplingError` を捕捉
- アトミック YAML 読み書きは `YamlDocumentRepository` へ汎用化し、sample / postprocess 両マニフェストで共有

## Python バージョン・依存の制約(2026-07-26)
- `requires-python` を `>=3.14` → **`>=3.12,<3.14`** へ降格。`.python-version` も 3.13 へ
  - `sample-loop-detector` が librosa/numba 経由で `<3.14` を要求し積集合が空だったため
  - `src/` に 3.14 固有構文は無し。3.13.9 で既存134件が全て成功することを確認済み
- `soundfile` は3プロジェクトとも **`>=0.14`** に統一済み(2026-07-26)
  - 当初 loop-detector が `>=0.13,<0.14` を要求し解決不能だったが、DSP側の上限を外して解消した
- 2パッケージとも PyPI 未公開のため `[tool.uv.sources]` で兄弟ディレクトリをパス参照している。**公開したらこのセクションを削除すること**(現状、他者が clone しても解決できない)
- **`[tool.uv.sources]` は取得元を教えるだけで、インストールはしない。** optional extra なので明示指定が必要:
  - `uv sync --extra postprocess`(素の `uv sync` は extra を入れず、既に入っていれば**削除**する)
  - 単発なら `uv run --extra postprocess midi-sampling postprocess <yaml>`
  - uv 0.11.32 時点で `[tool.uv] default-extras` は未対応(`default-groups` のみ)。extra を dependency-group へ移せば自動化できるが、group は PEP 735 の開発用メタデータでビルド成果物に入らず `pip install 'midi-sampling[postprocess]'` が成立しなくなるため採用しない

## postprocess end-to-end 検証(2026-07-26)
実WAV(正弦波 + 前後無音、PCM_24/48kHz/2ch)を録音成果物として生成し CLI で検証:
- trim → loop を4サンプルへ適用し exit 0
- 生成WAVの `smpl` チャンクの unity note が `mapping.root_note` と一致(38 / 43)
- PCM_24 / 48kHz / 2ch が保持され、`.work/` は成功時に削除される
- `recorded/` 全ファイルのSHA-256が実行前後で不変
- 2回目の実行は `ExistingOutputError` で停止し3種ハッシュの比較を表示して exit 1

## 補足
- `examples/sessions/postprocess.yaml` にポストプロセス定義サンプル
- DSP結合テスト(tests/test_postprocess_stages_integration.py)は `pytest.importorskip` でガード。librosa 解析のため約70秒かかる

## 次回やること
1. (未定。`export` ステージ、または `audit` のステージ対応)
