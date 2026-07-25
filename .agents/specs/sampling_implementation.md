# MIDI Sampling 実装仕様書

- 対象リポジトリ: `r-koubou/midi-sampling`
- 対象ブランチ: `refactor/next-gen`
- 実装対象ディレクトリ: `src/midi_sampling/sampling`
- 仕様バージョン: 1
- 文書作成日: 2026-07-21
- 状態: 初期実装向け確定仕様

---

## 1. 目的

外部MIDI音源を自動サンプリングし、KONTAKT、SFZ、UVI Falconなどのサンプラー形式へ変換可能な中間成果物を生成する。

初期実装の責務は以下とする。

1. YAML定義ファイルを読み込む。
2. サンプルゾーンとベロシティプロファイルを解決する。
3. 実行用サンプリング計画へ正規化する。
4. MIDI音源を制御し、WAVを録音する。
5. 音色単位のマニフェストを自動生成・更新する。
6. 既存成果物と現在の定義の整合性を監査する `audit` サブコマンドを提供する。

KONTAKT `*.nki`、SFZ、UVI Falcon `*.uvip` の生成処理そのものは初期実装の対象外とする。ただし、後続ツールがファイル名解析に依存せず、マニフェストだけでマッピングを再構築できることを必須とする。

---

## 2. 技術選定

### 2.1 使用ライブラリ

既存の `pyproject.toml` に含まれる以下を使用する。

- `pydantic`
  - YAMLから読み込んだデータの型定義、制約検証、正規化に使用する。
- `PyYAML`
  - `yaml.safe_load` によるYAML読込に使用する。
- `typer`
  - `run`、`audit` サブコマンドのCLI定義に使用する。
- 既存デバイス実装
  - `AudioDevice`
  - `MidiDevice`

追加のYAML ORMライブラリは導入しない。

### 2.2 Pydantic方針

- Pydantic v2を前提とする。
- 全モデルで未知フィールドを拒否する。
  - `ConfigDict(extra="forbid")`
- MIDI値は厳密な整数型として検証する。
  - `bool` を整数として受理しない。
- 時間値は有限の数値のみ受理する。
  - `NaN`、正負の無限大を拒否する。
- YAMLの構文検証と、複数要素間の意味検証を分離する。

---

## 3. アーキテクチャ

処理を以下の段階へ分離する。

```text
YAMLファイル
  ↓
YamlLoader
  ↓
Definition DTO（Pydantic）
  ↓
DefinitionResolver
  ↓
Resolved Definition
  ↓
SemanticValidator / Normalizer
  ↓
SamplingPlanBuilder
  ↓
SamplingPlan
  ├─ SamplingExecutor
  └─ AuditService
```

### 3.1 責務境界

#### YamlLoader

- UTF-8でYAMLを読み込む。
- `yaml.safe_load` のみを使用する。
- YAML構文エラーを、ファイルパスと位置情報付きのアプリケーション例外へ変換する。

#### Definition DTO

- YAMLの記述構造を表す。
- 外部ファイル参照を保持してよい。
- 実行処理へ直接渡してはならない。

#### DefinitionResolver

- 相対パスを解決する。
- 外部のゾーンレイアウト、ベロシティプロファイル、音色定義、デバイス定義、初期化SMFを読み込む。
- 参照先の `kind` を検証する。
- 実行処理がファイル参照を意識しなくてよい状態へ展開する。

#### SemanticValidator / Normalizer

- ゾーン重複、ベロシティ範囲、完全被覆などを検証する。
- ゾーンとレイヤーを規定順へ並べる。
- 同じ入力から常に同じ正規化結果を生成する。

#### SamplingPlanBuilder

- ゾーンとベロシティレイヤーの直積を生成する。
- 出力ファイル名と出力パスを全件生成する。
- 実行前フェイルセーフ検証を行う。
- ハッシュ算出対象となる正規化データを構築する。

#### SamplingExecutor

- YAML、Pydanticモデル、外部参照を扱わない。
- 解決・検証済みの `SamplingPlan` のみを受け取る。
- MIDI・オーディオデバイスを制御する。
- WAVとマニフェストをアトミックに更新する。

