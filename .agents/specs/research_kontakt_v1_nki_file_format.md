# KONTAKT 1 NKI ファイルフォーマット

## 1. 文書の範囲

本書は、暗号化されていない Native Instruments KONTAKT 1 形式の `*.nki` ファイルについて、ファイルフォーマットとして確認されている情報だけを整理する。

対象:

- NKIファイル全体のバイナリ配置
- ファイル識別子
- 固定長ヘッダー
- ZLIB圧縮されたXML領域
- XML内の基本的なインストゥルメント構造
- Zone、Sample、Loopに格納される主要情報
- Group内部モジュレーターとして記述されるAHDSRエンベロープ

対象外:

- アプリケーションやライブラリ固有の内部モデル
- 外部変換ツール固有のXMLテンプレート
- 外部ツールが設定する既定値
- クラス構成、CLI、API、処理フロー
- ディレクトリ構造
- KONTAKT 2以降
- 暗号化されたPlayerライブラリ
- モノリス形式
- NKMなどNKI以外の形式

Native Instrumentsによる完全な公式バイナリ仕様またはXML Schemaは公開されていないため、不明なフィールドは不明として扱う。

---

## 2. ファイル全体の構造

KONTAKT 1 NKIは、固定長バイナリヘッダーと、その直後に配置されたZLIBストリームで構成される。

```text
+-----------------------------------+
| 固定長バイナリヘッダー            |
| 36 bytes / 0x24 bytes             |
+-----------------------------------+
| ZLIB圧縮されたXML                 |
| 可変長                            |
+-----------------------------------+
```

ZLIB展開後のデータは、インストゥルメント、Group、Zone、サンプル参照、ループなどを記述したXMLである。

ZLIBは圧縮方式であり、暗号化ではない。

---

## 3. ファイル識別子

KONTAKT 1 NKIでは、先頭4バイトにファイル識別子が置かれる。

### 3.1 確認されている識別子

| バイトオーダー | 先頭4バイト |
|---|---|
| little-endian形式 | `5E E5 6E B3` |
| big-endian形式 | `B3 6E E5 5E` |

整数として表現する場合、読み取り側のエンディアンによって値の見え方が変わるため、判定には実際の4バイト列を使用する。

本書では、次の先頭バイト列を持つlittle-endian形式を中心に記述する。

```hex
5E E5 6E B3
```

---

## 4. 固定長ヘッダー

ヘッダー長は36バイト、すなわち `0x24` バイトである。

### 4.1 little-endian形式のヘッダー配置

| オフセット | サイズ | 型 | 内容 | 確認されている値・意味 |
|---:|---:|---|---|---|
| `0x00` | 4 | byte[4] | NKI識別子 | `5E E5 6E B3` |
| `0x04` | 4 | uint32 LE | 圧縮データ開始位置 | 通常 `0x00000024` |
| `0x08` | 2 | uint16 LE | ヘッダーバージョン | 通常 `0x0050` |
| `0x0A` | 2 | uint16 LE | 不明 | `0x0001` または `0x0002` が確認されている |
| `0x0C` | 4 | uint32 LE | 不明 | 通常 `0` |
| `0x10` | 4 | uint32 LE | 不明 | 通常 `0` |
| `0x14` | 4 | uint32 LE | 不明 | 通常 `1` |
| `0x18` | 4 | uint32 LE | 時刻情報 | Unix時刻の秒として解釈される |
| `0x1C` | 4 | uint32 LE | 参照サンプルのデータ量 | 32bit符号なし整数 |
| `0x20` | 4 | uint32 LE | 不明 | 通常 `0` |
| `0x24` | 可変 | byte[] | ZLIBストリーム | 展開後はXML |

### 4.2 代表的なヘッダーのバイト配置

