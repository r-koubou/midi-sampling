# MIDI Sampling ポストプロセス実装仕様書

- 対象リポジトリ: `r-koubou/midi-sampling`
- 実装対象ディレクトリ: `src/midi_sampling/postprocess`
- 仕様バージョン: 1
- 文書作成日: 2026-07-26
- 状態: 初期実装向け確定仕様
- 関連仕様: `sampling_implementation.md`(以下、本文書では「サンプリング仕様」と呼ぶ)

---

## 1. 目的

サンプリング仕様 §23 で将来対応としていた以下を実装する。

- ポストプロセス後の派生マニフェスト
- トリミング・ループ処理とのマニフェスト統合

本仕様の責務は以下とする。

1. ポストプロセスセッション定義(YAML)を読み込む。
2. 既存のサンプリング成果物(`sample_manifest` と WAV)を入力として解決する。
3. トリミング、ループ点検出、`smpl` チャンク埋め込みを規定順で適用する。
4. 派生マニフェスト(`postprocess_manifest`)を自動生成・更新する。

KONTAKT `*.nki`、SFZ、UVI Falcon `*.uvip` の生成処理は本仕様の対象外とする。ただし、パッチ生成ツールが**派生マニフェスト1枚だけ**でマッピングを再構築できることを必須とする。

---

## 2. 技術選定

### 2.1 責務の分割方針

波形処理アルゴリズムは本リポジトリへ取り込まない。境界は「純粋DSPライブラリ」と「ワークフロー」の間に置く。

| | 責務 |
|---|---|
| `wav-silence-trimmer` / `sample-loop-detector` | WAVファイル単位の純粋な波形処理。YAML・マニフェスト・MIDIを知らない |
| `midi-sampling` | 定義解決・計画・録音・**ポストプロセスの適用**・マニフェスト連鎖 |

この分割により、DSP側は単体でリリース・テスト可能なまま維持され、本リポジトリが増やす責務はオーケストレーションと契約のみとなる。

### 2.2 使用ライブラリ

optional extra `postprocess` として以下へ依存する。

- `wav-silence-trimmer`
  - トリミング(無音区間検出、フェード)に使用する。
- `sample-loop-detector`
  - サステインループ点検出、`smpl` チャンク生成・埋め込みに使用する。

既存依存(`pydantic`、`PyYAML`、`typer`)はサンプリング仕様と同じ方針で使用する。

### 2.3 Pythonバージョン

`sample-loop-detector` が librosa 経由で `<3.14` を要求するため、`requires-python` を `>=3.12,<3.14` とする。librosa が 3.14 へ対応した時点で引き上げる。

---

## 3. アーキテクチャ

```text
postprocess_session.yaml
  ↓
YamlDefinitionLoader(既存を再利用)
  ↓
PostprocessSessionDefinition(Pydantic)
  ↓
PostprocessResolver
  ├─ source の sample_manifest 群を読む(読み取り専用)
  ↓
ResolvedPostprocessSession
  ↓
PostprocessPlanBuilder
  ↓
PostprocessPlan
  ↓
PostprocessExecutor
  └─ PostprocessStage(TrimStage / LoopStage)
```

### 3.1 責務境界

#### PostprocessResolver

- 相対パスを解決する。
- source ディレクトリ配下の音色ディレクトリと `manifest.yaml` を読む。
- source マニフェストの `status` が `completed` であることを検証する。
- ファイルを一切変更しない。

#### PostprocessPlanBuilder

- source マニフェストの `samples` から処理対象を全件生成する。
- 出力パスと中間ファイルパスを全件生成する。
- 実行前フェイルセーフ検証を行う。
- 設定ハッシュ算出対象となる正規化データを構築する。

#### PostprocessStage

- DSPパッケージへの唯一の接点。
- 1本のWAVを受け取り、1本のWAVを書き出す。
- 派生マニフェストへ記録する情報を返す。

#### PostprocessExecutor

- YAML、Pydanticモデル、外部参照を扱わない。
- 解決・検証済みの `PostprocessPlan` のみを受け取る。
- source 成果物を一切変更しない。
- WAVと派生マニフェストをアトミックに更新する。

---

## 4. 出力レイアウトと不変条件

```text
recorded/<tone-id>/manifest.yaml     kind: sample_manifest        ← run が生成。以後不変
        │
        ↓ postprocess
processed/<tone-id>/                 ← 派生成果物
        ├─ .work/                    ← ステージ間中間ファイル
        ├─ *.wav
        └─ manifest.yaml             kind: postprocess_manifest
```

