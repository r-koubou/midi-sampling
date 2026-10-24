# WAV先頭・終端無音トリミングCLI 仕様書

## 1. 目的

サンプリングしたWAVファイルの先頭および終端に含まれる無音相当区間を、高い精度で自動検出して削除するコマンドラインツールをPythonで実装する。

本ツールは、後段で実行されるサスティンループ検出処理の前処理として使用する。

単純な固定dB閾値ではなく、各入力ファイルの先頭・終端に含まれる約1秒の余白から録音系のノイズフロアを推定し、そのノイズフロアを基準として有音区間を検出する。

---

## 2. スコープ

### 2.1 対象

- 入力形式: WAV
- 出力形式: WAV
- モノラルおよびマルチチャンネルWAV
- PCM整数形式およびIEEE Float形式
- 1ファイル単位の処理
- ディレクトリ単位の一括処理
- Windows、macOS、Linux
- Pythonによる実装
- `uv`によるプロジェクトおよび依存関係管理

### 2.2 対象外

- MP3、FLAC、AIFFなどWAV以外の入力
- サスティンループ検出
- クロスフェード生成
- `smpl`チャンクの読み書き、補正、維持
- ピッチ検出
- 楽器種別の自動分類
- ノイズ除去
- 音量ノーマライズ
- リミッター、コンプレッサーなどのダイナミクス処理
- GUI

---

## 3. 前提条件

入力WAVには、ノイズフロア測定用として以下の余白が含まれているものとする。

- 先頭: 約1秒
- 終端: 約1秒

余白には意図的な発音が含まれず、録音系由来のノイズのみが含まれていることを前提とする。

ただし、以下の可能性は考慮すること。

- DCオフセット
- 微小なハム
- オーディオインターフェース由来の定常ノイズ
- サンプリング機材のアナログ出力由来のノイズ
- 左右チャンネル間のノイズ量差
- 短いインパルスノイズ
- MIDI Note On直前の微小ノイズ
- リリース末尾の非常に小さい残響
- アタックが遅いパッド音色
- トレモロやビブラートによる周期的な音量低下

---

## 4. 技術要件

## 4.1 Python

- Python 3.12以上
- 型ヒントを使用する
- `pathlib.Path`を使用する
- データクラスを使用して設定値および検出結果を表現する
- 主要関数にはdocstringを付与する
- 例外を握りつぶさない
- CLI層と信号処理層を分離する

## 4.2 パッケージ管理

`uv`を使用する。

初期化例:

```bash
uv init --package wav-silence-trimmer
```

依存関係の追加例:

```bash
uv add numpy scipy soundfile
uv add --dev pytest pytest-cov
```

## 4.3 外部依存パッケージ

`pyproject.toml`の実行時依存関係には、最低限以下を記述する。

| パッケージ | 用途 |
|---|---|
| `numpy` | 音声配列、RMS、累積和、統計処理 |
| `scipy` | メディアンフィルタ、モルフォロジー処理、連結成分処理 |
| `soundfile` | WAV読み書き、サンプルレート・チャンネル数・サブタイプ取得 |

開発時依存関係:

| パッケージ | 用途 |
|---|---|
| `pytest` | 単体テスト、統合テスト |
| `pytest-cov` | カバレッジ計測 |

CLIには標準ライブラリの`argparse`を使用し、CLIフレームワークへの追加依存は避ける。

## 4.4 `pyproject.toml`例

```toml
[project]
name = "wav-silence-trimmer"
version = "0.1.0"
description = "High-accuracy leading and trailing silence trimmer for sampled WAV files"
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
    "numpy>=2.0",
    "scipy>=1.14",
    "soundfile>=0.13",
]

[project.scripts]
wav-trim = "wav_silence_trimmer.cli:main"

[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

バージョン下限は実装時点で`uv lock`可能な安定版に調整してよい。

---

## 5. プロジェクト構成

```text
wav-silence-trimmer/
├─ pyproject.toml
├─ uv.lock
├─ README.md
├─ src/
│  └─ wav_silence_trimmer/
│     ├─ __init__.py
│     ├─ cli.py
│     ├─ config.py
│     ├─ models.py
│     ├─ detector.py
│     ├─ audio_io.py
│     ├─ fade.py
│     └─ errors.py
└─ tests/
   ├─ test_detector.py
   ├─ test_fade.py
   ├─ test_audio_io.py
   ├─ test_cli.py
   └─ fixtures/