#### AuditService

- MIDI・オーディオデバイスを開かない。
- ファイルを変更しない。
- 現在の定義と既存マニフェスト・WAVの整合性を検査する。

---

## 4. 定義ファイルの種類

初期仕様では、以下の4種類を定義する。

1. `zone_layout`
2. `velocity_profile`
3. `sampling_definition`
4. `sampling_session`

既存のオーディオデバイス定義、MIDIデバイス定義は現在の形式を継続利用する。

すべての新規定義ファイルは以下を必須とする。

```yaml
schema_version: 1
kind: <definition kind>
```

---

## 5. ゾーンレイアウト

### 5.1 外部プリセット形式

```yaml
schema_version: 1
kind: zone_layout

zones:
  - low: 36
    root: 38
    high: 40

  - low: 41
    root: 43
    high: 45
```

### 5.2 フィールド

| フィールド | 型 | 必須 | 制約 |
|---|---:|---:|---|
| `low` | int | Yes | 0～127 |
| `root` | int | Yes | 0～127 |
| `high` | int | Yes | 0～127 |

### 5.3 意味制約

- `low <= root <= high`
- ゾーン同士は重複禁止。
- ゾーン間の空白は許可する。
- 1件以上のゾーンを必須とする。
- YAML記述順には依存しない。
- 正規化時に `(low, root, high)` の昇順へ並べる。
- 同一範囲または交差範囲が存在した場合はエラーとする。

---

## 6. ベロシティプロファイル

### 6.1 外部プリセット形式

```yaml
schema_version: 1
kind: velocity_profile

layers:
  - low: 1
    high: 63
    send: 48

  - low: 64
    high: 127
    send: 112
```

### 6.2 フィールド

| フィールド | 型 | 必須 | 制約 |
|---|---:|---:|---|
| `low` | int | Yes | 1～127 |
| `high` | int | Yes | 1～127 |
| `send` | int | Yes | 1～127 |

MIDIベロシティ0はNote Off相当として扱われるため、サンプリング用ベロシティには使用しない。

### 6.3 意味制約

- `low <= send <= high`
- 各範囲は両端を含む。
- レイヤー同士は重複禁止。
- レイヤー間の空白は禁止。
- 全体で1～127を完全に被覆する。
- 1件以上のレイヤーを必須とする。
- YAML記述順には依存しない。
- 正規化時に `(low, high, send)` の昇順へ並べる。

---

## 7. 音色サンプリング定義

### 7.1 基本形式

```yaml
schema_version: 1
kind: sampling_definition

id: sc8850-cello-1
name: Cello 1

midi_program:
  bank_msb: 0
  bank_lsb: 0
  program: 41

zone_layout:
  file: ../presets/zones/cello.yaml

velocity_profile:
  file: ../presets/velocities/four_layers.yaml

timing:
  note_on: 4.0
  release_capture: 3.0
```

### 7.2 識別子

#### `id`

- 必須。
- 音色単位の出力ディレクトリ名に使用する。
- セッション内で一意でなければならない。
- 推奨正規表現:

```regex
^[a-z0-9][a-z0-9_-]*$
```

- Windows予約デバイス名と衝突してはならない。
- Bank Select / Program Changeから自動生成しない。
- 同じMIDI音色を異なる条件で収録する場合は異なる`id`を使用できる。

#### `name`

- 任意。
- 表示専用。
- 日本語、空白などを許可する。
- 出力パスの生成には使用しない。

### 7.3 MIDI音色指定

```yaml
midi_program:
  bank_msb: 0
  bank_lsb: 0
  program: 41
```

| フィールド | 値域 | 必須 |
|---|---:|---:|
| `bank_msb` | 0～127 | Yes |
| `bank_lsb` | 0～127 | Yes |
| `program` | 0～127 | Yes |

Bank Selectの省略および暗黙の0補完は禁止する。

1つの `sampling_definition` は、1組のBank Select MSB / LSB / Program Changeのみを持つ。

複数音色の列挙は許可しない。

### 7.4 ゾーン定義の指定方法

