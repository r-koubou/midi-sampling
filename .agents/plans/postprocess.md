# ポストプロセス統合：postprocess ステージとマニフェスト契約

## Context

`sampling_implementation.md` §23 で将来対応としていた「ポストプロセス後の派生マニフェスト」「トリミング・ループ処理とのマニフェスト統合」を実装する。

すでに別リポジトリとして波形処理の実装が完了している。

| プロジェクト | 配布名 | 依存 | requires-python |
|---|---|---|---|
| `../sample-loop-detector` | `sample-loop-detector` | numpy, scipy, **librosa**, soundfile, typer | `>=3.12,<3.14` |
| `../sample-trimmer` | `wav-silence-trimmer` | numpy, scipy, soundfile | `>=3.12` |
| このリポジトリ | `midi-sampling` | mido, pydantic, pyyaml, sounddevice, soundfile, typer | `>=3.14` |

### 方針（決定済み）

**DSP アルゴリズムは取り込まない。マニフェスト契約で連結する。**

責務の切り方を「サンプリング vs ポストプロセス」ではなく **「純粋DSPライブラリ vs ワークフロー」** とする。

- DSP 2プロジェクトは WAV ファイル単位の汎用ライブラリとして独立を維持する。midi-sampling を一切知らない。単体リリース・単体テスト・独自品質ゲート（loop-detector は mypy strict / coverage 85%）をそのまま保つ。
- midi-sampling が `[postprocess]` optional extra として依存し、**アダプタ層のみ**を持つ。増える責務はオーケストレーションと契約であり、DSP アルゴリズムではない。
- 境界は `manifest.yaml`。これは §1「後続ツールがファイル名解析に依存せず、マニフェストだけでマッピングを再構築できることを必須とする」の直接的な帰結。

### 統合によって初めて可能になること（分離のままでは得られない価値）

単体 CLI ではファイルから推測するしかない情報を、マニフェストが正解として持っている。

- ループの `midi_unity_note` → `mapping.root_note` が既知。音高推定に頼らなくてよい。
- トリムの無音区間ヒント → `timing.pre_roll` / `release_capture` が既知。
- `mapping`（key/velocity レンジ）→ ポストプロセス後もそのまま引き継げるため、パッチ生成が派生マニフェスト1枚で完結する。

### Python バージョン

`>=3.14` と `<3.14` の積集合が空のため現状は連携不能。`src/` に 3.14 固有構文（`type` 文・`except*`・`ReadOnly`・`TypeIs` 等）は無いことを確認済みのため、**midi-sampling を `>=3.12,<3.14` へ降格**して同一環境で in-process 連携する。librosa の 3.14 対応後に上げ直す。

### 今回のスコープ外

- `export`（KONTAKT `*.nki` / SFZ / UVI Falcon `*.uvip` 生成）— 判断保留
- `audit` サブコマンドのステージ対応 — ただし派生マニフェストは将来 audit 可能なハッシュ連鎖を最初から持たせる

---

## 0. ドキュメントの配置（最初に行う）

役割の異なる2つのドキュメントを作る。内容を重複させず、仕様書を正本とする。

| ファイル | 役割 | 内容 |
|---|---|---|
| `.agents/plans/postprocess.md` | **実装プラン** | 本ドキュメントをそのまま保管する。判断の経緯（なぜ統合するか、なぜ別リポジトリ維持か、Python 降格の理由、`.wav.part` を採らない理由）と作業手順・検証手順 |
| `.agents/specs/postprocess_implementation.md` | **確定仕様** | §2〜§8 を仕様として整形したもの。経緯は書かず、実装が従うべき規則のみ |

`.agents/plans/postprocess.md` は着手前に配置する（`.agents/plans/` は作成済み・空）。

## 1. 仕様書の新規作成

`.agents/specs/postprocess_implementation.md` を新規作成する。`sampling_implementation.md` の章立て（目的 / 技術選定 / アーキテクチャ / 定義ファイル / 計画 / 出力 / フェイルセーフ / 実行シーケンス / マニフェスト / ハッシュ / CLI / モジュール構成 / 例外 / ロギング / テスト要件 / 受入条件 / 対象外 / 禁止事項）に倣い、以下 §2〜§8 の内容を確定仕様として記述する。

`sampling_implementation.md` は変更しない（§23 の該当項目が実装されたことは progress.md 側に記録する）。

---

## 2. 出力レイアウトと不変条件