```

### 各モジュールの責務

#### `cli.py`

- コマンドライン引数解析
- 入力パス検証
- 単一ファイル処理
- ディレクトリ一括処理
- 終了コード制御
- ログおよび結果表示

#### `config.py`

- 検出パラメーター
- フェードパラメーター
- 入出力動作設定
- 引数値の妥当性検証

#### `models.py`

- `TrimConfig`
- `TrimResult`
- `AudioMetadata`
- `ProcessingResult`

#### `detector.py`

- DCオフセット除去
- フレームRMS計算
- ノイズフロア推定
- ヒステリシス閾値処理
- 短い無音ギャップの連結
- 有音区間の決定
- サンプル単位境界調整

#### `audio_io.py`

- WAV読み込み
- WAV書き込み
- 元のサブタイプ維持
- 出力先作成
- 上書き制御

#### `fade.py`

- 先頭フェードイン
- 終端フェードアウト
- 全チャンネル同一ゲインカーブ適用

#### `errors.py`

- 独自例外クラス

---

## 6. CLI仕様

## 6.1 コマンド名

```bash
wav-trim
```

## 6.2 単一ファイル

```bash
uv run wav-trim input.wav --output output.wav
```

## 6.3 ディレクトリ一括処理

```bash
uv run wav-trim ./input --output-dir ./output
```

入力ディレクトリ直下の`.wav`および`.WAV`を処理する。

再帰処理はオプション指定時のみ行う。

```bash
uv run wav-trim ./input --output-dir ./output --recursive
```

## 6.4 必須引数

```text
input
```

入力WAVファイルまたは入力ディレクトリ。

## 6.5 出力指定

単一ファイル入力時:

```text
--output PATH
```

ディレクトリ入力時:

```text
--output-dir PATH
```

以下の規則とする。

- 単一ファイル入力では`--output`必須
- ディレクトリ入力では`--output-dir`必須
- 入力ファイルと出力ファイルが同一の場合は、`--overwrite`なしではエラー
- デフォルトでは既存ファイルを上書きしない

## 6.6 検出パラメーター

| オプション | 型 | デフォルト | 説明 |
|---|---:|---:|---|
| `--edge-noise-seconds` | float | `1.0` | 先頭・終端からノイズ推定に使用する秒数 |
| `--frame-ms` | float | `10.0` | RMSフレーム長 |
| `--hop-ms` | float | `2.0` | RMSフレーム移動幅 |
| `--noise-percentile` | float | `20.0` | 端部レベル分布からノイズフロアを求めるパーセンタイル |
| `--on-margin-db` | float | `15.0` | ノイズフロアに加算する開始判定マージン |
| `--off-margin-db` | float | `8.0` | ノイズフロアに加算する継続判定マージン |
| `--minimum-noise-floor-dbfs` | float | `-120.0` | ノイズフロア推定値の下限 |
| `--minimum-on-ms` | float | `10.0` | 開始判定に必要な連続有音時間 |
| `--bridge-gap-ms` | float | `80.0` | 有音として連結する短い無音ギャップ |
| `--pre-roll-ms` | float | `8.0` | 検出開始点より前に残す余白 |
| `--post-roll-ms` | float | `40.0` | 検出終了点より後に残す余白 |

## 6.7 フェードパラメーター

| オプション | 型 | デフォルト | 説明 |
|---|---:|---:|---|
| `--fade-in-ms` | float | `1.0` | 出力先頭に適用するフェードイン |
| `--fade-out-ms` | float | `5.0` | 出力終端に適用するフェードアウト |
| `--no-fade` | flag | false | フェードを適用しない |

## 6.8 動作オプション

| オプション | 説明 |
|---|---|
| `--recursive` | 入力ディレクトリを再帰処理 |
| `--overwrite` | 既存出力を上書き |
| `--dry-run` | 書き込みをせず検出結果のみ表示 |
| `--report-json PATH` | 処理結果をJSONで保存 |
| `--fail-on-no-signal` | 有音検出不能時に処理全体を失敗扱い |
| `--verbose` | 詳細ログ |
| `--quiet` | エラー以外を非表示 |
| `--version` | バージョン表示 |

## 6.9 使用例

```bash
uv run wav-trim input.wav --output output.wav
```

```bash
uv run wav-trim input.wav \
  --output output.wav \
  --edge-noise-seconds 1.0 \
  --on-margin-db 15 \
  --off-margin-db 8 \
  --pre-roll-ms 8 \
  --post-roll-ms 40