```text
Offset  Bytes
------  -----------------------------------------------
00      5E E5 6E B3
04      24 00 00 00
08      50 00
0A      01 00
0C      00 00 00 00
10      00 00 00 00
14      01 00 00 00
18      TT TT TT TT   時刻情報
1C      SS SS SS SS   サンプルデータ量
20      00 00 00 00
24      78 ..          ZLIBストリーム
```

`TT TT TT TT` と `SS SS SS SS` はlittle-endianで格納される可変値である。

ZLIBストリームは一般に `0x78` から始まるが、後続バイトは圧縮設定によって異なる。

---

## 5. オフセット `0x1C` のサンプルデータ量

オフセット `0x1C` の値は、NKIが参照するサンプルデータの総量を表す。

確認されている解釈では、WAVファイル全体のファイルサイズではなく、各WAV内のオーディオデータ部分の合計である。

RIFF/WAVEの場合、通常は各ファイルの `data` チャンクのペイロードサイズを合計する。

```text
sample_data_size =
    sample_1 の data チャンクサイズ
  + sample_2 の data チャンクサイズ
  + ...
```

次のデータは通常、この合計には含まれない。

- RIFFヘッダー
- `fmt ` チャンク
- `smpl` チャンク
- `LIST` チャンク
- その他のメタデータチャンク
- RIFFチャンク境界のパディング

このフィールドは32bit符号なし整数である。

---

## 6. 圧縮XML領域

### 6.1 圧縮方式

オフセット `0x24` から、ZLIB形式の圧縮ストリームが始まる。

```text
NKI
  ├─ 36-byte header
  └─ ZLIB stream
       └─ XML
```

これは次の形式とは異なる。

- GZIP
- ヘッダーなしのraw Deflate
- 暗号化データ

### 6.2 XMLの文字コード

展開後のXMLはテキストデータである。

一般に次のXML宣言が使用される。

```xml
<?xml version="1.0"?>
```

文字コードはUTF-8として扱われる。

公式XML Schemaは公開されていない。

---

## 7. XMLの基本モデル

KONTAKT 1のXMLでは、インストゥルメントをProgramとして表し、その配下にGroupとZoneを持つ。

概念上の階層は次のとおり。

```text
Program
├─ Program parameters
├─ Groups
│  ├─ Group 0
│  ├─ Group 1
│  └─ ...
└─ Zones
   ├─ Zone 0
   ├─ Zone 1
   └─ ...
```

ZoneはGroupをインデックスで参照する。

各Zoneは、少なくとも次の種類の情報を保持できる。

- 所属Group
- キー範囲
- ベロシティ範囲
- ルートキー
- 再生開始位置
- 再生終了位置
- 音量
- パン
- チューニング
- サンプルファイル参照
- ループ情報

---

## 8. XML要素名

KONTAKT 1 XMLで確認されている主要な要素名は次のとおり。

| 意味 | XML要素名 |
|---|---|
| Program | `NiSS_Program` |
| Group集合 | `Groups` |
| Group | `NiSS_Group` |
| Zone集合 | `Zones` |
| Zone | `NiSS_Zone` |
| パラメーター集合 | `Parameters` |
| 汎用パラメーター値 | `V` |
| Sample情報 | `Sample` |
| Loop集合 | `Loops` |
| Loop | `Loop` |

パラメーターは一般に、`V` 要素の `name` 属性と `value` 属性で表現される。

```xml
<V name="parameterName" value="parameterValue"/>
```

数値もXML上では属性値の文字列として格納される。

---

## 9. Program

単一インストゥルメントのXMLでは、`NiSS_Program` がProgramを表す。

```xml
<NiSS_Program
    index="0"
    name="Instrument Name"
    version="...">

  <Parameters>
    ...
  </Parameters>

  <Groups>
    ...
  </Groups>

  <Zones>
    ...
  </Zones>
</NiSS_Program>
```

確認されている主要属性:

| 属性 | 意味 |
|---|---|
| `index` | Programのインデックス |
| `name` | Program名 |
| `version` | XML要素のバージョン |