外部ファイル参照またはインライン定義のどちらか一方を使用する。

#### 外部参照

```yaml
zone_layout:
  file: ../presets/zones/cello.yaml
```

#### インライン

```yaml
zone_layout:
  zones:
    - low: 36
      root: 38
      high: 40
```

`file` と `zones` の併記は禁止する。

### 7.5 ベロシティ定義の指定方法

外部ファイル参照またはインライン定義のどちらか一方を使用する。

#### 外部参照

```yaml
velocity_profile:
  file: ../presets/velocities/four_layers.yaml
```

#### インライン

```yaml
velocity_profile:
  layers:
    - low: 1
      high: 63
      send: 48
    - low: 64
      high: 127
      send: 112
```

`file` と `layers` の併記は禁止する。

### 7.6 音色固有タイミング

```yaml
timing:
  note_on: 4.0
  release_capture: 3.0
```

| フィールド | 意味 | 必須 |
|---|---|---:|
| `note_on` | Note OnからNote Offまでの秒数 | Yes |
| `release_capture` | Note Off後に録音を継続する総秒数 | Yes |

`release_capture` には以下を含める。

- 音色のリリースまたは残響
- 終端ノイズフロア測定用の余白

`release` という旧名称は使用しない。

---

## 8. サンプリングセッション定義

### 8.1 基本形式

```yaml
schema_version: 1
kind: sampling_session

audio_device:
  file: devices/audio_device.yaml

midi_device:
  file: devices/sc8850_part_a.yaml

midi:
  channel: 0
  initialization_files:
    - midi/GS_Reset.mid
    - midi/Reverb_Chorus_Delay_Set_0.mid

timing:
  program_change_settle: 0.5
  pre_roll: 1.0
  inter_sample_wait: 0.5

output:
  directory: recorded
  naming:
    sample_filename: >-
      r{root_note:03d}__k{key_low:03d}-{key_high:03d}__v{velocity_low:03d}-{velocity_high:03d}__s{send_velocity:03d}

definitions:
  - file: tones/cello-1.yaml
  - file: tones/trumpet-1.yaml
```

### 8.2 MIDIチャンネル

- 値域は0～15。
- 必須。
- セッション内の全音色で共通とする。
- 音色定義側からの上書きは初期仕様では禁止する。

### 8.3 初期化SMF

- `initialization_files` は記述順に送信する。
- セッション開始時に一度だけ送信する。
- 各音色または各サンプルの前には再送しない。
- 空配列を許可する。
- 相対パスはセッション定義ファイルの所在ディレクトリを基準とする。

### 8.4 セッション共通タイミング

```yaml
timing:
  program_change_settle: 0.5
  pre_roll: 1.0
  inter_sample_wait: 0.5
```

| フィールド | 意味 | 必須 |
|---|---|---:|
| `program_change_settle` | Bank Select / Program Change送信後、録音へ進むまでの待機秒数 | Yes |
| `pre_roll` | 録音開始後、Note On送信までの録音秒数 | Yes |
| `inter_sample_wait` | 録音完了後、次のサンプルへ進むまでの非録音待機秒数 | Yes |

`pre_roll` は先頭ノイズフロア測定用の余白として使用できる。

`inter_sample_wait` は録音データに含めない。

### 8.5 時間値共通制約

- 単位は秒。
- YAMLでは整数または浮動小数点数を受理する。
- 内部では `float` として扱う。
- 0以上の有限値を必須とする。
- 総録音時間は以下で算出する。

```text
pre_roll + note_on + release_capture
```

- 総録音時間は0より大きくなければならない。
- 録音直前に以下でフレーム数へ変換する。

```text
round(sample_rate * total_seconds)
```

---

## 9. 外部ファイル参照規則

### 9.1 許可する参照

- `sampling_session` から:
  - オーディオデバイス定義
  - MIDIデバイス定義
  - 初期化SMF
  - `sampling_definition`
- `sampling_definition` から:
  - `zone_layout`
  - `velocity_profile`

### 9.2 禁止事項

