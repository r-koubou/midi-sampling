# SFZエクスポート機能（instrument_definition 第3レイヤー）実装プラン

## Context

外部MIDI音源の自動サンプリング成果物（`processed/<tone-id>/manifest.yaml` + WAV）を、サンプラーソフトウェア向けパッチとしてエクスポートする機能を新設する。初版は **Sforzando (*.sfz)** のみ。UVI Falcon (*.uvip) / KONTAKT 1 (*.nki) は将来対応とし、抽象/具象の分離だけ先に用意する。

排他グループ（ハイハットのchoke等）やリリーストリガーは録音成果物に属さない「サンプル間の関係」であるため、既存マニフェストには一切手を触れず（ハッシュ連鎖 `resolved_definition_sha256` / `source_manifest_sha256` が壊れるため厳禁）、人間が手書きする **第3レイヤー `instrument_definition`（instrument.yaml）** で表現する。設計根拠は `.agents/discussions/2026-0727-exclusive-groups-release-trigger.md`。

### ユーザーとの確定事項

| 論点 | 決定 |
|---|---|
| sources の参照先 | **processed/ の postprocess_manifest のみ**（recorded/ 直接参照は不可） |
| 初版スコープ | region マッピング＋ループポイント＋**exclusive_groups**＋**release_triggers**。生opcodeエスケープハッチは対象外 |
| 成果物構成 | **自己完結型**: 出力ディレクトリへ .sfz とオーディオ一式をコピー |
| オーディオ形式 | 定義ファイルで **wav / flac** を選択可能。FLACはロスレスでフレーム位置不変のためループポイントは `.sfz` の `loop_start=`/`loop_end=` opcodeで正しく機能する（smplチャンクは失われるがSFZ再生には不要）。libsndfile 1.2.2 のFLACは int16/int24 のみ対応（実測確認済み）のため、float32/int32 ソースは `bit_depth` 明示時のみ変換、未指定はエラー |

## 設計

既存の縦割りパターン（`definitions/`(pydantic) → `resolving/`(frozen dataclass) → `planning/` → 実行 → 出力）と `devices` の abstractions/impl 分離、`postprocess/stages/__init__.py` の明示ファクトリを踏襲する。

```
src/midi_sampling/export/
├── exceptions.py            ExportError(MidiSamplingError), ExportDefinitionError など
├── definitions/
│   ├── instrument_definition.py   InstrumentDefinition (pydantic)
│   └── field_types.py             必要なら sampling/definitions/field_types.py の型を再利用
├── resolving/
│   └── export_resolver.py         ExportResolver → ResolvedInstrument (frozen dataclass)
├── planning/
│   └── export_plan_builder.py     ExportPlanBuilder → ExportPlan
├── abstractions/
│   ├── instrument_patch_writer.py InstrumentPatchWriter (Protocol): format_id / write(context) → outcome
│   └── instrument_model.py        サンプラー非依存中間表現: Instrument / ExclusiveGroup / ReleaseLink / Region (frozen dataclass)
├── audio/
│   └── audio_exporter.py          WAVコピー / FLACエンコード（soundfile使用、bit_depth検証）
└── sfz_impl/
    └── sfz_patch_writer.py        SfzPatchWriter
```

### instrument_definition スキーマ（v1）

pydantic、`extra="forbid"`、先頭は `schema_version: Literal[1]` / `kind: Literal["instrument_definition"]`（リポジトリ規約どおり）。

```yaml
schema_version: 1
kind: instrument_definition
name: sc8850-drums          # パッチ名（出力ファイル名の基礎）

audio:
  format: flac              # wav | flac（省略時 wav）
  bit_depth: 24             # 省略可。flac かつソースが float32/int32 のときは必須（16|24）

sources:
  - tone: sc8850-drums-1    # definition.id と一致検証する参照名
    manifest: processed/sc8850-drums-1/manifest.yaml   # instrument.yaml からの相対パス

exclusive_groups:
  - name: hihat
    members:
      - { tone: sc8850-drums-1, root_note: 42 }   # root_note 省略時は tone 全region
      - { tone: sc8850-drums-1, root_note: 46 }

release_triggers:
  - trigger_of: { tone: gtr-sustain }
    plays:      { tone: gtr-fret-noise }
    rt_decay: 6.0           # 省略可 (dB/sec)
```

- パス検証は `PostprocessResolver._reject_unsupported_reference` と同等ルール（相対のみ、`~`/絶対/glob拒否）を再利用または同型実装。
- resolver は `PostprocessManifestRepository` で各マニフェストを読み込み、`kind: postprocess_manifest`・`status: completed`・参照 `tone`/`root_note` の実在・tone 重複などを検証（`@model_validator` ＋ resolver の2段構え）。