### 4.1 絶対の不変条件

- source ディレクトリ(`recorded/`)を書き換えない。in-place 処理を禁止する。
- WAVファイル名は source からそのまま引き継ぐ。source サンプルと出力WAVは 1:1 に対応する。
- `mapping` は source マニフェストからコピーする。ファイル名からマッピング情報を逆解析しない。
- 既存の出力音色ディレクトリが存在した場合はエラーとする。自動上書き・自動削除・自動再開を行わない。

録音は実時間・ハードウェア占有で長時間を要するのに対し、トリム閾値やループ検出の調整は反復的に行われる。この非対称性がステージを分離する実務上の根拠である。

---

## 5. ポストプロセスセッション定義

### 5.1 基本形式

```yaml
schema_version: 1
kind: postprocess_session

source:
  directory: recorded

output:
  directory: processed

stages:
  - kind: trim
    settings:
      on_margin_db: 15.0
      off_margin_db: 8.0
      pre_roll_ms: 8.0
      post_roll_ms: 40.0
      fade_in_ms: 1.0
      fade_out_ms: 5.0

  - kind: loop
    on_failure: skip
    settings:
      min_loop: 0.3
      max_loop: 8.0
      quality_threshold: 0.6
      crossfade_lengths_ms: [10.0, 25.0, 50.0]
      midi_unity_note: from_manifest
      replace_existing_loop: false

tones:
  - sc8850-cello-1
```

### 5.2 共通事項

- `schema_version` と `kind` を必須とする。
- 全モデルで未知フィールドを拒否する(`ConfigDict(extra="forbid")`)。
- 相対パスは常に、参照を記述したYAMLファイルの所在ディレクトリを基準とする。
- サンプリング仕様 §9.2 の禁止事項(URL参照、絶対パス、`~` 展開、環境変数展開、glob、YAMLカスタムタグ)を継承する。

### 5.3 `source` / `output`

| フィールド | 型 | 必須 | 意味 |
|---|---:|---:|---|
| `source.directory` | str | Yes | サンプリングセッションの `output.directory` と同じ場所 |
| `output.directory` | str | Yes | 派生成果物の出力先。`source.directory` と同一であってはならない |

### 5.4 `tones`

- 省略時は `source.directory` 直下の全音色ディレクトリを対象とする。
- 明示した場合、その音色が source に存在しなければエラーとする。
- 記述順には依存しない。音色IDの昇順で処理する。

### 5.5 `stages`

- 1件以上を必須とする。
- 記述順に適用する。
- 同じ `kind` を複数回記述してはならない。
- `kind` は `trim` または `loop` のみ許可する。

DSP側の設定は将来増える可能性があるため、`settings` は **明示フィールドで定義する**。`dict` の素通しを禁止する。未知キーがサイレントに無視されることを防ぐためである。

### 5.6 `trim` ステージ設定

`wav_silence_trimmer.models.TrimConfig` に1:1で対応する。省略したフィールドはDSP側のデフォルト値を使用する。

| フィールド | 型 | 意味 |
|---|---:|---|
| `edge_noise_seconds` | float | ノイズフロア推定に使う両端の秒数 |
| `frame_ms` | float | 解析フレーム長 |
| `hop_ms` | float | 解析ホップ長 |
| `noise_percentile` | float | ノイズフロア推定のパーセンタイル |
| `on_margin_db` | float | 立ち上がり判定マージン |
| `off_margin_db` | float | 立ち下がり判定マージン |
| `minimum_noise_floor_dbfs` | float | ノイズフロアの下限 |
| `minimum_on_ms` | float | 有音とみなす最小継続長 |
| `bridge_gap_ms` | float | 有音区間を橋渡しする最大無音長 |
| `pre_roll_ms` | float | 検出開始点の手前に残す余白 |
| `post_roll_ms` | float | 検出終了点の後ろに残す余白 |
| `fade_in_ms` | float | フェードイン長 |
| `fade_out_ms` | float | フェードアウト長 |
| `no_fade` | bool | フェードを適用しない |

### 5.7 `loop` ステージ設定

`sample_loop_detector.config.DetectionSettings` のうち、入出力パスに関わらないものへ対応する。

