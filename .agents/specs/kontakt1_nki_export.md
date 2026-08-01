# KONTAKT 1 NKI エクスポート仕様

## 1. 概要

`--format nki` で KONTAKT 1 形式の `.nki` パッチを生成する。
ファイル形式の基礎調査は
`.agents/specs/research_kontakt_v1_nki_file_format.md` を参照。
XML の細部（version 属性、パラメーター順序、改行コード）は
`examples/kontakt/example_kontakt_v1.nki`（KONTAKT 1 実ファイル）を
テンプレートとして踏襲する。

出力レイアウトは SFZ と同一（`export_implementation.md` §7.1）:

```
patches/nki/
├── Instruments/<instrument name>.nki
└── Samples/<tone_id>/<stem>.wav
```

ゾーンの `file` 値は NKI からの相対パス `..\Samples\<tone_id>\<stem>.wav` になる。
これは NI 純正ライブラリと同じ `Instruments/` + `Samples/` 構成である。
`..` を含む相対パスが正しく解決されることは実機で確認済み（2026-07-31）。

定義ファイルの `output.subdirectory` を指定すると NKI は
`Instruments/<subdirectory>/<instrument name>.nki` へ出力され、`file` 値の `..\`
が階層数ぶん増える（例: `8850/Piano` なら `..\..\..\Samples\...`）。
多階層でも実機で解決されることは確認済み（2026-08-01）。
`<NiSS_Program name>`（KONTAKT のラック表示名）は常に定義の `name` そのままで、
ディレクトリ構造は混ざらない。

## 2. モジュール構成

```
src/midi_sampling/export/nki_impl/
├── __init__.py            NkiPatchWriter を re-export
├── nki_patch_writer.py    NkiPatchWriter(InstrumentPatchWriter)
├── nki_grouping.py        KontaktGroup + partition_groups()（純関数）
├── nki_xml.py             render_program() / エスケープ / version 定数
├── nki_binary.py          36 バイトヘッダー + zlib 圧縮
└── wav_info.py            RIFF スキャン（frame_count / data チャンクサイズ）
```

- `NkiPatchWriter.supported_audio_formats == ("wav",)`。
  `ExportPlanBuilder.build(..., supported_audio_formats=...)` が非対応
  フォーマット（flac）を検出すると警告ログを出して wav へフォールバックする。
- ヘッダー `0x1C` のサンプルデータ量とゾーンの `sampleEnd` は、
  executor が先に書き出した WAV（`patch_directory / region.sample_path` で解決）を
  `wav_info.read_wav_data_info()` で走査して得る（stdlib のみ、`wave`
  モジュールは float PCM を拒否するため不使用）。

## 3. バイナリヘッダー

`struct.pack("<4sIHH6I", ...)` で 36 バイト:

| フィールド | 値 |
|---|---|
| magic | `5E E5 6E B3` |
| 0x04 | `0x24` |
| 0x08 | `0x0050` |
| 0x0A | `2`（実ファイル準拠） |
| 0x0C / 0x10 | `0` |
| 0x14 | `1` |
| 0x18 | Unix 時刻（writer に注入可能な clock から取得） |
| 0x1C | 参照ユニーク WAV の `data` チャンクサイズ合計（u32 クランプ + 警告） |
| 0x20 | `0` |

続けて XML（UTF-8、CRLF、末尾改行なし）を `zlib.compress` した
ストリームを連結する。

## 4. Group 分割（nki_grouping.py）

Region のキー `(exclusive_group, release_key)`（`release_key` は
`trigger=="release"` のとき `tone_id`、それ以外 `None`）で NiSS_Group へ
分割する。

| キー | Group 名 | voiceGroup | releaseTrigger |
|---|---|---|---|
| `(None, None)` | `default`（常に index 0、空でも出力） | -1 | no |
| `(eg, None)` | `exec_%02d`（eg.number−1） | VoiceGroup index | no |
| `(None, tone)` | `release_%02d`（初出順採番） | -1 | yes |
| `(eg, tone)` | `exec_%02d_release_%02d` | VoiceGroup index | yes |

- Group index は default=0、以降 regions 初出順。
- Zone は `groupIdx` で所属 Group を参照し、regions の順序を維持する。
- release tone_id ↔ ReleaseTriggerDefinition の 1:1 は
  InstrumentDefinition のバリデーター（plays 重複禁止）が保証する。

### 排他（Voice Group）の表現

KONTAKT 1 では排他は Program 直下 `Polyphony` の `VoiceGroup` 要素で
表現し、NiSS_Group の `voiceGroup` パラメーターはそのインデックス参照
（-1 = インストゥルメント既定）である（実ファイルで確認）。

- index 0: 既定 `&lt;instrument>`（maxNumVoices=128、実ファイル準拠）
- index 1..N: exclusive_group ごとに 1 つ。
  `name` = 定義の group 名、`mode=kill_oldest`、`preferReleased=yes`、
  `maxNumVoices=1`、`msFadeTime=10`、`exclusionGroup=-1`。
  maxNumVoices=1 により同一 VoiceGroup 内の新しいノートが古いノートを
  消音する（= choke）。

## 5. XML（nki_xml.py）

- 手書き文字列組み立て（SFZ writer と同方式）。改行 CRLF、
  インデントはネスト 1 段 = 半角スペース 2。
- エスケープは `&` → `<` → `>` → `"` → `'` の順に置換。
- version 属性・固定値は実ファイルから採録しモジュール定数に集約:
  `NiSS_Program=0.50` / `VoiceGroup=0.60` / `NiSS_Group=0.60` /
  `NiSS_Zone=0.60` / `NiSS_IntMod=0.50` / `NiSS_ExtMod=0.80` /
  `Envelope=0.60` / FX スタブ各種。