Programのパラメーターとして確認されている主な項目:

| パラメーター | 意味 |
|---|---|
| `midiChannel` | MIDIチャンネル |
| `transpose` | 移調 |
| `masterVolume` | Program全体の音量 |
| `masterPan` | Program全体のパン |
| `masterTune` | Program全体のチューニング |
| `lowVelocity` | Program全体の最低ベロシティ |
| `highVelocity` | Program全体の最高ベロシティ |
| `lowKey` | Program全体の最低キー |
| `highKey` | Program全体の最高キー |

これらの項目の必須性および省略時の既定値は、公式仕様では確認できない。

---

## 10. Group

Groupは `Groups` の子要素として格納される。

```xml
<Groups>
  <NiSS_Group
      index="0"
      name="Group Name"
      version="...">

    <Parameters>
      ...
    </Parameters>
  </NiSS_Group>
</Groups>
```

確認されている主要属性:

| 属性 | 意味 |
|---|---|
| `index` | Groupの0基準インデックス |
| `name` | Group名 |
| `version` | XML要素のバージョン |

Groupのパラメーターとして確認されている主な項目:

| パラメーター | 意味 |
|---|---|
| `volume` | Group音量 |
| `pan` | Groupパン |
| `tune` | Groupチューニング |
| `keyTracking` | キートラッキング |
| `reverse` | 逆再生 |
| `releaseTrigger` | リリーストリガー |
| `voiceGroup` | ボイスまたは排他Group |
| `midiChannel` | Group単位のMIDIチャンネル |
| `output` | 出力先 |

これらの項目の必須性、値域、既定値は、公式仕様では確認できない。

---

## 11. AHDSRエンベロープ

### 11.1 サポート状況

KONTAKT 1はAHDSRエンベロープをサポートする。

ここでいうAHDSRは次の5段階を指す。

```text
Attack
Hold
Decay
Sustain
Release
```

KONTAKT 1のNiSS XMLでは、AHDSRは単独のZoneパラメーターとしてではなく、Group配下の内部モジュレーターとして記述される形式が確認されている。

概念上の階層:

```text
NiSS_Group
└─ IntModulators
   └─ NiSS_IntMod
      └─ Envelope type="ahdsr"
```

モジュレーターの `target` によって、エンベロープが制御する対象を指定する。

確認されている主な対象:

| `target` の値 | 制御対象 |
|---|---|
| `volume` | 音量 |
| `pitch` | ピッチ |
| `filterCutoff` | フィルター・カットオフ |

### 11.2 XML書式

AHDSRを含む内部モジュレーターの基本書式は次のとおり。

```xml
<IntModulators>
  <NiSS_IntMod index="0" version="...">
    <V name="target" value="volume"/>
    <V name="intensity" value="..."/>
    <V name="bypass" value="no"/>
    <V name="retrigger" value="yes"/>

    <Envelope type="ahdsr" version="...">
      <V name="atkCurving" value="..."/>
      <V name="attack" value="..."/>
      <V name="hold" value="..."/>
      <V name="decay" value="..."/>
      <V name="sustain" value="..."/>
      <V name="release" value="..."/>
    </Envelope>
  </NiSS_IntMod>
</IntModulators>
```

XML内での要素順序は実ファイルや保存バージョンによって異なる可能性がある。処理側では、`V` 要素の出現順ではなく `name` 属性でパラメーターを識別する。

### 11.3 `NiSS_IntMod` の属性

| 属性 | 意味 |
|---|---|
| `index` | 内部モジュレーターの0基準インデックス |
| `version` | モジュレーター要素のフォーマットバージョン |

### 11.4 内部モジュレーターのパラメーター

| パラメーター | 意味 |
|---|---|
| `target` | エンベロープの制御対象 |
| `intensity` | 対象へ適用する深度 |
| `bypass` | モジュレーターのバイパス状態 |
| `retrigger` | Note On時にエンベロープを再トリガーするか |