```

```bash
uv run wav-trim ./samples \
  --output-dir ./trimmed \
  --recursive \
  --report-json ./trim-report.json
```

```bash
uv run wav-trim input.wav \
  --output output.wav \
  --dry-run \
  --verbose
```

---

## 7. WAV入出力仕様

## 7.1 読み込み

`soundfile.read`を使用する。

```python
audio, sample_rate = sf.read(
    input_path,
    dtype="float64",
    always_2d=True,
)
```

内部処理では必ず次の形状に統一する。

```text
(samples, channels)
```

モノラルも`(samples, 1)`として扱う。

## 7.2 メタデータ

少なくとも以下を読み取る。

- サンプルレート
- チャンネル数
- フレーム数
- WAVサブタイプ
- WAVフォーマット種別

## 7.3 書き込み

基本的に入力のサブタイプを維持する。

```python
sf.write(
    output_path,
    trimmed_audio,
    sample_rate,
    subtype=input_subtype,
    format="WAV",
)
```

### 注意事項

- 本ツールでは`smpl`チャンクを扱わない
- その他の未知チャンクの完全維持は保証対象外
- 音声データ、サンプルレート、チャンネル数、サンプル形式の維持を主要要件とする
- 後段処理が必要なため、出力は必ずWAVとする

---

## 8. 検出アルゴリズム

## 8.1 全体フロー

```text
WAV読み込み
  ↓
解析用コピー作成
  ↓
チャンネルごとのDCオフセット除去
  ↓
短時間RMS計算
  ↓
端部約1秒からノイズフロア推定
  ↓
開始閾値・継続閾値生成
  ↓
開始候補検出
  ↓
弱い有音区間の検出
  ↓
短い無音ギャップを連結
  ↓
開始候補を含む連結成分のみ採用
  ↓
粗い開始・終了位置決定
  ↓
境界周辺の高精度再探索
  ↓
プリロール・ポストロール付加
  ↓
切り出し
  ↓
短いフェード
  ↓
WAV出力
```

---

## 8.2 DCオフセット除去

元音声は変更せず、解析用配列のみDCオフセットを除去する。

各チャンネルについて中央値を減算する。

```python
analysis = audio.astype(np.float64, copy=True)
analysis -= np.median(analysis, axis=0, keepdims=True)
```

平均値ではなく中央値を使用し、発音区間の大振幅による影響を減らす。

出力音声にはDC除去済みデータを使用せず、元の音声データを切り出す。

---

## 8.3 フレームRMS

フレーム長とホップ長をサンプル数に変換する。

```text
frame_length = round(sample_rate × frame_ms / 1000)
hop_length   = round(sample_rate × hop_ms / 1000)
```

フレームごとにチャンネル別RMSを計算する。

```text
RMS = sqrt(mean(x²))
```

各フレームの代表値は、チャンネルRMSの最大値とする。

```text
frame_rms = max(channel_rms)
```

理由:

- 左右どちらか一方に偏った音を保護する
- 片チャンネルだけ長く残る残響を保護する
- チャンネル平均による低レベル化を防ぐ

処理量削減のため、累積和を用いてRMSを計算する。

---

## 8.4 dBFS変換

```text
frame_dbfs = 20 × log10(max(frame_rms, epsilon))
```

`epsilon`は`1e-12`程度とする。

変換後、3フレーム程度のメディアンフィルタを適用し、単発のインパルスノイズの影響を低減する。

```python
filtered_db = scipy.ndimage.median_filter(
    frame_db,
    size=3,
    mode="nearest",
)
```

---

## 8.5 ノイズフロア推定

先頭および終端から、それぞれ`edge_noise_seconds`分のフレームを取得する。

```text
edge_levels =
    first edge_noise_seconds
    +
    last edge_noise_seconds
```

端部データ全体の単純平均は使用しない。

先頭や終端に微小な残響や突発ノイズが混入する可能性があるため、指定パーセンタイルを使用する。

```text
estimated_noise_dbfs =
    percentile(edge_levels, noise_percentile)
```

デフォルト:

```text
noise_percentile = 20
```

最終値:

```text
noise_floor_dbfs =
    max(estimated_noise_dbfs, minimum_noise_floor_dbfs)