- ゾーンプリセットから別プリセットを参照すること。
- ベロシティプリセットから別プリセットを参照すること。
- 定義の継承。
- deep merge。
- URL参照。
- 絶対パス。
- `~` 展開。
- 環境変数展開。
- glob。
- YAMLカスタムタグ。

### 9.3 相対パス基準

相対パスは常に、参照を記述したYAMLファイルの所在ディレクトリを基準とする。

内部では `Path.resolve(strict=True)` 相当で正規化してよいが、YAML上では相対パスのみ許可する。

`.yaml` を標準拡張子とし、`.yml` も読み込み可能とする。

---

## 10. サンプリング計画

### 10.1 直積規則

すべてのゾーンへ同一のベロシティプロファイルを適用する。

```text
サンプル数 = ゾーン数 × ベロシティレイヤー数
```

ゾーン単位のベロシティプロファイル上書きは初期仕様では対応しない。

### 10.2 実行用モデル例

```python
@dataclass(frozen=True)
class SamplingTarget:
    definition_id: str
    root_note: int
    key_low: int
    key_high: int
    velocity_low: int
    velocity_high: int
    send_velocity: int
    note_on: float
    release_capture: float
    output_path: Path
```

実際には必要に応じてPydanticモデルまたはdataclassを選択してよい。ただし実行モデルは外部参照やYAML構造を保持してはならない。

### 10.3 実行順序

以下の昇順で固定する。

1. `root_note`
2. `velocity_low`
3. 必要なら `key_low`, `key_high`, `send_velocity` を安定ソート用の補助キーとする。

例:

```text
root 36 / velocity 1～63
root 36 / velocity 64～127
root 41 / velocity 1～63
root 41 / velocity 64～127
```

YAML記述順には依存しない。

---

## 11. 出力ディレクトリとWAV命名

### 11.1 ディレクトリ構造

音色単位でディレクトリを分ける。

```text
<output.directory>/
├─ sc8850-cello-1/
│  ├─ manifest.yaml
│  └─ *.wav
└─ sc8850-trumpet-1/
   ├─ manifest.yaml
   └─ *.wav
```

セッション全体のマニフェストは初期仕様では生成しない。

### 11.2 標準ファイル名

コード内の標準テンプレート:

```text
r{root_note:03d}__k{key_low:03d}-{key_high:03d}__v{velocity_low:03d}-{velocity_high:03d}__s{send_velocity:03d}
```

プログラムが `.wav` を付加する。

例:

```text
r060__k058-062__v001-063__s048.wav
r060__k058-062__v064-127__s112.wav
```

### 11.3 命名テンプレートの上書き

セッション定義で任意に上書きできる。

```yaml
output:
  naming:
    sample_filename: >-
      {definition_id}__r{root_note:03d}__v{send_velocity:03d}
```

`sample_filename` を省略した場合は標準テンプレートを使用する。

拡張子はテンプレートに含めない。

### 11.4 初期仕様で許可するプレースホルダー

- `definition_id`
- `bank_msb`
- `bank_lsb`
- `program`
- `root_note`
- `key_low`
- `key_high`
- `velocity_low`
- `velocity_high`
- `send_velocity`
- `sample_index`

Python式、属性アクセス、関数呼出し、任意コード実行は禁止する。

安全な限定フォーマッターを実装すること。任意の `str.format` 入力を無検証で実行しない。

### 11.5 Bank / Programを標準名に含めない理由

- 音色単位のディレクトリで分離されるため冗長。
- マニフェストに記録される。
- WAV名を過度に長くしない。

必要な場合のみカスタムテンプレートで追加可能とする。

---

## 12. 実行前フェイルセーフ

最初のMIDIメッセージを送信する前、可能であればデバイスを開く前に、全音色・全ターゲットを検証する。

### 12.1 必須検証