| フィールド | 型 | 意味 |
|---|---:|---|
| `search_start` | float \| null | 探索開始秒 |
| `search_end` | float \| null | 探索終了秒 |
| `min_sustain` | float | サステイン区間の最小秒数 |
| `min_loop` | float | ループの最小秒数 |
| `max_loop` | float | ループの最大秒数 |
| `fmin` | float | 音高推定の下限周波数 |
| `fmax` | float | 音高推定の上限周波数 |
| `crossfade_lengths_ms` | list[float] | 評価するクロスフェード長 |
| `top_k` | int | 詳細評価する候補数 |
| `quality_threshold` | float | 採用する最低スコア |
| `midi_unity_note` | `from_manifest` \| `auto` \| 0-127 | 後述 |
| `replace_existing_loop` | bool | 既存 `smpl` チャンクを置換する |

`on_failure` はステージ直下に置く。

| 値 | 意味 |
|---|---|
| `skip` | ループが見つからない場合もWAVを出力し、`loop.status` に理由を記録して次のサンプルへ進む |
| `error` | ループが見つからない場合はセッション全体を停止する |

既定値は `skip` とする。ループが見つからないことは音色によっては正常な結果(打楽器、減衰音)であるためである。

#### `midi_unity_note`

| 値 | 挙動 |
|---|---|
| `from_manifest` | source マニフェストの `mapping.root_note` を使用する(既定) |
| `auto` | DSP側の音高推定に委ねる |
| 0-127 | 指定値を固定で使用する |

`from_manifest` が本統合の中核である。単体CLIでは音高推定に頼るしかないが、マニフェストには収録時のノート番号が正解として記録されているため、推定誤りを構造的に排除できる。

---

## 6. ステージ適用と中間ファイル

### 6.1 中間ファイル

```text
processed/<tone-id>/
├─ .work/
│  ├─ <name>.s1-trim.wav
│  └─ <name>.s2-loop.wav
├─ <name>.wav
└─ manifest.yaml
```

- ステージ間の中間ファイルは `.work/` 配下へ置く。
- **中間ファイルは必ず `.wav` 拡張子とする。**
- 最終WAVは、最後のステージの出力を `os.replace` で音色ディレクトリ直下へ確定させる。
- 音色の全サンプル完了後に `.work/` をベストエフォートで削除する。エラー時は残す。
- 派生マニフェストは `.work/` 配下を参照しない。

### 6.2 `.wav.part` を使用しない理由

サンプリング仕様 §14 は完成前のWAVに `.wav.part` を用いるが、ポストプロセスの中間ファイルには**この形式を使用してはならない**。

libsndfile は書き込み時に拡張子から出力フォーマットを推定するため、`.wav.part` を渡すと判別に失敗する(サンプリング初期実装で実際に発生し、`format="WAV"` の明示指定で解決した経緯がある)。

外部DSPパッケージへ渡すパスが常に `.wav` で終わることを設計として保証し、相手ライブラリの拡張子推定の実装詳細に依存しない。

拡張子を後置する `.part.wav` も採用しない。エラー時に残った中間ファイルが通常のWAVとして走査に拾われてしまい、サンプリング仕様 §14「通常のWAVとしては扱わない」の意図を損なうためである。

### 6.3 DSPパッケージのimport

- DSPパッケージの import は `postprocess/stages/` 配下のモジュールに限定する。
- 関数内での遅延importとする。
- 未インストール時は `PostprocessDependencyError` を送出し、CLIが `pip install midi-sampling[postprocess]` を案内する。

---

## 7. 実行前フェイルセーフ

最初のWAVを読み込む前に、全音色・全サンプルを検証する。

### 7.1 必須検証

- `source.directory` が存在し、ディレクトリである。
- `output.directory` が `source.directory` と同一でない。
- 対象音色の `manifest.yaml` が存在し、`kind: sample_manifest` として妥当である。
- source マニフェストの `status` が `completed` である。
- source マニフェスト記載の全WAVが実在する。
- `tones` に記述した音色が全て source に存在する。
- 出力対象の音色ディレクトリが存在しない。
- 出力ファイル名が音色ディレクトリ内で一意である。
- 生成パスが現在のOSで使用可能である(既存 `OutputPathValidator` を使用する)。
- 出力ルートの作成権限がある。
- 有効化されたステージのDSPパッケージが import 可能である。

### 7.2 既存出力

- 既存の出力音色ディレクトリが存在した場合はエラーとする。
- 自動上書き、自動削除、自動再開を行わない。
- エラー時点でプログラムを終了する。

---

## 8. 実行シーケンス

### 8.1 セッション開始