確認されている真偽値文字列:

```text
yes
no
```

`intensity` の正確な値域と、対象ごとのスケーリング規則は公式仕様では確認できない。

### 11.5 `Envelope` の属性

| 属性 | 意味 |
|---|---|
| `type` | エンベロープ種別。AHDSRでは `ahdsr` |
| `version` | Envelope要素のフォーマットバージョン |

### 11.6 AHDSRパラメーター

| パラメーター | 意味 |
|---|---|
| `atkCurving` | Attack区間のカーブ形状 |
| `attack` | Attack時間 |
| `hold` | Hold時間 |
| `decay` | Decay時間 |
| `sustain` | Sustainレベル |
| `release` | Release時間 |

公開されている解析実装では、`attack`、`hold`、`decay`、`release` はミリ秒単位として扱われている。

ただしNative Instrumentsの公式仕様が公開されていないため、次は未確定事項として扱う。

- 各時間値の厳密な有効範囲
- 浮動小数点または整数のどちらを必須とするか
- `atkCurving` の厳密な値域と曲線変換式
- `sustain` の全有効範囲
- 対象ごとの `intensity` の値域
- `version` 属性の必須値

### 11.7 音量AHDSRの構造例

次は、音量を対象にしたAHDSRの構造例である。値は書式説明用であり、KONTAKT 1の公式な既定値を意味しない。

```xml
<IntModulators>
  <NiSS_IntMod index="0" version="0.50">
    <V name="target" value="volume"/>
    <V name="intensity" value="1.0"/>
    <V name="bypass" value="no"/>
    <V name="retrigger" value="yes"/>

    <Envelope type="ahdsr" version="0.60">
      <V name="atkCurving" value="0.0"/>
      <V name="attack" value="10.0"/>
      <V name="hold" value="0.0"/>
      <V name="decay" value="200.0"/>
      <V name="sustain" value="0.8"/>
      <V name="release" value="500.0"/>
    </Envelope>
  </NiSS_IntMod>
</IntModulators>
```

この例が表す概念:

```text
Attack  = 10 ms
Hold    = 0 ms
Decay   = 200 ms
Sustain = 0.8
Release = 500 ms
```

数値は例示にすぎず、互換性を保証する既定値ではない。

### 11.8 複数エンベロープ

同一Groupの `IntModulators` 内に、対象の異なる複数の `NiSS_IntMod` を格納できる形式が確認されている。

```xml
<IntModulators>
  <NiSS_IntMod index="0" version="...">
    <V name="target" value="volume"/>
    ...
    <Envelope type="ahdsr" version="...">
      ...
    </Envelope>
  </NiSS_IntMod>

  <NiSS_IntMod index="1" version="...">
    <V name="target" value="filterCutoff"/>
    ...
    <Envelope type="ahdsr" version="...">
      ...
    </Envelope>
  </NiSS_IntMod>

  <NiSS_IntMod index="2" version="...">
    <V name="target" value="pitch"/>
    ...
    <Envelope type="ahdsr" version="...">
      ...
    </Envelope>
  </NiSS_IntMod>
</IntModulators>
```

各 `index` は同じ `IntModulators` 内で重複させない。

### 11.9 Zoneとの関係

AHDSR内部モジュレーターはGroup配下に置かれるため、そのGroupを参照するZone群へ共通して作用する構造となる。

```text
NiSS_Group index="0"
├─ volume AHDSR
├─ pitch AHDSR
└─ filterCutoff AHDSR

NiSS_Zone groupIdx="0"
NiSS_Zone groupIdx="0"
NiSS_Zone groupIdx="0"
```

Zoneごとに異なるAHDSRを使用する場合は、AHDSR設定の異なるGroupへZoneを分ける構造が必要になる。

### 11.10 未確認事項

次の点は、公開された正式仕様がないため断定できない。

