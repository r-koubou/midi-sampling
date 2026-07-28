# エクスポート（サンプラーパッチ生成）実装仕様

- 関連プラン: `.agents/plans/2026-0728-sfz-instrument-export.md`
- 関連ディスカッション: `.agents/discussions/2026-0727-exclusive-groups-release-trigger.md`
- 関連仕様: `.agents/specs/sampling_implementation.md`、`.agents/specs/postprocess_implementation.md`

---

## 1. 目的とスコープ

ポストプロセス済みのサンプリング成果物（`processed/<tone-id>/manifest.yaml` と処理済み WAV）を、サンプラーソフトウェア向けパッチとしてエクスポートする。

- 初版の対応形式は **SFZ（Sforzando / ARIA）のみ**。UVI Falcon (*.uvip) / KONTAKT 1 (*.nki) は将来対応とし、抽象と具象を分離した構造だけを先に用意する。
- サンプル間の関係（排他グループ・リリーストリガー）は、人間が手書きする**第3レイヤー定義ファイル `instrument_definition`** で表現する。

### 1.1 スコープ外（初版）

- 生 opcode のエスケープハッチ（形式固有記述の埋め込み）
- サンプル終端を契機とする連鎖トリガー（ディスカッション §6(b) の決定どおり恒久的にスコープ外）
- `tune=` / `volume=`（チューニング補正・音量正規化。マニフェストに測定値が存在しない）
- 音色・サンプル単位のエンベロープ出力（`timing.release_capture` は postprocess_manifest に引き継がれない）。パッチ全体の既定エンベロープは §3 の `envelope` で対応する

## 2. 不変条件

1. **既存マニフェストには一切書き込まない。** `resolved_definition_sha256` / `source_manifest_sha256` のハッシュ連鎖を壊すため（ディスカッション §3）。エクスポートは recorded/ ・ processed/ に対して完全に read-only。
2. **ファイル名の逆解析をしない。** マッピングは全て postprocess_manifest の `samples[].mapping` から取得する（サンプリング仕様 §24、ポストプロセス仕様の派生マニフェスト単独復元原則）。
3. **`sources` が参照できるのは postprocess_manifest のみ。** recorded/ の sample_manifest 直接参照は不可。postprocess を経ていない音色をエクスポートしたい場合は、trim/loop なしの postprocess を一度通す。
4. 既存のエクスポート成果物は自動で上書き・削除・再開しない（postprocess と同じ原則）。出力ディレクトリが空でない場合はエラー。

## 3. instrument_definition スキーマ (schema_version: 1)

人間が手書きする唯一のエクスポート入力。pydantic で検証し、`extra="forbid"`。

```yaml
schema_version: 1
kind: instrument_definition

name: sc8850-drums          # パッチ名。出力ファイル名・既定出力ディレクトリ名の基礎

audio:                      # 省略可。省略時は format: wav
  format: flac              # wav | flac
  bit_depth: 24             # 省略可 (16 | 24)。format: flac の場合のみ指定可

envelope:                   # 省略可。パッチ全体の既定アンプエンベロープ（秒、非負）
  attack: 0.0               # 省略時 0.0
  release: 0.3              # 省略時 0.3

sources:                    # 1件以上
  - tone: sc8850-drums-1    # マニフェストの definition.id と一致していることを検証
    manifest: processed/sc8850-drums-1/manifest.yaml   # この定義ファイルからの相対パス

exclusive_groups:           # 省略可
  - name: hihat
    members:                # 2件以上
      - { tone: sc8850-drums-1, root_note: 42 }   # root_note 省略時は tone の全 region
      - { tone: sc8850-drums-1, root_note: 46 }

release_triggers:           # 省略可
  - trigger_of: { tone: gtr-sustain }
    plays:      { tone: gtr-fret-noise }
    rt_decay: 6.0           # 省略可。dB/秒、非負
```

### 3.1 検証規則（モデルバリデータ）