```text
定義読込
  ↓
参照解決(source マニフェスト読込)
  ↓
計画生成
  ↓
実行前フェイルセーフ検証
  ↓
DSPパッケージ import 検証
  ↓
初期マニフェスト生成(status: pending)
```

### 8.2 音色単位

```text
音色ディレクトリ作成
  ↓
.work/ 作成
  ↓
マニフェストを in_progress へ更新
  ↓
音色内の全サンプルを index 昇順で処理
  ↓
.work/ 削除(ベストエフォート)
  ↓
マニフェストを completed へ更新
```

### 8.3 サンプル単位

```text
source WAV を .work/ の入力として参照
  ↓
ステージを記述順に適用(各ステージは .work/ 内へ出力)
  ↓
最終ステージ出力を音色ディレクトリ直下へ os.replace
  ↓
マニフェストの対象サンプルを completed へ更新
```

### 8.4 エラー時

- 最初のエラーでセッション全体を停止する。
- 後続サンプルへ進まない。
- 現在の音色マニフェストを `failed` へ更新する。
- エラー情報をマニフェストへ記録する。
- 既に完成しているWAVは削除しない。
- source 成果物には一切触れない。

`loop` ステージで `on_failure: skip` の場合、ループ未検出はエラーではない。WAVを出力し `loop.status` に理由を記録して継続する。

---

## 9. 派生マニフェスト

### 9.1 生成方式

サンプリング仕様 §15.1 と同一方針とする。

- ポストプロセスプログラムが自動生成する。
- ユーザーが手書きする前提にしない。ユーザーが記述するのは §5 のセッション定義のみ。
- 全事前検証成功後、最初のWAVを処理する前に初期状態を生成する。
- WAV完成ごとに更新する。
- 正常終了時に `completed` とする。
- 更新は一時ファイル経由のアトミック置換とする。

### 9.2 状態

トップレベル状態:

- `pending`
- `in_progress`
- `completed`
- `failed`

サンプル状態:

- `pending`
- `completed`
- `failed`

### 9.3 最低限の内容

```yaml
schema_version: 1
kind: postprocess_manifest

status: completed

definition:
  id: sc8850-cello-1
  name: Cello 1

provenance:
  application_version: 0.1.0
  source_manifest_sha256: "<sha256>"
  resolved_definition_sha256: "<sha256>"
  postprocess_settings_sha256: "<sha256>"
  stages:
    - trim
    - loop

source:
  directory: ../../recorded/sc8850-cello-1
  manifest: manifest.yaml

midi:
  channel: 0
  bank_msb: 0
  bank_lsb: 0
  program: 41

audio:
  sample_rate: 48000
  channels: 2
  data_format: int24

naming:
  sample_filename: >-
    r{root_note:03d}__k{key_low:03d}-{key_high:03d}__v{velocity_low:03d}-{velocity_high:03d}__s{send_velocity:03d}

resolved_definition:
  zones:
    - low: 36
      root: 38
      high: 40
  velocity_layers:
    - low: 1
      high: 63
      send: 48

samples:
  - index: 0
    file: r038__k036-040__v001-063__s048.wav
    source_file: r038__k036-040__v001-063__s048.wav
    status: completed

    mapping:
      root_note: 38
      key_low: 36
      key_high: 40
      velocity_low: 1
      velocity_high: 63

    audio:
      frame_count: 214032
      duration_seconds: 4.459

    trim:
      applied: true
      start_sample: 47992
      end_sample_exclusive: 262024
      removed_head_frames: 47992
      removed_tail_frames: 122
      removed_head_seconds: 0.99983
      removed_tail_seconds: 0.00254
      noise_floor_dbfs: -96.3
      fade_in_frames: 48
      fade_out_frames: 240

    loop:
      applied: true
      status: success
      start_frame: 96000
      end_frame: 187391
      crossfade_ms: 25.0
      midi_unity_note: 38
      confidence: 0.87
      confidence_label: high
      smpl_chunk_written: true
```

### 9.4 引き継ぐ情報と新規に記録する情報

| ブロック | 由来 |
|---|---|
| `definition`, `midi`, `naming`, `resolved_definition` | source からそのままコピー |
| `audio`(トップレベル) | source からコピー。トリミングは `sample_rate` / `channels` / `data_format` を変更しない |
| `samples[].mapping` | source からそのままコピー |
| `samples[].audio` | ポストプロセス後の実測値 |
| `samples[].trim` | `TrimResult` から生成 |
| `samples[].loop` | `LoopResult` から生成 |