- 未知のプレースホルダーがない。
- 生成ファイル名が空でない。
- 全生成ファイル名が音色ディレクトリ内で一意。
- `/`、`\`、NUL文字を含まない。
- 現在のOSで使用不能な文字を含まない。
- Windows予約デバイス名と衝突しない。
- ファイル名末尾が空白またはピリオドでない。
- パスコンポーネント長とフルパス長が現在のOS制限を超えない。
- `definition_id` 由来のディレクトリ名が有効。
- 出力対象の既存ファイルまたは既存音色ディレクトリがない。
- 全参照ファイルが存在し、期待する型である。
- 出力ルートの作成権限がある。

### 12.2 Windows予約デバイス名

大文字・小文字を区別せず、少なくとも以下を拒否する。

```text
CON
PRN
AUX
NUL
COM1 ～ COM9
LPT1 ～ LPT9
```

拡張子を付けた形式も拒否する。

例:

```text
CON.wav
com1.sample.wav
```

### 12.3 既存出力

初期実装では以下とする。

- 既存の音色出力ディレクトリ、マニフェスト、対象WAVが存在した場合はエラー。
- 自動上書きしない。
- 自動削除しない。
- 自動再開しない。
- エラー時点でプログラムを終了する。

`--resume` は将来対応とする。

---

## 13. MIDI・録音実行シーケンス

### 13.1 セッション開始

```text
全定義読込
  ↓
参照解決
  ↓
意味検証・正規化
  ↓
全SamplingTarget生成
  ↓
全出力パス事前検証
  ↓
初期マニフェスト生成
  ↓
デバイス初期化
  ↓
初期化SMFを順番に送信
```

### 13.2 音色単位

```text
Bank Select MSB
  ↓
Bank Select LSB
  ↓
Program Change
  ↓
program_change_settle
  ↓
音色内の全SamplingTargetを規定順で処理
```

Bank Select / Program Changeは音色開始前に一度だけ送信する。各ノートの前には再送しない。

### 13.3 サンプル単位

```text
WAV録音開始
  ↓
pre_roll
  ↓
Note On
  ↓
note_on
  ↓
Note Off
  ↓
release_capture
  ↓
録音停止
  ↓
一時WAVを書き出し
  ↓
完成WAVへアトミックリネーム
  ↓
マニフェストを更新
  ↓
inter_sample_wait
```

### 13.4 エラー時

- 最初のエラーでセッション全体を停止する。
- 後続サンプルへ進まない。
- 可能な限りMIDI Panic / Resetを送る。
- 録音を停止する。
- 現在の音色マニフェストを `failed` へ更新する。
- エラー情報をマニフェストへ記録する。
- 既に完成しているWAVは削除しない。

---

## 14. WAVのアトミック出力

完成ファイル名へ直接書き込まない。

例:

```text
r060__k058-062__v001-063__s048.wav.part
  ↓ 書込・flush・close成功
r060__k058-062__v001-063__s048.wav
  ↓
manifest.yamlをcompletedへ更新
```

必須順序:

1. 一時WAVを書き出す。
2. 一時WAVをクローズする。
3. 完成名へ同一ファイルシステム内で置換する。
4. マニフェストの対象サンプルを `completed` へ更新する。

エラー時に `.part` が残ることは許容する。通常のWAVとしては扱わない。

---

## 15. 音色単位マニフェスト

### 15.1 生成方式

- サンプリングプログラムが自動生成する。
- ユーザーが手書きする前提にしない。
- 全事前検証成功後、デバイス初期化前に初期状態を生成する。
- WAV完成ごとに更新する。
- 正常終了時に `completed` とする。
- 更新は一時ファイル経由のアトミック置換とする。

```text
manifest.yaml.tmp
  ↓ 書込成功
manifest.yaml
```

### 15.2 状態

トップレベル状態:

- `pending`
- `in_progress`
- `completed`
- `failed`

サンプル状態:

- `pending`
- `completed`
- `failed`

初期実装ではサンプルを失敗後に継続しないため、通常は最初の `failed` で音色およびセッションが停止する。

### 15.3 最低限の内容

```yaml
schema_version: 1
kind: sample_manifest

status: completed

definition:
  id: sc8850-cello-1
  name: Cello 1

provenance:
  application_version: 0.1.0
  resolved_definition_sha256: "<sha256>"

midi:
  channel: 0
  bank_msb: 0
  bank_lsb: 0
  program: 41

audio:
  sample_rate: 48000
  channels: 2
  data_format: int24