- Program パラメーターと Group 配下の
  `PlayPosOffset/LoopOffset/SendLevels/GroupStart/Grain/ExtModulators`
  は実ファイルの値を固定で複製する（masterVolume=0.5 も実ファイル準拠）。
- **NiSS パーサは要素を固定順で逐次読みし、既知スロットの省略は
  `ERROR parsing input file at line N: <syntax error>` になる**
  （2026-07-30 実機確認。FX スタブ削除ビルドが行 31 = 本来 `FXDelay`
  がある位置の `<Groups>` で失敗）。したがって Program 直下の FX
  スタブ 12 種、Group の `Filter` と FX スタブ 6 種は必ず出力する。
  エフェクトとして使わない意図は「空要素のまま」（FX スタブ）と
  「`bypass=yes`」（Filter）で表現する。
- Group の `selectedForEdit` は index 0 のみ `yes`。

### エンベロープ

Group ごとに `IntModulators` に volume の `NiSS_IntMod` を 1 つ出力する
（実ファイルにあった filterCutoff / pitch のスロットは実機フィードバック
により不要と判断し出力しない）。AHDSR は InstrumentModel を反映する:

| パラメーター | 値 |
|---|---|
| atkCurving | 0 |
| attack | `envelope.attack × 1000`（ミリ秒、小数 6 桁） |
| decay | 500.0 ms |
| hold | 0.0 ms |
| release | `envelope.release × 1000`（ミリ秒、小数 6 桁） |
| sustain | 1.0（リニア = 0.0 dB） |

filterCutoff / pitch の AHDSR は intensity=0 の中立値。

### Zone

実ファイルのパラメーター順で出力。動的な値:

| パラメーター | ソース |
|---|---|
| sampleStart | 0 |
| sampleEnd | WAV の実フレーム数（実ファイルは 0 だったが省略とみなす） |
| low/highVelocity, low/highKey, rootKey | InstrumentRegion |
| Sample file | `sample_path` の `/` → `\` 変換 + XML エスケープ |

`slicerSens` / `sourceZoneIdx` / `mRetriggerInfo.*` 等は実ファイルの
既定値を固定出力する。

### ループ

- ループなし: `<Loops/>`（空要素、実ファイル準拠）
- ループあり（研究文書 §13 準拠、実ファイルに例が無いため version=0.60 は推定）:

| パラメーター | 値 |
|---|---|
| loopStart | `RegionLoop.start_frame` |
| loopLength | `end_frame − start_frame + 1`（end は inclusive） |
| loopCount | 0（無限と解釈） |
| mode | `until_end` |
| alternatingLoop | no |
| loopTuning | 1（周波数比。ニュートラル = 1.0） |
| xfadeLength | 0 |

`loopTuning` は他の tune 系と同じ周波数比で格納される。0 を書いた場合
KONTAKT は Tune -12 semitone として読み込み、サスティンループが機能
しなくなることを実機で確認済み（2026-07-30）。

## 6. 制限・警告

| 条件 | 挙動 |
|---|---|
| `audio.format: flac` | 警告ログを出して wav で出力（builder 層） |
| `rt_decay` 指定あり | 警告ログを出して無視（KONTAKT 1 に相当機能なし） |

## 7. 実機確認の結果（2026-07-30）

実 KONTAKT でロード・演奏可能なことを確認済み。判明した事項:

- `sampleEnd` = 実フレーム数は正しく解釈される（Wave Editor の S.End と一致）
- ループの `Loop` 要素構造（version=0.60 含む）は読み込まれる
- `loopTuning=0` はサスティンループを壊す → 1（周波数比ニュートラル）へ修正
- filterCutoff / pitch のモジュレーションスロットは不要 → 出力から削除
  （`IntModulators` 内のインデックス付き要素は可変個数を許容すると推定）
- FX 要素の**完全削除はパーサエラーになる**（§5 参照）→ スロットは
  復元し、Filter は `bypass=yes` で不活性化

最終構成（FX スロット復元 + volume のみの IntModulators + loopTuning=1）で
ロード・サスティンループの動作を実機確認済み（2026-07-30）。
`IntModulators` 内のインデックス付き要素の可変個数は許容されることが
確定した。
