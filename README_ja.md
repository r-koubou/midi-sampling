midi-sampling
================


## 概要

`midi-sampling`は外部のMIDI音源からサンプリングを行います。
任意のMIDIノート・ベロシティを指定して、MIDIデバイスを制御し、サンプリングを行います。

コンソールベースで動作するため、軽量でサンプリングの自動化が可能です。

## 動作に必要なもの

- Python 3.12 以上が動作する Windows OS
  - macOSでも動作すると思いますが、未検証です
- [pipenv](https://github.com/pypa/pipenv)
- [ffmpeg](https://www.ffmpeg.org/)

## セットアップ

### pipenvのインストール

https://github.com/pypa/pipenv?tab=readme-ov-file#installation

### 依存パッケージのインストール

プロジェクトのディレクトリに移動し、以下のコマンドを実行します。

```bash
pipenv install
```

### ffmpegのインストール

https://www.ffmpeg.org/download.html

インストール後、環境変数 `PATH` に ffmpeg.exe があるディレクトリを追加してください。

## 実行方法

### pipenv 環境の有効化

プロジェクトのディレクトリに移動し、以下のコマンドを実行します。

```bash
pipenv shell
```

以下のように `(midi-sampling)` というプロンプトが左側に表示されていれば、pipenv環境内です。

```bash
(midi-sampling) C:\Path\To\Project\midi-sampling>
~~~~~~~~~~~~~~~
```

### サンプリングの実行

以下のコマンドを実行します。

```bash
python python midisampling/sampling.py <サンプリング設定ファイル.json> <MIDI設定ファイル.json>
```

### デバイス一覧の出力

以下のコマンドを実行します。

```bash
python python midisampling/devicelist.py
```

#### 出力例

```bash
+------------------------------------------------------+
|                    Audio Devices                     |
+--------------------------------+---------------------+
| Name                           | Platform            |
+--------------------------------+---------------------+
| Line(Steinberg UR28M)          | Windows WDM-KS      |
| Microsoft Sound Mapper - Input | MME                 |
| Primary Sound Capture Driver   | Windows DirectSound |
| UR28M In (Steinberg UR28M)     | MME                 |
| UR28M In (Steinberg UR28M)     | Windows DirectSound |
| UR28M In (Steinberg UR28M)     | Windows WASAPI      |
| Yamaha Steinberg USB ASIO      | ASIO                |
+--------------------------------+---------------------+
+------------------------------+
|         MIDI Devices         |
+------------------------------+
| Name                         |
+------------------------------+
| Impact GX Mini               |
| Microsoft GS Wavetable Synth |
| MIDIOUT2 (Impact GX Mini)    |
| Roland SC-8850 MIDI OUT 1    |
| Roland SC-8850 MIDI OUT 2    |
| Roland SC-8850 PART A        |
| Roland SC-8850 PART B        |
| Roland SC-8850 PART C        |
| Roland SC-8850 PART D        |
+------------------------------+
```

## 設定ファイル

サンプルとして、sampling-config.json と midi-config.example.json が同梱されています。
お使いの環境に合わせて設定してください。

### サンプリング設定ファイル

json形式で記述します。

```json
{
    "audio_channels": 2,
    "audio_sample_rate": 48000,
    "audio_sample_bits": 32,
    "audio_sample_bits_format": "int",
    "audio_in_device": {
        "name": "Yamaha Steinberg USB ASIO",
        "platform": "ASIO"
    },
    "asio_audio_ins": [
        2, 3
    ],
    "midi_out_device": "Roland SC-8850 PART A",
    "target_peak": -8,
    "trim_threshold": -60,
    "trim_min_silence_duration": 250
}
```

- `audio_channels`
  - サンプリングする音声ファイルのチャンネル数
- `audio_sample_rate`
  - サンプリングする音声ファイルのサンプリングレート
- `audio_sample_bits`
  - サンプリングする音声ファイルのビット深度
- `audio_sample_bits_format`
  - サンプリングする音声ファイルのビット深度のフォーマット (`int` or `float`)
- `audio_in_device`
  - `name`
    - サンプリングする音声ファイルの入力デバイス名
  - `platform`
    - サンプリングする音声ファイルの入力デバイスのプラットフォーム (例： `ASIO`, `MME`, `Windows DirectSound`, `Windows WASAPI`, `Core Audio` など)
  - `デバイスの一覧出力`のコマンドを実行して、使用するデバイス名、プラットフォームを指定してください
- `asio_audio_ins` (ASIOデバイス使用時)
  - ASIOの入力チャンネル番号のリスト
  - お使いのデバイスの入力チャンネル番号を指定してください。0から始まる形式です。(例えば入力1と入力2を使用する場合、`[0, 1]` と指定)
- `midi_out_device`
  - サンプリングする音源のMIDIデバイス名
  - `デバイスの一覧出力`のコマンドを実行して、使用するデバイス名を指定してください
- `target_peak`
  - サンプリングする音声ファイルのピークレベル (dB)
  - サンプリングしたファイル全体を通したピークレベルを元にノーマライズを行います
- `trim_threshold`
  - 無音部分をトリムする閾値 (dB)
- `trim_min_silence_duration`
  - 無音部分をトリムする最小の無音長 (ms)

### MIDI設定ファイル

json形式で記述します。

```json
{
    "output_dir": "_recorded",
    "processed_output_dir": "_recorded/_processed",
    "output_prefix": "piano",
    "midi_channel": 0,
    "midi_notes": [
        40
    ],
    "midi_velocities": [
        127
    ],
    "midi_pre_wait_duration": 0.6,
    "midi_note_duration": 2,
    "midi_release_duration": 1.5
}
```

- `output_dir`
  - サンプリングした音声ファイルの出力ディレクトリ
- `processed_output_dir`
  - サンプリングした音声ファイルの加工後の出力ディレクトリ
- `output_prefix`
  - サンプリングした音声ファイルのファイル名のプレフィックス
- `midi_channel`
  - サンプリングするMIDIチャンネル番号 (`0`-`15`)
- `midi_notes`
  - サンプリングするMIDIノート番号のリスト (`0`-`127`)
- `midi_velocities`
  - サンプリングするMIDIベロシティのリスト (`0`-`127`)
- `midi_pre_wait_duration`
  - サンプリング前の待機時間 (秒)
  - 0.6以上を推奨
- `midi_note_duration`
  - サンプリングするMIDIノートの長さ (秒)。 整数のみ指定可能
- `midi_release_duration`
  - サンプリングするMIDIノートのリリース後の待機時間 (秒)。 整数のみ指定可能