```

推定に使用する先頭・終端の長さが入力ファイル長を超える場合は、有効範囲に丸める。

入力が短すぎて先頭区間と終端区間が大きく重複する場合も動作させるが、警告を表示する。

---

## 8.6 ヒステリシス閾値

2種類の閾値を使用する。

```text
threshold_on  = noise_floor_dbfs + on_margin_db
threshold_off = noise_floor_dbfs + off_margin_db
```

デフォルト:

```text
on_margin_db  = 15 dB
off_margin_db = 8 dB
```

必ず次の関係を満たすこと。

```text
on_margin_db > off_margin_db
```

### 開始閾値

明確な発音開始候補を検出するための高い閾値。

### 継続閾値

リリース、残響、トレモロなどの低レベル音を有音区間として維持するための低い閾値。

---

## 8.7 開始候補の検出

`threshold_on`以上のフレームが`minimum_on_ms`以上連続する区間のみ、強い有音候補とする。

単発クリックや短いノイズでは開始しない。

```text
seed_mask =
    frame_dbfs >= threshold_on
    が minimum_on_ms 以上連続
```

強い有音候補が1つもない場合は、有音検出不能とする。

---

## 8.8 弱い有音区間の検出

```text
weak_mask = frame_dbfs >= threshold_off
```

`weak_mask`に対してモルフォロジーのクロージングを適用する。

目的:

- トレモロの谷を埋める
- ビブラートや位相干渉による短い音量低下を埋める
- リバーブ末尾の一時的な閾値下回りを埋める

構造要素の長さ:

```text
bridge_frames = round(bridge_gap_ms / hop_ms)
```

```python
connected_mask = scipy.ndimage.binary_closing(
    weak_mask,
    structure=np.ones(bridge_frames, dtype=bool),
)
```

---

## 8.9 採用する有音区間

`connected_mask`の連結成分をラベリングする。

強い有音候補`seed_mask`を1つ以上含む連結成分だけを採用する。

これにより、端部の定常ノイズや散発ノイズを有音区間として誤採用しにくくする。

複数の有音連結成分がある場合は、最初の採用成分の開始から最後の採用成分の終了までを保持する。

サンプリング用途では、途中の休符を削除してはならない。

---

## 8.10 粗い境界位置

最初の有効フレーム開始位置を粗い開始位置とする。

最後の有効フレーム末尾を粗い終了位置とする。

```text
coarse_start = first_frame_start
coarse_end   = last_frame_start + frame_length
```

---

## 8.11 高精度境界再探索

粗い境界の前後を、より短い窓で再評価する。

### 再探索範囲

デフォルト:

```text
開始側: coarse_startの前後50 ms
終了側: coarse_endの前後100 ms
```

### 再探索窓

- 窓長: 1 ms
- ホップ: 1サンプルまたは0.25 ms以下
- チャンネル代表値: 最大RMS
- 閾値: `threshold_off`

### 開始位置

再探索範囲内で、短時間エネルギーが`threshold_off`を継続的に上回り始める最初の位置を選ぶ。

### 終了位置

再探索範囲内で、短時間エネルギーが`threshold_off`を最後に上回る位置を選ぶ。

### 境界保護

境界位置決定後、以下の余白を追加する。

```text
start = max(0, refined_start - pre_roll)
end   = min(total_samples, refined_end + post_roll)
```

---

## 8.12 ゼロクロス処理

ゼロクロスは補助的にのみ使用する。

理由:

- ステレオ左右でゼロクロス位置が一致しない
- 低周波音ではゼロクロス間隔が長い
- ノイズを含むとゼロクロスが大量に発生する
- ゼロクロスだけでは実質的な無音境界を表せない

採用する場合は、検出境界の近傍数ms内で次のスコアが最小となる位置を選ぶ。

```text
score =
    max(abs(all_channels_at_sample))
    +
    local_energy_weight × local_rms