timing:
  program_change_settle: 0.5
  pre_roll: 1.0
  note_on: 4.0
  release_capture: 3.0
  inter_sample_wait: 0.5

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
    - low: 64
      high: 127
      send: 112

samples:
  - index: 0
    file: r038__k036-040__v001-063__s048.wav
    status: completed

    mapping:
      root_note: 38
      key_low: 36
      key_high: 40
      velocity_low: 1
      velocity_high: 63

    captured:
      note: 38
      velocity: 48
      note_on: 4.0
      release_capture: 3.0
```

### 15.4 `mapping` と `captured`

- `mapping`
  - サンプラーへ設定する情報。
- `captured`
  - MIDI音源へ実際に送信した情報。

現時点では `mapping.root_note` と `captured.note` は同値だが、意味を分離して保持する。

### 15.5 エラー情報

```yaml
status: failed

error:
  type: AudioDeviceError
  message: Recording failed
```

スタックトレースや機密性の高い絶対パスは、既定ではマニフェストへ保存しない。詳細はログへ出力する。

---

## 16. 解決済み定義ハッシュ

### 16.1 目的

- 既存サンプルがどの実効定義から生成されたかを識別する。
- 現在の定義との不一致を検出する。
- `audit` による再サンプリング候補判定に使用する。
- 将来の `--resume` 実装へ備える。

### 16.2 アルゴリズム

- SHA-256
- 外部参照解決後、正規化済みの実効定義を対象とする。
- 正規化済みデータをcanonical JSONへ変換する。
- UTF-8バイト列に対してSHA-256を計算する。

canonical JSONの最低条件:

- オブジェクトキーを辞書順に並べる。
- 不要な空白を含めない。
- Unicodeの表現方法を固定する。
- 数値の表現を一意にする。
- ゾーン、レイヤー、サンプル計画を規定順へ並べる。

Python実装では、専用の正規化DTOを作成し、`json.dumps(..., sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)` 相当を使用する。

### 16.3 ハッシュ対象

少なくとも以下を含める。

- MIDIチャンネル
- Bank Select MSB / LSB / Program
- 正規化済みゾーン
- 正規化済みベロシティレイヤー
- `program_change_settle`
- `pre_roll`
- `note_on`
- `release_capture`
- `inter_sample_wait`
- オーディオ形式
- ファイル命名テンプレート

### 16.4 ハッシュ対象外

- YAMLコメント
- 空白、インデント
- YAMLキーの記述順
- プリセットファイルの保存場所
- 出力先の絶対パス
- 作成日時、完了日時
- 実行状態
- エラー情報
- アプリケーションバージョン
- 表示用 `name`

### 16.5 不一致時の `run` 挙動

既存出力が存在する場合、初期実装の `run` は常に停止する。

マニフェストが存在する場合は、追加情報として以下を表示する。

- 既存ハッシュ
- 現在ハッシュ
- 同一か不一致か

不一致でも自動削除、自動上書き、自動再サンプリングは行わない。

---

## 17. CLI

### 17.1 サンプリング実行

```bash
midi-sampling run <session.yaml>
```

音色定義を直接実行するモードは設けない。

1音色だけ実行する場合も、その音色だけを参照するセッション定義を使用する。

### 17.2 監査

```bash
midi-sampling audit <session.yaml>
```

`audit` は以下を厳守する。

- 読み取り専用。
- MIDIデバイスを開かない。
- オーディオデバイスを開かない。
- ファイルを作成、更新、削除しない。
- 現在の定義を解決・正規化してハッシュを計算する。
- 音色別マニフェストとWAVを検証する。

### 17.3 監査状態

| 状態 | 意味 | 再サンプリング |
|---|---|---:|
| `up_to_date` | ハッシュ一致、マニフェストcompleted、必要WAVが全て存在 | No |
| `missing` | 音色ディレクトリまたはマニフェストが存在しない | Yes |
| `definition_changed` | 保存済みハッシュと現在ハッシュが異なる | Yes |
| `incomplete` | マニフェストがcompletedでない | Yes |
| `missing_samples` | マニフェスト記載WAVが不足 | Yes |
| `invalid_manifest` | マニフェストのYAMLまたはスキーマが不正 | Yes / Manual inspection |

### 17.4 出力例

```text
Sampling audit