### 中間表現 → SFZ マッピング

| 中間表現 | SFZ |
|---|---|
| Region(sample, key_low/root/high, vel_low/high) | `sample=` `lokey=` `pitch_keycenter=` `hikey=` `lovel=` `hivel=` |
| loop.applied && status==success | `loop_mode=loop_continuous loop_start= loop_end=` |
| ループなし | `loop_mode=no_loop` |
| ExclusiveGroup（連番intを割当） | メンバー全regionに `group=N off_by=N off_mode=fast` |
| ReleaseLink | plays 側 tone の全regionに `trigger=release`（＋`rt_decay=`） |

出力レイアウト（自己完結型）:

```
<output-dir>/
├── <name>.sfz              # <control> default_path=samples/ を使用
└── samples/<tone-id>/<元ファイル名>.wav|.flac   # tone-idサブディレクトリでファイル名衝突を回避
```

ファイル名逆解析はしない（マッピングは全てマニフェストの `mapping` から取得。サンプリング仕様 §24 遵守）。

### CLI

`src/midi_sampling/cli.py` に `@app.command() def export(...)` を追加（`postprocess` コマンド cli.py:140-175 が雛形）。

- `midi-sampling export <instrument.yaml> --format sfz --output <dir>`（`--format` 省略時 sfz、`--output` 省略時 `patches/<name>/`）
- 重い依存は関数内 lazy import、例外は `MidiSamplingError` 捕捉で既存 exit code 規約（`EXIT_DEFINITION_ERROR=2` 等）に従う。
- フォーマット選択は `postprocess/stages/__init__.py::create_stage` に倣った明示ファクトリ `create_patch_writer(format)` で行う。

## タスクリスト

- [x] AGENTS.md 規約に従い本プランを `.agents/plans/2026-0728-sfz-instrument-export.md` へ書き出し
- [x] 仕様書 `.agents/specs/export_implementation.md` を新規作成（スキーマ定義・SFZマッピング表・FLAC制約を明文化）
- [x] `export/exceptions.py` + `definitions/`（InstrumentDefinition、バリデーション）
- [x] `resolving/`（ExportResolver、postprocess_manifest 読み込み・整合検証、frozen dataclass化）
- [x] `abstractions/`（Instrument/Region 中間表現、InstrumentPatchWriter Protocol）
- [x] `planning/`（ExportPlanBuilder: region展開、グループint割当、release関係解決、audio変換タスク列挙）
- [x] `audio/audio_exporter.py`（WAVコピー / FLACエンコード、bit_depth検証、フレーム数一致の検証）
- [x] `sfz_impl/sfz_patch_writer.py`（.sfz テキスト生成）
- [x] CLI `export` コマンド追加＋明示ファクトリ
- [x] テスト（下記）
- [x] `.agents/contexts/progress/progress.md` へ実行記録を追記
- [x] 実データの `processed/` からパッチを生成し、Sforzando で読み込みを人間が確認（2026-07-28。フィードバック3件は envelope 追加・出力レイアウト変更・Writer の ABC 化として反映済み）

## テスト・検証

`tests/` フラット配置・`conftest.py` 集約の既存規約に従う。

- `tests/test_export_definitions.py` — スキーマ検証（不正kind、extra key拒否、flac×float32でbit_depth未指定エラー等）
- `tests/test_export_resolver.py` — マニフェスト参照解決、存在しない tone/root_note、status未完了の拒否
- `tests/test_export_sfz_writer.py` — 中間表現→.sfzテキストのゴールデン比較（choke opcode、trigger=release、loop opcode含む）
- `tests/test_export_audio.py` — FLACエンコード後のフレーム数・PCM内容一致（soundfileでラウンドトリップ検証）
- `tests/test_export_cli.py` — `CliRunner` で exit code / `--help` 掲載確認
- conftest に processed ツリー生成ヘルパ（既存 `make_recorded_output()` に倣う `make_processed_output()`）を追加
- 最終確認: 実データの `processed/` からパッチを生成し、Sforzando で発音・choke・ループを人間が確認（自動化不可のため手動手順としてプランに残す）

## 懸念点・設計方針メモ

- リリース長 `timing.release_capture` は postprocess_manifest に引き継がれないため、`ampeg_release` 等のエンベロープ出力は初版対象外（サンプル自体が自然リリースを含むため実害小）。
- `tune=` / `volume=`（チューニング補正・音量正規化）はマニフェストに測定値が存在しないため初版対象外。
- 生opcodeエスケープハッチ・連鎖トリガー(b)は対象外（ディスカッション決定事項どおり）。将来 Falcon/KONTAKT 追加時は `abstractions/` の中間表現を共有し `<format>_impl/` を追加するだけで済む構造とする。
