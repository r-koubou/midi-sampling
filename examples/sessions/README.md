# サンプリングセッション定義サンプル

外部MIDI音源の自動サンプリングに使用する各種定義ファイルのサンプル一式。

## 構成

```text
sessions/
├─ session.yaml                    サンプリングセッション定義(エントリポイント)
├─ devices/
│  ├─ audio_device.yaml            オーディオデバイス定義(既存形式)
│  └─ midi_device.yaml             MIDIデバイス定義(既存形式)
├─ midi/
│  └─ gs_reset.mid                 初期化SMF(GS Reset)
├─ presets/
│  ├─ zones/
│  │  └─ cello.yaml                ゾーンレイアウト定義(kind: zone_layout)
│  └─ velocities/
│     ├─ two_layers.yaml           ベロシティプロファイル定義(kind: velocity_profile)
│     └─ four_layers.yaml
└─ tones/
   ├─ sc8850-cello-1.yaml          音色定義: 外部プリセット参照版
   └─ sc8850-trumpet-1.yaml        音色定義: インライン定義版
```

## 実行方法

```bash
# サンプリング実行
midi-sampling run examples/sessions/session.yaml

# 既存成果物と現在の定義の整合性を監査(読み取り専用)
midi-sampling audit examples/sessions/session.yaml
```

実行すると `output.directory`(このサンプルでは `recorded/`)の下に
音色 `id` ごとのディレクトリが作成され、WAV と `manifest.yaml` が生成される。

```text
recorded/
├─ sc8850-cello-1/
│  ├─ manifest.yaml
│  └─ *.wav
└─ sc8850-trumpet-1/
   ├─ manifest.yaml
   └─ *.wav
```

## 注意

- 既存の出力ディレクトリがある場合、`run` はエラーで停止する(自動上書き・自動再開はしない)。
- 相対パスは、参照を記述したYAMLファイルの所在ディレクトリが基準。
- `devices/` 以下のデバイス名は実際に接続されている機器の名称へ変更すること。