[UP TO DATE] sc8850-cello-1
  samples: 24

[RESAMPLE] sc8850-trumpet-1
  reason: definition_changed
  existing hash: 29e8...
  current hash:  941a...

[RESAMPLE] sc8850-flute-1
  reason: missing_samples
  missing:
    r072__k070-074__v064-127__s112.wav

Summary:
  up to date: 1
  resampling required: 2
```

### 17.5 終了コード

- `0`: 全音色が `up_to_date`
- `1`: 再サンプリングが必要な音色が1件以上存在
- `2`: セッション定義、参照ファイル、マニフェストなどの読込・検証エラー

JSON出力は将来拡張としてよい。内部の監査結果モデルは機械可読出力を追加できる構造にする。

---

## 18. 推奨モジュール構成

すべて `src/midi_sampling/sampling` 以下へ配置する。

```text
src/midi_sampling/sampling/
├─ __init__.py
├─ sampling_executor.py
├─ exceptions.py
│
├─ definitions/
│  ├─ __init__.py
│  ├─ zone_layout_definition.py
│  ├─ velocity_profile_definition.py
│  ├─ sampling_definition.py
│  └─ sampling_session_definition.py
│
├─ loading/
│  ├─ __init__.py
│  └─ yaml_definition_loader.py
│
├─ resolving/
│  ├─ __init__.py
│  └─ definition_resolver.py
│
├─ planning/
│  ├─ __init__.py
│  ├─ sampling_target.py
│  ├─ sampling_plan.py
│  └─ sampling_plan_builder.py
│
├─ validation/
│  ├─ __init__.py
│  ├─ semantic_validator.py
│  └─ output_path_validator.py
│
├─ naming/
│  ├─ __init__.py
│  └─ sample_filename_formatter.py
│
├─ hashing/
│  ├─ __init__.py
│  └─ resolved_definition_hasher.py
│
├─ manifest/
│  ├─ __init__.py
│  ├─ sample_manifest.py
│  └─ sample_manifest_repository.py
│
└─ audit/
   ├─ __init__.py
   ├─ audit_result.py
   └─ audit_service.py