```
recorded/<tone-id>/manifest.yaml     kind: sample_manifest       ← run が生成。以後不変
        │
        ↓ postprocess （trim → loop → smpl チャンク埋込）
processed/<tone-id>/manifest.yaml    kind: postprocess_manifest  ← 派生。source hash を保持
        │
        ↓ export （今回スコープ外）
patches/<tone-id>.sfz / .nki / .uvip
```

**絶対の不変条件：**

- `recorded/` を書き換えない。in-place 処理は禁止。
  録音は実時間・ハードウェア占有で数時間かかるが、トリム閾値やループ検出は何度も試行錯誤する。この非対称性がステージ分離の実務的根拠。`sampling_implementation.md` §24「既存出力を暗黙に上書きしない」とも一致する。
- WAV ファイル名は source からそのまま引き継ぐ（1:1 対応）。
- `mapping` は source マニフェストからコピーする。ファイル名からの逆解析は行わない（§24）。
- ステージ間の中間ファイルは `processed/<tone-id>/.work/` に置き、**必ず `.wav` 拡張子とする**（理由は §6「ステージ連鎖と中間ファイル」）。

---

## 3. 派生マニフェスト `kind: postprocess_manifest`

**このファイルは完全な自動生成物である。** `sampling_implementation.md` §15.1 の `sample_manifest` と同じ扱いとし、以下を仕様書に明記する。