`mapping` を引き継ぐことにより、パッチ生成ツールは派生マニフェスト1枚だけでキーレンジ・ベロシティレンジ・ルートノートを再構築できる。

`captured`(MIDI音源へ実際に送信した情報)は引き継がない。ポストプロセス成果物の消費者はサンプラーであり、収録条件は source マニフェストを辿れば得られるためである。

### 9.5 実行されなかったステージ

セッション定義に含まれないステージのブロックは出力しない。含まれるが未適用に終わった場合は `applied: false` を記録する。

### 9.6 エラー情報

```yaml
status: failed

error:
  type: PostprocessStageError
  message: "loop detection failed"
```

スタックトレースや機密性の高い絶対パスは既定ではマニフェストへ保存しない。詳細はログへ出力する。

---

## 10. ハッシュ

### 10.1 目的

- 派生成果物がどの入力とどの設定から生成されたかを識別する。
- 将来の `audit` による再ポストプロセス候補判定に使用する。

### 10.2 3種のハッシュ

| フィールド | 対象 | 不一致が意味すること |
|---|---|---|
| `source_manifest_sha256` | source `manifest.yaml` のバイト列 | 入力の再録音・再生成 |
| `resolved_definition_sha256` | source から引き継ぎ | 元の音色定義の変更 |
| `postprocess_settings_sha256` | 正規化済みポストプロセス設定 | トリム・ループ設定の変更 |

3種を独立に持つことで、将来の `audit` が `up_to_date` / `source_changed` / `settings_changed` / `missing_samples` を判別できる。

### 10.3 アルゴリズム

- SHA-256。
- `source_manifest_sha256` は source `manifest.yaml` のバイト列に対して直接計算する。
- `postprocess_settings_sha256` は正規化済み設定を canonical JSON へ変換して計算する。
  - 既存 `ResolvedDefinitionHasher.hash_payload()` を再利用する。
  - オブジェクトキーを辞書順に並べ、不要な空白を含めず、`ensure_ascii=False`、`allow_nan=False` とする。

### 10.4 設定ハッシュの対象

- ステージの `kind` と適用順
- 各ステージの解決済み設定値(省略されたフィールドもDSP側デフォルトへ解決した後の値)
- `loop.on_failure`
- `midi_unity_note` の解決方式(`from_manifest` / `auto` / 固定値)

### 10.5 設定ハッシュの対象外

- YAMLコメント、空白、インデント、キーの記述順
- `source.directory` / `output.directory` のパス
- 対象音色の指定(`tones`)
- 作成日時、実行状態、エラー情報
- アプリケーションバージョン

---

## 11. CLI

```bash
midi-sampling postprocess <postprocess_session.yaml>
```

### 11.1 終了コード

サンプリング仕様 §17.5 と整合させる。

- `0`: 全音色のポストプロセスが成功
- `1`: 実行中のエラー
- `2`: セッション定義、参照ファイル、source マニフェストなどの読込・検証エラー

---

## 12. 推奨モジュール構成

```text
src/midi_sampling/postprocess/
├─ __init__.py
├─ exceptions.py
├─ postprocess_executor.py
│
├─ definitions/
│  ├─ __init__.py
│  ├─ postprocess_session_definition.py
│  ├─ trim_stage_definition.py
│  └─ loop_stage_definition.py
│
├─ resolving/
│  ├─ __init__.py
│  └─ postprocess_resolver.py
│
├─ planning/
│  ├─ __init__.py
│  ├─ postprocess_target.py
│  ├─ postprocess_plan.py
│  └─ postprocess_plan_builder.py
│
├─ stages/
│  ├─ __init__.py
│  ├─ stage.py
│  ├─ trim_stage.py
│  └─ loop_stage.py
│
├─ hashing/
│  ├─ __init__.py
│  └─ postprocess_settings_hasher.py
│
└─ manifest/
   ├─ __init__.py
   ├─ postprocess_manifest.py
   └─ postprocess_manifest_repository.py
```

`postprocess` から `sampling` への依存は許可する(source マニフェストを読むため)。逆方向の依存を禁止する。

---

## 13. 例外設計

`MidiSamplingError` を全体の基底とし、`SamplingError` と `PostprocessError` をその派生とする。

- `PostprocessError`
- `PostprocessDefinitionError`
- `PostprocessSourceError`
- `PostprocessDependencyError`
- `PostprocessStageError`
- `PostprocessExecutionError`