```

ゼロクロス調整を実装しなくても、短いフェードを必須とすることでクリックを抑制できる。

---

## 8.13 プリロール・ポストロール

デフォルト:

```text
pre_roll_ms  = 8 ms
post_roll_ms = 40 ms
```

目的:

- アタック直前の微小成分を保護
- アタック検出誤差を吸収
- リリース末尾を過剰に切らない
- 後段のループ検出用データを不必要に損なわない

---

## 8.14 フェード

切り出し後の音声に短いフェードを適用する。

デフォルト:

```text
fade_in_ms  = 1 ms
fade_out_ms = 5 ms
```

全チャンネルへ同一ゲインカーブを適用し、ステレオ定位を変化させない。

デフォルトは線形フェードとする。

```text
fade-in:  0 → 1
fade-out: 1 → 0
```

開始または終了位置が元ファイル端と一致し、トリミングされていない場合でもフェードを適用するかどうかは、実装上の設定として明示する。

推奨動作:

- 実際に先頭を削除した場合のみフェードイン
- 実際に終端を削除した場合のみフェードアウト

---

## 9. ノーマライズ方針

検出前の音量ノーマライズは行わない。

理由:

- 信号とノイズが同じ倍率で増幅されるため、信号対雑音比は改善しない
- クリッピングを誘発する可能性がある
- ファイルごとの相対レベル情報を変更する
- 後段処理に意図しない影響を与える

内部計算は`float64`で行い、極端に小さい値でも十分な数値精度を確保する。

---

## 10. 検出結果モデル

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class TrimResult:
    start_sample: int
    end_sample_exclusive: int
    original_frames: int
    output_frames: int
    sample_rate: int
    channels: int
    noise_floor_dbfs: float
    threshold_on_dbfs: float
    threshold_off_dbfs: float
    removed_head_frames: int
    removed_tail_frames: int
    removed_head_seconds: float
    removed_tail_seconds: float
    fade_in_frames: int
    fade_out_frames: int
```

終了位置は排他的境界とする。

```python
trimmed = audio[start_sample:end_sample_exclusive]
```

---

## 11. JSONレポート仕様

`--report-json`指定時、以下の形式で保存する。

```json
{
  "version": 1,
  "files": [
    {
      "input": "input.wav",
      "output": "output.wav",
      "status": "success",
      "sample_rate": 48000,
      "channels": 2,
      "original_frames": 576000,
      "output_frames": 431520,
      "start_sample": 48210,
      "end_sample_exclusive": 479730,
      "removed_head_frames": 48210,
      "removed_tail_frames": 96270,
      "removed_head_seconds": 1.004375,
      "removed_tail_seconds": 2.005625,
      "noise_floor_dbfs": -86.4,
      "threshold_on_dbfs": -71.4,
      "threshold_off_dbfs": -78.4,
      "fade_in_frames": 48,
      "fade_out_frames": 240
    }
  ]
}
```

失敗時:

```json
{
  "input": "input.wav",
  "status": "error",
  "error_type": "NoSignalDetectedError",
  "message": "No valid signal region was detected."
}
```

---

## 12. ログ仕様

通常出力例:

```text
input.wav
  noise floor : -86.4 dBFS
  threshold on: -71.4 dBFS
  threshold off: -78.4 dBFS
  trim head   : 1.004 s
  trim tail   : 2.006 s
  output      : output.wav
```

`--quiet`では成功ログを出力しない。

`--verbose`では以下も出力する。

- 入力サブタイプ
- サンプルレート
- チャンネル数
- フレーム長
- ホップ長
- ノイズ推定対象フレーム数
- 粗い境界
- 再探索後境界
- プリロール・ポストロール適用前後
- フェード長

---

## 13. エラー処理

独自例外を定義する。

```python
class WavTrimmerError(Exception):
    pass


class InvalidInputError(WavTrimmerError):
    pass


class UnsupportedFormatError(WavTrimmerError):
    pass


class NoSignalDetectedError(WavTrimmerError):
    pass


class OutputExistsError(WavTrimmerError):
    pass


class InvalidConfigurationError(WavTrimmerError):
    pass
```

## 13.1 終了コード

| 終了コード | 意味 |
|---:|---|
| `0` | 全処理成功 |
| `1` | 一部または全部のファイル処理失敗 |
| `2` | CLI引数不正 |
| `3` | 入力ファイルまたはディレクトリ不正 |
| `4` | 有音区間検出不能 |
| `5` | 出力書き込み失敗 |

ディレクトリ一括処理では、デフォルトで他ファイルの処理を継続する。

最後に失敗件数が1件以上あれば終了コード`1`とする。

---

## 14. 出力ファイルの安全性