```

既存CLIのエントリポイントとの接続コードが別ディレクトリに存在する場合でも、サンプリング仕様の実装本体は上記ディレクトリ以下に置く。

---

## 19. 例外設計

用途別のアプリケーション例外を定義する。

例:

- `DefinitionLoadError`
- `DefinitionValidationError`
- `DefinitionReferenceError`
- `InvalidZoneLayoutError`
- `InvalidVelocityProfileError`
- `DuplicateDefinitionIdError`
- `InvalidFilenameTemplateError`
- `DuplicateOutputFilenameError`
- `InvalidOutputPathError`
- `ExistingOutputError`
- `ManifestReadError`
- `ManifestWriteError`
- `DefinitionHashMismatchError`
- `SamplingExecutionError`

低レベル例外をそのままCLIへ露出しない。CLIではユーザーが修正可能な情報を含むメッセージへ変換する。

---

## 20. ロギング

最低限以下をログへ記録する。

- 読み込んだセッション定義
- 解決した参照ファイル
- 音色IDと総サンプル数
- 現在の音色、root、velocity
- MIDI Program Change
- 録音開始・停止
- WAV一時パスと完成パス
- マニフェスト更新
- 監査判定
- エラー種別

標準出力は進捗と要約を中心にし、詳細はロガーへ送る。

---

## 21. テスト要件

### 21.1 定義モデル

- 正常な各YAMLを読める。
- 未知フィールドを拒否する。
- 型違反を拒否する。
- 値域違反を拒否する。
- `file` とインライン定義の併記を拒否する。

### 21.2 ゾーン意味検証

- `low <= root <= high`
- 重複検出
- 空白許可
- ソートの決定性

### 21.3 ベロシティ意味検証

- 1～127完全被覆
- 重複検出
- 空白検出
- `send` の範囲内制約
- ソートの決定性

### 21.4 参照解決

- 参照元ファイル基準の相対パス
- 存在しないファイル
- 異なる `kind`
- 絶対パス拒否
- 再参照拒否

### 21.5 計画生成

- ゾーン×レイヤーの件数
- 規定順
- ファイル名生成
- 重複ファイル名検出
- 未知プレースホルダー拒否

### 21.6 パス検証

- Windows予約名
- 不正文字
- 空文字
- 末尾ピリオド・空白
- 長すぎるパス
- 重複パス

### 21.7 ハッシュ

- コメント変更で変化しない。
- キー順変更で変化しない。
- ゾーン記述順変更で変化しない。
- プリセットパス変更かつ内容同一で変化しない。
- ゾーン値変更で変化する。
- ベロシティ値変更で変化する。
- MIDI値変更で変化する。
- タイミング変更で変化する。
- オーディオ形式変更で変化する。

### 21.8 マニフェスト

- 初期生成
- サンプル完了更新
- 音色完了更新
- 失敗更新
- 一時ファイルからのアトミック置換
- 途中で例外が発生しても旧マニフェストが壊れない。

### 21.9 WAV出力

実デバイスを使用せず、Fake AudioDevice / Fake MidiDeviceで検証する。

- 呼出し順
- Note On / Off
- 待機時間
- 一時WAVから完成WAVへの置換
- WAV完了後にマニフェストが更新される順序
- エラー後に後続サンプルを実行しない。

### 21.10 Audit

- `up_to_date`
- `missing`
- `definition_changed`
- `incomplete`
- `missing_samples`
- `invalid_manifest`
- 終了コード0 / 1 / 2
- デバイスを開かない。
- ファイルを書き換えない。

---

## 22. 初期実装の受入条件

以下を全て満たした場合、初期実装完了とする。

1. セッションYAMLから複数の音色定義を読み込める。
2. 外部ゾーンプリセットと外部ベロシティプリセットを解決できる。
3. インライン定義も利用できる。
4. 全意味制約を実行前に検証できる。
5. ゾーン×レイヤーのサンプリング計画を規定順で生成できる。
6. 全出力ファイル名を録音前に検証できる。
7. 初期化SMF、Bank Select、Program Change、Note On / Offを規定順で送信できる。
8. WAVを `.part` から完成名へアトミックに確定できる。
9. 音色単位の `manifest.yaml` を自動生成・更新できる。
10. エラー時に直ちにセッション全体を停止できる。
11. 解決済み定義のSHA-256をマニフェストへ保存できる。
12. `audit` が再サンプリング対象を判定できる。
13. 既存出力を暗黙に上書きしない。
14. 実デバイスを使わない単体・結合テストがある。

---

## 23. 初期仕様の対象外・将来対応

- `--resume`
- 既存WAVの自動上書き
- 既存WAVの自動削除
- ラウンドロビン
- 複数テイク
- ゾーンごとに異なるベロシティプロファイル
- 定義継承
- deep merge
- 外部プリセットからの再import
- URL参照
- 絶対パス参照
- 音色定義の直接実行
- エラー後の自動リトライ
- エラー後に次のサンプルへ進むモード
- サンプル単位の差分ハッシュ
- 変更されたゾーンだけの差分再録音
- WAV内容のハッシュ
- `audit --format json`
- 詳細な構造差分表示
- ポストプロセス後の派生マニフェスト
- トリミング・ループ処理とのマニフェスト統合
- KONTAKT `*.nki` 生成
- SFZ生成
- UVI Falcon `*.uvip` 生成

---

## 24. 実装上の禁止事項

- `SamplingExecutor` 内でYAMLを読み込まない。
- `SamplingExecutor` 内で外部参照を解決しない。
- ファイル名からマッピング情報を逆解析する設計にしない。
- マニフェストよりファイル名を正本として扱わない。
- 録音開始後に初めてファイル名重複を検出する設計にしない。
- 完成WAVへ直接書き込まない。
- 既存出力を暗黙に上書きしない。
- Pydanticの暗黙的な型変換へ過度に依存しない。
- YAMLの任意タグまたは任意コード実行を許可しない。