- `IntModulators` を完全に省略した場合の全リビジョンでの挙動
- `Envelope` の子 `V` 要素の厳密な順序制約
- AHDSR以外の全エンベロープ種別
- 1つの `NiSS_IntMod` に複数のEnvelopeを置けるか
- Zone直下またはProgram直下へのEnvelope配置が許されるか
- バージョン間での値スケール変更

## 12. Zone

Zoneは `Zones` の子要素として格納される。

```xml
<Zones>
  <NiSS_Zone
      index="0"
      groupIdx="0"
      version="...">

    <Parameters>
      ...
    </Parameters>

    <Loops>
      ...
    </Loops>

    <Sample>
      ...
    </Sample>
  </NiSS_Zone>
</Zones>
```

### 11.1 Zone属性

| 属性 | 意味 |
|---|---|
| `index` | Zoneの0基準インデックス |
| `groupIdx` | 所属するGroupのインデックス |
| `version` | XML要素のバージョン |

### 11.2 Zoneパラメーター

確認されている主要パラメーター:

| パラメーター | 意味 |
|---|---|
| `sampleStart` | サンプル再生開始位置 |
| `sampleEnd` | サンプル再生終了位置 |
| `lowVelocity` | 最低ベロシティ |
| `highVelocity` | 最高ベロシティ |
| `lowKey` | 最低MIDIノート |
| `highKey` | 最高MIDIノート |
| `fadeLowVelo` | 低ベロシティ側クロスフェード |
| `fadeHighVelo` | 高ベロシティ側クロスフェード |
| `fadeLowKey` | 低音側キークロスフェード |
| `fadeHighKey` | 高音側キークロスフェード |
| `rootKey` | ルートキー |
| `zoneVolume` | Zone音量 |
| `zonePan` | Zoneパン |
| `zoneTune` | Zoneチューニング |

キーとベロシティの一般的なMIDI値域:

| 項目 | 値域 |
|---|---:|
| MIDIノート | `0`～`127` |
| ベロシティ | `1`～`127` |

`sampleStart`、`sampleEnd`、各クロスフェード値の単位や終端包含・排他の厳密な定義は、公式仕様では確認できない。

---

## 13. Sample参照

Zoneが使用するサンプルファイルは、`Sample` 要素内に格納される。

確認されている形式:

```xml
<Sample>
  <V name="file" value="Samples\C4.wav"/>
</Sample>
```

主要な値名:

| 値名 | 意味 |
|---|---|
| `file` | サンプルファイルのパス |
| `file_ex` | 拡張されたサンプルパス表現 |

パスにはバックスラッシュが使用される例が確認されている。

XML属性値であるため、パスにXMLの予約文字が含まれる場合はXMLエスケープが必要である。

---

## 14. Loop

LoopはZoneの `Loops` 配下に格納される。

```xml
<Loops>
  <Loop index="0" version="...">
    <V name="loopStart" value="..."/>
    <V name="loopLength" value="..."/>
    <V name="loopCount" value="..."/>
    <V name="mode" value="..."/>
    <V name="alternatingLoop" value="..."/>
    <V name="loopTuning" value="..."/>
    <V name="xfadeLength" value="..."/>
  </Loop>
</Loops>
```

確認されている主要パラメーター:

| パラメーター | 意味 |
|---|---|
| `loopStart` | ループ開始位置 |
| `loopLength` | ループ長 |
| `loopCount` | ループ回数 |
| `mode` | ループモード |
| `alternatingLoop` | 往復ループ |
| `loopTuning` | ループチューニング |
| `xfadeLength` | ループクロスフェード長 |

確認されているモード文字列:

| 値 | 意味 |
|---|---|
| `until_release` | Note Offまでループ |
| `until_end` | サンプル終端までループ |
| `oneshot` | ワンショット |

ループ終端は、開始位置と長さから表現される。

```text
loopEnd = loopStart + loopLength
```

各位置および長さの正確な単位は、実ファイルとの照合が必要である。