- 一時ファイルへ書き込んだ後、正常終了時に出力先へ置換する
- 書き込み途中で失敗した不完全ファイルを残さない
- `--overwrite`指定時も、入力ファイルを直接破壊しない
- 入力と出力が同じパスの場合は、一時ファイルを使用して原子的に置換する
- 出力ディレクトリが存在しない場合は作成する
- 入力ファイルの相対ディレクトリ構造は、再帰処理時に出力先へ維持する

---

## 15. パフォーマンス要件

精度優先とし、処理時間は厳しく制限しない。

ただし、通常の数秒から数十秒のサンプルWAVに対して、不要な二重ループを避ける。

推奨:

- NumPyベクトル演算
- 累積和によるRMS
- フレーム全体のPythonループ回避
- 高精度再探索は境界近傍に限定
- 入力全体を`float64`でメモリへ展開してよい

非常に長いWAVへのストリーミング対応は将来拡張とする。

---

## 16. テスト要件

## 16.1 単体テスト

以下をテストする。

### RMS計算

- モノラル正弦波
- ステレオで片側のみ発音
- 無音
- 1フレーム未満の入力
- フレーム長の倍数でない入力

### ノイズフロア推定

- 完全無音
- 一定ホワイトノイズ
- 先頭のみ突発ノイズあり
- 終端に短い残響あり
- 左右でノイズ量が異なる
- 端部長が入力長を超える

### 有音判定

- 明確なアタック
- 遅いアタック
- 長いリリース
- トレモロ
- 有音途中に短い無音
- 有音途中に長い無音
- 先頭の単発クリック
- 終端の単発クリック
- 全体が無音
- 全体が有音

### 境界

- 先頭が0未満にならない
- 終端が総フレーム数を超えない
- `start < end`
- プリロール適用
- ポストロール適用
- 排他的終了位置

### フェード

- 先頭値が0に近い
- フェード終端が1に近い
- 終端値が0に近い
- 全チャンネルに同じゲイン
- 短すぎる音声でも例外にならない
- `--no-fade`時に無変更

## 16.2 合成音声テスト

NumPyで以下のWAV相当データを生成する。

```text
1秒ノイズ
+ 0.2秒アタック
+ 2秒サスティン
+ 1秒リリース
+ 1秒ノイズ
```

既知の境界と検出結果の誤差を検証する。

許容誤差の目安:

- 開始境界: ±10 ms以内
- 終了境界: ±30 ms以内
- プリロール・ポストロール適用後は設定値との整合性を検証

## 16.3 実ファイル統合テスト

以下の種類を用意する。

- ピアノ系の短いアタック
- ストリングス系の遅いアタック
- パッド系の長いリリース
- トレモロ音色
- 左右定位の強い音色
- 低ベロシティー音
- 高ベロシティー音
- 録音ノイズが比較的大きいファイル

実ファイルはリポジトリへ含めなくてもよい。ローカル検証手順をREADMEへ記載する。

## 16.4 CLIテスト

- 単一ファイル成功
- ディレクトリ一括成功
- 出力先未指定
- 非WAV入力
- 出力既存
- `--overwrite`
- `--dry-run`
- JSONレポート
- 無音ファイル
- 不正な閾値
- `on_margin_db <= off_margin_db`
- 再帰処理
- 大文字`.WAV`

---

## 17. 受け入れ条件

以下をすべて満たすこと。

1. `uv sync`で環境構築できる
2. `uv run wav-trim --help`が正常に表示される
3. 単一WAVを入力し、トリミング済みWAVを出力できる
4. 入力サンプルレートを維持する
5. 入力チャンネル数を維持する
6. 入力WAVサブタイプを可能な範囲で維持する
7. 先頭・終端それぞれ約1秒の余白からノイズフロアを推定する
8. 固定dBFS閾値だけに依存しない
9. 開始閾値と継続閾値のヒステリシスを使用する
10. 単発ノイズを発音開始として誤検出しにくい
11. 短い音量低下で有音区間が分断されない
12. 遅いアタックを過剰に削らない
13. 長いリリースを過剰に削らない
14. ステレオ片側だけの低レベル成分を保護する
15. プリロールおよびポストロールを付加する
16. 短いフェードを適用できる
17. `smpl`チャンク処理を実装しない
18. 音量ノーマライズを行わない
19. ディレクトリ一括処理が可能
20. `pytest`がすべて成功する

---

## 18. 実装上の推奨デフォルト値