- `name` は空でなく、ファイル名に使えない文字（`\ / : * ? " < > |`）を含まない。
- `sources` 内の `tone` 重複禁止。
- `exclusive_groups` の `name` 重複禁止。同一グループ内の `(tone, root_note)` 重複禁止。members は2件以上。
- `exclusive_groups` / `release_triggers` が参照する `tone` は `sources` で宣言済みであること。
- `release_triggers`: `trigger_of.tone != plays.tone`。同じ tone を複数の `plays` に指定禁止。同じ tone を `plays` と `trigger_of` の両方に指定禁止。
- `audio.bit_depth` は `format: flac` の場合のみ指定可。
- `envelope.attack` / `envelope.release` は非負の有限値（秒）。単位はプロジェクト全体の時間表現（`timing.note_on` 等）と同じく秒 float に統一する。msec 系フォーマット（KONTAKT 等）への変換は各エクスポータが行う。
- パス参照はサンプリング定義と同じ規則: 相対パスのみ。URL・`~`・glob・絶対パス拒否。

### 3.2 リゾルバによる検証（マニフェスト読み込み後）

- マニフェストの `kind` は `postprocess_manifest`（リポジトリのスキーマ検証で担保）。
- `definition.id` == `sources[].tone`。
- tone / 各サンプルの `status` が `completed`。
- 全サンプルのオーディオファイルがマニフェストと同じディレクトリに実在。
- `exclusive_groups` の `root_note` は対象 tone のいずれかのサンプルの `mapping.root_note` に実在。
- 1つの region が複数の排他グループに属さないこと（プランニング時に検証）。
- 複数の `sources` が同一マニフェスト（解決後パス）を指していないこと。
- FLAC 選択時のビット深度制約（§5）。

## 4. モジュール構成

既存の縦割り（definitions → resolving → planning → 実行）と `devices` の抽象/実装分離、`postprocess/stages` の明示ファクトリを踏襲する。

```
src/midi_sampling/export/
├── __init__.py              create_patch_writer(format) 明示ファクトリ
├── exceptions.py            ExportError(MidiSamplingError) 階層
├── definitions/             InstrumentDefinition (pydantic)
├── resolving/               ExportResolver → ResolvedInstrument (frozen dataclass)
├── planning/                ExportPlanBuilder → ExportPlan
├── abstractions/            サンプラー非依存中間表現 (InstrumentModel / InstrumentRegion)
│                            InstrumentPatchWriter (抽象基底クラス)
├── audio/                   AudioExporter (WAVコピー / FLACエンコード)
├── sfz_impl/                SfzPatchWriter
└── export_executor.py       ExportExecutor（オーディオ出力 → パッチ書き出し）
```

- 中間表現 `InstrumentModel` は形式非依存。将来の Falcon / KONTAKT 対応は `<format>_impl/` の追加と `create_patch_writer` への分岐追加だけで済む構造とする。
- `InstrumentPatchWriter` は Protocol ではなく**抽象基底クラス**とする。Python の Protocol は実装側の継承が文法上不要なため、「インターフェースを実装しているか」を継承関係で判別できない。形式の実装は明示的な継承で表明する。
  - 抽象プロパティ `format_id`（CLI `--format` / ファクトリの識別子）と抽象メソッド `write()` を持つ。
  - プロパティ `directory_name` は出力レイアウト `<出力ルート>/<directory_name>/<パッチ名>/` のフォーマット別サブディレクトリ名を返す。既定実装は `format_id` を返し、慣習的なディレクトリ名が識別子と異なるフォーマットのみオーバーライドする。
- `soundfile` の import は AudioExporter の関数内 lazy import に閉じる。

## 5. オーディオ出力

定義ファイルの `audio.format` で選択。出力は常にサンプルごとに `Samples/<tone-id>/<元ファイル名>.<ext>` へ書き出す（tone-id サブディレクトリでファイル名衝突を回避）。

### 5.1 wav（既定）

バイト単位のコピー（`shutil.copyfile`）。loop ステージが埋め込んだ `smpl` チャンクもそのまま保持される。