低レベル例外およびDSPパッケージの例外をそのままCLIへ露出しない。CLIではユーザーが修正可能な情報を含むメッセージへ変換する。

---

## 14. ロギング

最低限以下をログへ記録する。

- 読み込んだセッション定義
- 解決した source 音色とサンプル数
- 有効なステージと適用順
- 現在の音色、サンプルindex、ファイル名
- 各ステージの適用結果(トリム量、ループ点、信頼度)
- 中間ファイルパスと完成パス
- マニフェスト更新
- エラー種別

標準出力は進捗と要約を中心にし、詳細はロガーへ送る。

---

## 15. テスト要件

### 15.1 定義モデル

- 正常なYAMLを読める。
- 未知フィールドを拒否する。
- 型違反、値域違反を拒否する。
- `stages` 空配列を拒否する。
- 未知の `kind` を拒否する。
- 同一 `kind` の重複を拒否する。

### 15.2 参照解決

- source ディレクトリ不在
- source マニフェスト不正、`status` が `completed` でない
- source WAV欠損
- `tones` に存在しない音色ID
- 絶対パス拒否

### 15.3 計画生成

- source マニフェストからのターゲット件数
- ファイル名の1:1対応
- 出力パス検証

### 15.4 実行前フェイルセーフ

- 出力ディレクトリ既存でエラー
- `source.directory` と `output.directory` の同一指定を拒否

### 15.5 実行

実DSPパッケージを使用せず、Fake `PostprocessStage` で検証する。

- ステージ適用順
- 中間ファイルから完成WAVへの置換
- WAV完了後にマニフェストが更新される順序
- エラー後に後続サンプルを実行しない
- エラー時にマニフェストが `failed` になる
- **source ディレクトリが一切変更されない**
- **各ステージへ渡す入力・出力パスが必ず `.wav` で終わる**

### 15.6 マニフェスト

- 初期生成
- `mapping` が source からコピーされる
- サンプル完了更新、音色完了更新、失敗更新
- 一時ファイルからのアトミック置換
- 途中で例外が発生しても旧マニフェストが壊れない

### 15.7 ハッシュ

- 設定変更でハッシュが変化する。
- YAMLコメント、キー順の変更で変化しない。
- ディレクトリパスの変更で変化しない。

### 15.8 DSP結合

`pytest.importorskip` でガードし、DSPパッケージが利用可能な場合のみ実行する。

- トリム後のWAVが読み込める。
- 生成WAVから `smpl` チャンクを読み戻せる。

---

## 16. 初期実装の受入条件

1. ポストプロセスセッションYAMLから複数の音色を読み込める。
2. source マニフェストを読み取り専用で解決できる。
3. トリミングとループ検出を規定順で適用できる。
4. `midi_unity_note: from_manifest` が `mapping.root_note` を使用する。
5. 中間ファイルが常に `.wav` 拡張子である。
6. 最終WAVをアトミックに確定できる。
7. 音色単位の派生 `manifest.yaml` を自動生成・更新できる。
8. `mapping` が source から欠落なく引き継がれる。
9. エラー時に直ちにセッション全体を停止できる。
10. source 成果物が一切変更されない。
11. 3種のハッシュを派生マニフェストへ保存できる。
12. 既存出力を暗黙に上書きしない。
13. 実DSPパッケージを使わない単体・結合テストがある。

---

## 17. 初期仕様の対象外・将来対応

- `audit` サブコマンドのポストプロセスステージ対応
- `--resume`
- 既存派生成果物の自動上書き・自動削除
- 変更されたサンプルだけの差分再処理
- ノーマライズ、リサンプル、ビット深度変換
- ラウンドロビン、複数テイク
- KONTAKT `*.nki` 生成
- SFZ生成
- UVI Falcon `*.uvip` 生成

---

## 18. 実装上の禁止事項

- source ディレクトリ配下を書き換えない。
- `PostprocessExecutor` 内でYAMLを読み込まない。
- `PostprocessExecutor` 内で外部参照を解決しない。
- `stages/` 以外のモジュールでDSPパッケージを import しない。
- 外部DSPパッケージへ `.wav` 以外の拡張子のパスを渡さない。
- ファイル名からマッピング情報を逆解析する設計にしない。
- マニフェストよりファイル名を正本として扱わない。
- 既存出力を暗黙に上書きしない。
- DSP側の設定を `dict` で素通ししない。