```python
DEFAULT_FRAME_MS = 10.0
DEFAULT_HOP_MS = 2.0
DEFAULT_EDGE_NOISE_SECONDS = 1.0
DEFAULT_NOISE_PERCENTILE = 20.0
DEFAULT_MINIMUM_NOISE_FLOOR_DBFS = -120.0
DEFAULT_ON_MARGIN_DB = 15.0
DEFAULT_OFF_MARGIN_DB = 8.0
DEFAULT_MINIMUM_ON_MS = 10.0
DEFAULT_BRIDGE_GAP_MS = 80.0
DEFAULT_PRE_ROLL_MS = 8.0
DEFAULT_POST_ROLL_MS = 40.0
DEFAULT_FADE_IN_MS = 1.0
DEFAULT_FADE_OUT_MS = 5.0
```

これらはCLI引数で上書き可能とする。

---

## 19. 実装優先順位

### フェーズ1

- プロジェクト初期化
- WAV読み書き
- RMS計算
- ノイズフロア推定
- 粗い境界検出
- 単一ファイルCLI
- 単体テスト

### フェーズ2

- 高精度境界再探索
- フェード
- ディレクトリ一括処理
- JSONレポート
- 詳細ログ
- 統合テスト

### フェーズ3

- パラメーター調整
- 実サンプルでの評価
- README
- エラー処理強化
- 原子的ファイル置換
- カバレッジ改善

---

## 20. READMEに記載すべき内容

- ツールの目的
- `uv`の導入前提
- セットアップ方法
- `uv sync`
- 基本的な使用方法
- 単一ファイル処理
- ディレクトリ一括処理
- 主要パラメーター
- 推奨録音方法
- 先頭・終端に約1秒の無音余白が必要であること
- ノーマライズを行わない理由
- 有音検出不能時の対処
- 遅いアタック音色向け設定例
- 長いリリース音色向け設定例
- `smpl`チャンクを扱わないこと
- 後段でループ検出を行う前処理であること

---

## 21. 推奨録音条件

本ツールへ入力するWAVは、以下の構成を推奨する。

```text
録音開始
  ↓
約1秒の無音余白
  ↓
MIDI Note On
  ↓
発音
  ↓
MIDI Note Off
  ↓
リリースが十分減衰
  ↓
約1秒の無音余白
  ↓
録音終了
```

録音ごとに以下を一定にする。

- サンプリング機材本体の出力レベル
- オーディオインターフェースの入力ゲイン
- ケーブル
- サンプルレート
- ビット深度
- 録音チャンネル構成

---

## 22. 将来拡張候補

今回の実装には含めない。

- ノイズプロファイル専用WAVの指定
- 複数ファイル共通ノイズフロア
- 周波数帯域別ノイズ判定
- スペクトルフラックスによるアタック補助検出
- LUFSベースの補助判定
- GUI
- リアルタイム処理
- FLACおよびAIFF対応
- BWFメタデータ維持
- RIFF未知チャンク完全維持
- サスティンループ検出との統合
- バッチ処理並列化
- 検出結果の波形画像出力

---

## 23. エージェンティックAIへの実装指示

1. 本仕様書を満たすPythonプロジェクトを新規作成すること。
2. `uv`で依存関係を管理すること。
3. 実行時依存は`numpy`、`scipy`、`soundfile`を基本とすること。
4. CLIは標準ライブラリ`argparse`で実装すること。
5. 信号処理ロジックとCLI処理を分離すること。
6. 処理対象はWAVのみとすること。
7. 各入力WAVの先頭・終端約1秒からノイズフロアを推定すること。
8. 固定閾値だけで判定せず、ノイズフロア相対のヒステリシス閾値を使用すること。
9. ステレオ判定ではチャンネルRMSの最大値を使用すること。
10. 途中の休符や音量低下を削除しないこと。
11. 検出後にプリロール、ポストロール、短いフェードを適用すること。
12. 出力音声には解析用DC除去データではなく、元音声の切り出しを使用すること。
13. 音量ノーマライズを行わないこと。
14. `smpl`チャンク関連処理を実装しないこと。
15. 単体テストおよびCLI統合テストを作成すること。
16. `uv run pytest`ですべてのテストが成功する状態にすること。
17. 実装完了後、README、主要設計判断、既知の制約を整理すること。
18. 実装中に仕様と異なる判断が必要になった場合は、理由を明記し、最小限の変更に留めること。