- ポストプロセスプログラムが自動生成する。ユーザーが手書きする前提にしない。
- ユーザーが記述するのは §4 の `postprocess_session.yaml` のみ。
- 実行前フェイルセーフを全て通過した後、最初の WAV を処理する前に `status: pending` の初期状態を生成する。
- WAV が1本完成するたびに更新し、正常終了時に `completed`、失敗時に `failed` + `error` を書く。
- 更新は必ず `manifest.yaml.tmp` 経由のアトミック置換とする（既存 [SampleManifestRepository.write()](src/midi_sampling/sampling/manifest/sample_manifest_repository.py#L55) と同一手順）。
- source 側の `recorded/<tone>/manifest.yaml` は**読むだけ**で、決して書き換えない。

```yaml
schema_version: 1
kind: postprocess_manifest
status: completed            # pending | in_progress | completed | failed

definition:
  id: sc8850-cello-1
  name: Cello 1

provenance:
  application_version: 0.2.0
  source_manifest_sha256: "<source manifest.yaml のバイト列 SHA-256>"
  resolved_definition_sha256: "<source から引き継ぎ。元定義の追跡用>"
  postprocess_settings_sha256: "<設定の canonical JSON の SHA-256>"
  stages: [trim, loop]       # 適用順

source:
  directory: ../../recorded/sc8850-cello-1   # このマニフェストからの相対パス
  manifest: manifest.yaml

midi: {...}                  # source から引き継ぎ
audio: {...}                 # sample_rate / channels / data_format はトリムで不変
naming:
  sample_filename: "<source と同一>"
resolved_definition:         # zones / velocity_layers。パッチ生成が1枚で完結するため引き継ぐ
  zones: [...]
  velocity_layers: [...]

samples:
  - index: 0
    file: r038__k036-040__v001-063__s048.wav
    source_file: r038__k036-040__v001-063__s048.wav
    status: completed
    mapping:                 # source から引き継ぎ（サンプラーへ設定する情報）
      root_note: 38
      key_low: 36
      key_high: 40
      velocity_low: 1
      velocity_high: 63
    audio:                   # ポストプロセス後の実測値
      frame_count: 214032
      duration_seconds: 4.459
    trim:                    # TrimResult 由来
      applied: true
      start_sample: 47992
      end_sample_exclusive: 262024
      removed_head_frames: 47992
      removed_tail_frames: 122
      noise_floor_dbfs: -96.3
      fade_in_frames: 48
      fade_out_frames: 240
    loop:                    # LoopResult 由来
      applied: true
      status: success        # success | not_found | skipped
      start_frame: 96000
      end_frame: 187391
      crossfade_ms: 25.0
      midi_unity_note: 38
      confidence: 0.87
      confidence_label: high
      smpl_chunk_written: true
```

3種のハッシュで「入力・元定義・設定」を独立に追跡でき、将来の `audit` が `up_to_date` / `source_changed` / `settings_changed` / `missing_samples` を判定できる。

- `source_manifest_sha256` は source `manifest.yaml` の**バイト列**の SHA-256（単純・確実）。
- `postprocess_settings_sha256` は既存の [ResolvedDefinitionHasher.hash_payload()](src/midi_sampling/sampling/hashing/resolved_definition_hasher.py#L12) をそのまま再利用する（dict を受け取る汎用メソッドなので改造不要）。

---

## 4. 定義ファイル `kind: postprocess_session`

```yaml
schema_version: 1
kind: postprocess_session

source:
  directory: recorded        # sampling session の output.directory と同じ場所

output:
  directory: processed

stages:                      # 記述順に適用。空配列は禁止
  - kind: trim
    settings:                # TrimConfig に1:1対応。省略値は DSP 側のデフォルト
      on_margin_db: 15.0
      off_margin_db: 8.0
      pre_roll_ms: 8.0
      post_roll_ms: 40.0
      fade_in_ms: 1.0
      fade_out_ms: 5.0

  - kind: loop
    on_failure: skip         # skip（WAVは通す・loop.status=not_found） | error（セッション停止）
    settings:                # DetectionSettings のうち入出力パス以外
      min_loop: 0.3
      max_loop: 8.0
      quality_threshold: 0.6
      crossfade_lengths_ms: [10.0, 25.0, 50.0]
      midi_unity_note: from_manifest   # from_manifest | auto | 0-127
      replace_existing_loop: false

tones:                       # 省略時は source 配下の全音色ディレクトリ
  - sc8850-cello-1
```

- `sampling_implementation.md` §9 の外部ファイル参照規則を継承する（相対パスのみ、URL・絶対パス・glob・環境変数展開・YAMLカスタムタグ禁止）。
- `ConfigDict(extra="forbid")`、Pydantic v2、未知フィールド拒否。DSP 側の設定は将来増えるため、**明示フィールドで写経する**（`dict` の素通しはしない。未知キーがサイレントに無視されるのを防ぐ）。
- `midi_unity_note: from_manifest` が統合の核。`mapping.root_note` を `DetectionSettings.midi_unity_note` へ渡す。

---

## 5. モジュール構成

`src/midi_sampling/postprocess/` を `sampling/` と同格の兄弟パッケージとして新設する。依存方向は **postprocess → sampling の一方向のみ**（source マニフェストを読むため）。

```
src/midi_sampling/postprocess/
├─ __init__.py
├─ exceptions.py                      # PostprocessError 系
├─ postprocess_executor.py
├─ definitions/
│  ├─ postprocess_session_definition.py
│  ├─ trim_stage_definition.py
│  └─ loop_stage_definition.py
├─ resolving/
│  └─ postprocess_resolver.py         # source マニフェスト群を読み ResolvedPostprocessSession へ
├─ planning/
│  ├─ postprocess_target.py
│  ├─ postprocess_plan.py
│  └─ postprocess_plan_builder.py
├─ stages/                            # ★ DSP パッケージへの唯一の接点
│  ├─ stage.py                        # PostprocessStage Protocol / StageContext / StageOutcome
│  ├─ trim_stage.py                   # wav_silence_trimmer
│  └─ loop_stage.py                   # sample_loop_detector
├─ hashing/
│  └─ postprocess_settings_hasher.py  # ResolvedDefinitionHasher を再利用する薄いラッパ
└─ manifest/
   ├─ postprocess_manifest.py
   └─ postprocess_manifest_repository.py
```

`sampling/` 側の既存コードは §7 の小規模リファクタ以外は変更しない。

### 再利用する既存実装

| 用途 | 再利用先 |
|---|---|
| YAML 読込＋Pydantic 検証 | [YamlDefinitionLoader](src/midi_sampling/sampling/loading/yaml_definition_loader.py) をそのまま使う |
| canonical JSON → SHA-256 | [ResolvedDefinitionHasher.hash_payload()](src/midi_sampling/sampling/hashing/resolved_definition_hasher.py#L12) |
| source マニフェスト読込 | [SampleManifestRepository.read()](src/midi_sampling/sampling/manifest/sample_manifest_repository.py#L25) |
| 出力パス検証（予約名・不正文字・長さ） | [OutputPathValidator](src/midi_sampling/sampling/validation/output_path_validator.py) |
| 一時ファイル → 完成名のアトミック確定 | `os.replace` の手順のみ踏襲（[sampling_executor.py:180-190](src/midi_sampling/sampling/sampling_executor.py#L180-L190)）。`PARTIAL_SUFFIX` は使わない（§6 参照） |
| executor の構造（DI・進捗コールバック・`_abort` で failed マニフェスト書込） | [SamplingExecutor](src/midi_sampling/sampling/sampling_executor.py) の構造を踏襲 |

---

## 6. ステージアダプタ層

```python
class PostprocessStage(Protocol):
    kind: str
    def apply(self, context: StageContext) -> StageOutcome: ...
```

`StageContext`: 入力WAVパス / 出力WAVパス / `ManifestSampleMapping` / audio format / 解決済み設定
`StageOutcome`: 成否 + 派生マニフェストへ書く dict（`trim:` / `loop:` ブロック）

**DSP パッケージの import は `stages/` 配下のモジュールに限定し、かつ関数内で遅延 import する**（[cli.py:55-62](src/midi_sampling/cli.py#L55-L62) が sounddevice に対して既に採っているパターン）。未インストール時は `PostprocessDependencyError` を送出し、CLI が `pip install midi-sampling[postprocess]` を案内する。

### TrimStage

`wav_silence_trimmer.cli.process_file` は使わない（CLI 層にあり `ProcessingResult` / ログ出力が絡むため）。ライブラリ関数を直接組み合わせる：

```
audio_io.read_wav → detector.detect_trim_region → スライス → fade.apply_fades → audio_io.write_wav
```

`write_wav` は `subtype` / `format` を保存するため、24bit PCM が維持される。

### LoopStage

```
pipeline.run_detection(DetectionSettings(input_path=..., output_path=..., midi_unity_note=<mapping.root_note>, ...))
  → pipeline.write_output_wav(output, settings)
```

`write_output_wav` が `build_smpl_chunk` + `insert_smpl_chunk` を行い一時ファイル経由でアトミックに書く。libsndfile は `smpl` チャンクを書けないため、この経路が必須（自前実装は不要）。

`DetectionSettings.force=True` を渡す（出力先の存在チェックは midi-sampling 側の実行前フェイルセーフが担当するため、二重チェックにしない）。

### ステージ連鎖と中間ファイル

複数ステージを鎖にすると中間 WAV が必要になるが、**中間ファイルに `.wav.part` を使ってはならない。**

progress.md 記載のとおり、サンプリング初回実装で `*.wav.part` が soundfile の書込時フォーマット推定に失敗して TypeError になった経緯がある（`SdAudioDevice.export_audio` に `format="WAV"` を明示して解決、リグレッションテスト [tests/test_sd_audio_device_export.py](tests/test_sd_audio_device_export.py) あり）。

今回の DSP 2ライブラリを調査した結果、**現状は同じ問題は起きない**：

| I/O | 実装 | 拡張子依存 |
|---|---|---|
| `wav_silence_trimmer.audio_io.read_wav` | `sf.info()` / `sf.read()` | なし（libsndfile は読込時 RIFF ヘッダで判別。前回のバグは書込側限定） |
| `wav_silence_trimmer.audio_io.write_wav` | `sf.write(..., format=...)` | なし（常に `format=` を明示） |
| `sample_loop_detector.audio.riff.parse_wave_file` | `path.read_bytes()` → 自前 RIFF パーサ | なし |
| `sample_loop_detector.pipeline.write_output_wav` | 生バイト `handle.write()` → `os.replace` | なし（soundfile 不使用） |

ただしこれは相手ライブラリの現在の実装に依存しているだけなので、**設計として拡張子推定に一切依存させない**。中間ファイルは隠しワークディレクトリに置き、全て正規の `.wav` 拡張子とする：

```
processed/<tone-id>/
├─ .work/                        ← ステージ間中間ファイル（全て .wav 拡張子）
│  ├─ <name>.s1-trim.wav
│  └─ <name>.s2-loop.wav
├─ <name>.wav                    ← 全ステージ成功後 .work/ から os.replace で確定
└─ manifest.yaml
```

- 外部ライブラリへ渡すパスは入力・出力とも必ず `.wav` で終わる。
- `.part.wav`（拡張子を後置する案）は採らない。残骸が通常の WAV として glob に拾われてしまい、§14「エラー時に残った一時ファイルを通常のWAVとして扱わない」の意図を壊すため。
- `.work/` は同一ディレクトリツリー内なので `os.replace` はアトミック。
- 音色の全サンプル完了後に `.work/` をベストエフォートで削除する。失敗時は残してデバッグに使えるようにする（ステージごとの中間物が残るため、トリム結果だけ聴いて閾値を調整できる）。
- マニフェストは `.work/` 配下を一切参照しない。

**追加テスト（リグレッション）**: 各ステージへ渡す入力・出力パスが必ず `.wav` で終わることを Fake stage で検証する。`tests/test_sd_audio_device_export.py` と同じ意図の防御。

---

## 7. 既存コードへの変更（最小限）

1. **`pyproject.toml`**
   - `requires-python = ">=3.12,<3.14"`
   - `[project.optional-dependencies] postprocess = ["sample-loop-detector>=0.1.0", "wav-silence-trimmer>=0.1.0"]`
   - 2パッケージが PyPI 未公開の間は `[tool.uv.sources]` でパス参照 or git 参照を暫定指定する（**要確認事項**：公開予定の有無）
2. **`src/midi_sampling/exceptions.py`（新規）** — `MidiSamplingError` を導入し、既存 `SamplingError` をその派生にする。`postprocess/exceptions.py` の `PostprocessError` も同じ基底に置く。CLI は `MidiSamplingError` を捕捉する。既存の公開名は変えないため互換。
3. **`src/midi_sampling/sampling/manifest/sample_manifest_repository.py`** — アトミック YAML 読み書きを Pydantic モデル型で汎用化した基底クラスへ切り出し、`SampleManifestRepository` と `PostprocessManifestRepository` の両方から使う。公開 API は不変のため既存テストは通る。
4. **`src/midi_sampling/cli.py`** — `postprocess` サブコマンドを追加。既存 `run` / `audit` と同じ終了コード方針（0 = 正常、1 = 実行失敗、2 = 定義エラー）。
5. **`examples/`** — `examples/sessions/postprocess.yaml` を追加。

---

## 8. テスト

`tests/test_postprocess_*.py` を既存テストの流儀（Fake デバイス・実デバイス不使用）に合わせて追加する。

- 定義モデル：未知フィールド拒否 / 値域違反 / `stages` 空配列拒否 / 未知 `kind` 拒否
- 参照解決：source ディレクトリ不在 / source マニフェスト不正 / `tones` に無い音色ID
- 計画生成：source マニフェストからの target 生成、ファイル名 1:1 対応
- 実行前フェイルセーフ：出力ディレクトリ既存でエラー、`recorded/` が変更されないこと
- executor：**Fake stage**（`PostprocessStage` Protocol の実装）で DSP 非依存に検証。ステージ適用順 / `.part` → 完成名 / マニフェスト更新順序 / 失敗時に後続へ進まない・`failed` が書かれる
- マニフェスト：`mapping` が source からコピーされること、3種ハッシュが記録されること、設定変更でハッシュが変わりコメント変更で変わらないこと
- DSP 実結合テスト：`pytest.importorskip("sample_loop_detector")` でガードし、生成 WAV から `smpl` チャンクを読み戻して検証

---

## 検証

```bash
# 1. Python 降格の妥当性（既存 134 件が 3.13 で通ること）
uv run --python 3.13 pytest

# 2. 追加テストを含む全体
uv sync --extra postprocess
uv run pytest

# 3. 実データでの end-to-end
uv run midi-sampling run examples/sessions/session.yaml        # 既存 recorded/ があればスキップ
uv run midi-sampling postprocess examples/sessions/postprocess.yaml
uv run midi-sampling postprocess examples/sessions/postprocess.yaml   # 2回目 → ExistingOutputError で停止すること
```

手動確認：

- `recorded/` の WAV とマニフェストのタイムスタンプ・ハッシュが変化していないこと
- `processed/<tone>/manifest.yaml` の `mapping` が source と完全一致すること
- 生成 WAV に `smpl` チャンクが入っていること
  （`python -c "from sample_loop_detector.audio.riff import parse_wave_file; ..."` で確認）
- 生成 WAV を KONTAKT / sforzando へ読み込ませ、ループ点が認識されること
- `postprocess_settings_sha256` が設定変更で変わり、YAML コメント変更で変わらないこと

`.agents/contexts/progress/progress.md` を更新し、`sampling_implementation.md` §23 の「ポストプロセス後の派生マニフェスト」「トリミング・ループ処理とのマニフェスト統合」が解消済みであること、`export`（nki/sfz/uvip）が未着手であることを記録する。
