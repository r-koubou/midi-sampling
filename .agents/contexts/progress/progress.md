# 現在の状態(2026-07-28 更新)

## 現状
- `sampling_implementation.md` 実装完了(CLI `run` / `audit`)。詳細は `archives/2026-07-22-sampling-initial.md`
- `postprocess_implementation.md` 実装完了(`src/midi_sampling/postprocess/`、CLI `postprocess`)
  - `sampling_implementation.md` §23 の「ポストプロセス後の派生マニフェスト」「トリミング・ループ処理とのマニフェスト統合」を解消
  - 実装プランは `.agents/plans/postprocess.md`
- `export_implementation.md` 実装完了(`src/midi_sampling/export/`、CLI `export`)。SFZ のみ対応
  - 実装プランは `.agents/plans/2026-0728-sfz-instrument-export.md`
  - 実データでのエクスポートと Sforzando での読み込みを人間が確認済み(2026-07-28)
- `tests/` 286 件、全て成功(実デバイス不使用)

## 未完了
- `export` の UVI Falcon `*.uvip` / KONTAKT 1 `*.nki` 対応 — `abstractions/` の中間表現を共有し `<format>_impl/` と `create_patch_writer` の分岐を足す構造は用意済み
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
- 2パッケージとも PyPI 未公開のため `[tool.uv.sources]` で兄弟ディレクトリを**相対パス参照**している。**公開したらこのセクションを削除すること**
  - 他者が clone しただけでは解決できないため、README のセットアップに DSP リポジトリの clone 手順と相対パス編集の必要性を明記した
  - `wav-silence-trimmer` の clone 先ディレクトリ名は `sample-trimmer`(パッケージ名と不一致)
  - 検討したが採用しなかった代替案(2026-07-26):
    - **git submodule**: 固定コミットが submodule と `uv.lock` の二重管理になる。`git submodule update --init` の手順も増える
    - **uv の git ソース**(`{ git = "...", branch = "main" }`): 検証済みで動作し `uv.lock` が sha を固定する(`#ec8c3c9` / `#c58708d`)。clone 直後に動く利点があるが、DSP側を uv キャッシュへ clone するため **editable なローカル編集ができなくなる**。3プロジェクトを並行開発する現状を優先して見送り
    - 将来 git ソースへ移行する場合、DSP側に `v0.1.0` 等のタグを切って `tag = ` で参照するのが望ましい
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

## export 実装(2026-07-28)
ディスカッション `.agents/discussions/2026-0727-exclusive-groups-release-trigger.md` の「第3レイヤー」案を実装。仕様は `.agents/specs/export_implementation.md`。

- 人間が手書きする `instrument_definition`(instrument.yaml)が `processed/<tone>/manifest.yaml` を参照し、排他グループ・リリーストリガーを宣言する。**既存マニフェストには一切書き込まない**(ハッシュ連鎖保護)
- `sources` は postprocess_manifest **のみ**参照可(ユーザー決定)。recorded/ を使いたい場合は trim/loop なしの postprocess を一度通す
- 成果物は自己完結型: `<output>/<name>.sfz` + `samples/<tone-id>/*.wav|.flac`(tone-id サブディレクトリでファイル名衝突回避)。出力先が空でなければ `ExportExistingOutputError`
- FLAC エクスポート対応(ユーザー要望)。libsndfile 1.2.2 の FLAC は **16/24bit のみ**(実測確認)
  - int16/int24 は無劣化パススルー(int32 dtype 経由でビット単位一致、テストで検証)
  - int32/float32/float64 は `audio.bit_depth` の明示指定必須。暗黙のビット深度削減はしない
  - smpl チャンクは FLAC に引き継がれないが、ループは SFZ の `loop_start=`/`loop_end=` opcode で表現するため実害なし。エンコード後にフレーム数一致を検証(ループフレームの有効性保証)
- `loop_start`/`loop_end` はマニフェストの `start_frame`/`end_frame` をそのまま使用(smpl と SFZ はともにループ終端を「含む」)
- 排他グループは定義順に 1 始まりの整数を割当て、`group=N off_by=N off_mode=fast` に変換。`plays` 指定の音色はリリース専用(`trigger=release` + `rt_decay=`)になる
- 構造は既存規約を踏襲: `definitions/`(pydantic, extra=forbid) → `resolving/`(frozen dataclass) → `planning/` → `export_executor`、形式選択は `create_patch_writer` の明示ファクトリ、`soundfile` は関数内 lazy import
- スコープ外(仕様 §1.1): 生 opcode エスケープハッチ、連鎖トリガー、`tune=`/`volume=`、音色・サンプル単位のエンベロープ
- `examples/sessions/instrument.yaml` に楽器定義サンプル

### 実機確認後のフィードバック対応(2026-07-28)
Sforzando での読み込み確認後、3件のフィードバックを反映:
- `envelope`(パッチ全体の既定アンプエンベロープ)を定義ファイルへ追加。**単位は秒 float**(既存 timing 系と統一、SFZ/Falcon は秒ネイティブ、msec 系へは各エクスポータが変換する方針で合意)。省略時 attack: 0.0 / release: 0.3。SFZ では `<global>` の `ampeg_attack=`/`ampeg_release=` に出力
- 出力レイアウトを `<出力ルート>/<フォーマット名>/<パッチ名>/` に変更(`--output` はルート指定。既定 `patches/sfz/<name>/`)。フォーマット別ディレクトリ名は `InstrumentPatchWriter.directory_name` が返す(既定実装は `format_id`)
- `InstrumentPatchWriter` を Protocol から**抽象基底クラス**へ変更。Protocol は実装側の継承が文法上不要で、継承関係から「インターフェースを実装しているか」を判別できないため。`SfzPatchWriter` は明示継承に変更
- サンプルディレクトリ名は `Samples/`(大文字。ユーザーが SAMPLES_DIRECTORY_NAME を変更)

## 補足
- `examples/sessions/postprocess.yaml` にポストプロセス定義サンプル
- DSP結合テスト(tests/test_postprocess_stages_integration.py)は `pytest.importorskip` でガード。librosa 解析のため約70秒かかる

## 次回やること
1. (未定。Falcon/KONTAKT 対応、または `audit` のステージ対応)