### 5.2 flac

- libsndfile 1.2.2 の FLAC 書き込みは **PCM 16/24bit のみ**（実測確認済み）。
- ソース `audio.data_format` ごとの規則:
  - `int16` → 省略時 16bit パススルー（ロスレス）
  - `int24` → 省略時 24bit パススルー（ロスレス）
  - `int32` / `float32` / `float64` → `audio.bit_depth`（16 or 24）の明示指定が必須。未指定はエラー（暗黙のビット深度削減をしない）
- 整数系ソースは int32 dtype で読み書きし、パススルー時はビット単位で無劣化。浮動小数系は [-1.0, 1.0] へクリップ後に変換。
- エンコード後にフレーム数の一致を検証する。**FLAC はロスレスでフレーム位置が不変**のため、マニフェストのループフレームはそのまま有効。
- `smpl` チャンクは FLAC には引き継がれないが、ループ情報は SFZ 側に opcode として書き出すため実害はない（ディスカッションで合意済み）。

## 6. 中間表現 → SFZ マッピング

出力は `<出力ディレクトリ>/<name>.sfz`（UTF-8、LF）。`sample=` は .sfz からの相対パス（`Samples/<tone-id>/...`、POSIX 区切り）。

| 中間表現 | SFZ opcode |
|---|---|
| envelope (attack / release、秒) | `<global>` に `ampeg_attack=` `ampeg_release=`（SFZ は秒単位ネイティブのため変換不要） |
| mapping (key_low / root_note / key_high) | `lokey=` `pitch_keycenter=` `hikey=` |
| mapping (velocity_low / velocity_high) | `lovel=` `hivel=` |
| loop（applied かつ status: success かつ start/end あり） | `loop_mode=loop_continuous loop_start= loop_end=` |
| ループなし | `loop_mode=no_loop` |
| 排他グループ（定義順に 1 からの整数を割当） | メンバー全 region に `group=N off_by=N off_mode=fast` |
| release_triggers の plays 側 tone の全 region | `trigger=release`（＋指定時 `rt_decay=`） |

- `loop_start` / `loop_end` はマニフェストの `start_frame` / `end_frame` をそのまま使用する。これらは loop ステージが `smpl` チャンクへ書いた値と同一であり、`smpl` と SFZ はともにループ終端を「含む」フレーム番号として扱うため変換不要。
- `plays` に指定された tone は release 専用となり、attack region としては出力されない。
- ノート番号は整数の MIDI ノート番号で出力する（オクターブ表記はソフトウェア間で非互換のため使わない）。

## 7. CLI

```
midi-sampling export <instrument.yaml> [--format sfz] [--output <root>]
```

- `--format` 省略時は `sfz`。未知の形式は定義エラー扱い。
- パッチの出力先は常に `<出力ルート>/<フォーマット別ディレクトリ名>/<name>/`（例: `patches/sfz/sc8850-cello/`）。フォーマット別ディレクトリ名は Writer の `directory_name`（§4）が決める。
- `--output` は出力ルートを差し替える。省略時のルートは `<instrument.yaml のあるディレクトリ>/patches/`。
- 出力ディレクトリ（`<name>/` 階層）が存在して空でない場合はエラー（§2-4）。
- 終了コードは既存規約: 成功 0 / 実行失敗 1 / 定義・入力エラー 2。
- 例外は `MidiSamplingError` を CLI が捕捉する既存方式（`export/exceptions.py` は全て `ExportError(MidiSamplingError)` 派生）。

## 8. 将来拡張のための注記

- UVI Falcon / KONTAKT 対応時は `InstrumentModel` を共有し、`<format>_impl/` と `create_patch_writer` の分岐を追加する。
- 排他グループは中間表現では「整数 ID＋名前」であり、Falcon の mute group / KONTAKT の Voice Group へも素直に写像できる。
- 形式固有のエスケープハッチを導入する場合は instrument_definition に形式名を key とするセクションを追加する方針（初版では未実装）。