---

## 15. 数値表現

### 14.1 音量

`masterVolume`、`volume`、`zoneVolume` は線形倍率として格納される例が確認されている。

一般的な変換関係:

```text
linear_gain = 10^(dB / 20)
```

ただし、すべての音量関連パラメーターについて同一スケールが保証されているわけではない。

### 14.2 チューニング

`masterTune`、`tune`、`zoneTune`、`loopTuning` は周波数比として格納される例が確認されている。

一般的な変換関係:

```text
frequency_ratio = 2^(semitones / 12)
```

ニュートラル値は比率 `1.0` である。

### 14.3 パン

中央を `0.5` とする例が確認されている。

全値域と左右方向の定義は公式仕様では確認できない。

---

## 16. XMLエスケープ

XML属性値にはXMLエスケープが必要である。

| 文字 | エスケープ |
|---|---|
| `&` | `&amp;` |
| `<` | `&lt;` |
| `>` | `&gt;` |
| `"` | `&quot;` |
| `'` | `&apos;` |

対象例:

- Program名
- Group名
- サンプルパス
- その他の文字列属性

---

## 17. 不明または未確定の事項

### 16.1 バイナリヘッダー

次のフィールドの意味は確定していない。

- `0x0A` の16bit値
- `0x0C`～`0x13` の8バイト
- `0x14` の32bit値
- `0x20` の32bit値
- 時刻情報の歴史的なタイムゾーン解釈

### 16.2 XML

公式XML Schemaが公開されていないため、次は確定していない。

- 各XML要素の必須性
- パラメーター省略時の既定値
- `version` 属性の厳密な互換条件
- 未使用セクションを省略できるか
- パラメーターごとの完全な値域
- `sampleEnd` の終端包含・排他
- ループ位置とクロスフェード値の厳密な単位

### 16.3 互換性

既知のフィールドだけでXMLを構成しても、すべてのKONTAKT 1リビジョンで読み込めることは保証されない。

互換性の判定には、実際のKONTAKT 1で保存されたNKIとの比較および読み込み試験が必要である。

---

## 18. ファイル単体の検査項目

NKIファイルの構造を検査する場合、少なくとも次を確認する。

1. ファイルサイズが36バイトを超えている
2. 先頭4バイトが既知のNKI識別子である
3. 圧縮データ開始位置がファイル範囲内である
4. 通常形式では圧縮データ開始位置が `0x24` である
5. 圧縮領域が有効なZLIBストリームである
6. ZLIB展開結果が整形式XMLである
7. Program、Group、Zoneの参照関係が破綻していない
8. 各Zoneが存在するGroupを参照している
9. Zoneのキー範囲が有効である
10. Zoneのベロシティ範囲が有効である
11. Sample参照が存在する
12. Loopがある場合、開始位置と長さが負数でない
13. `NiSS_IntMod` の `index` が同じコンテナ内で重複していない
14. `Envelope type="ahdsr"` に必要なAHDSRパラメーターが存在する
15. `target` が意図した制御対象を示している
16. 時間値、Sustain、Intensityが負数や非数などの不正値でない
17. ヘッダーのサンプルデータ量が32bit範囲内である

---

## 19. 参考資料

### LinuxSampler nkitool

```text
https://www.linuxsampler.org/nkitool/
```

nkitoolは、KONTAKT 1～4形式のNKIに格納されたXMLを抽出し、XMLをNKIへ戻すためのツールである。

この事実から、対象世代のNKIが人間可読XMLを圧縮格納していることを確認できる。

### 注意

本書はNative Instrumentsの公式仕様書ではない。

外部ツール固有のテンプレート、独自中間モデル、既定値、補完要素は本書に含めていない。

AHDSR節に記載した要素名とパラメーター名は、KONTAKT 1 NKIのNiSS XMLとして確認されている書式だけを対象とし、特定ツールの内部モデルや独自フォーマットは含めていない。
