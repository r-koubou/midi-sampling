# サンプリング音源向けWAVループポイント自動検出ツール 実装仕様書

## 1. 文書の目的

サンプリング音源として使用されるWAVファイルを解析し、自然なサスティンを形成できるループ開始位置およびループ終了位置を自動検出するコマンドラインツールを実装する。

単純なゼロクロスポイント探索だけではなく、以下を組み合わせて候補を評価すること。

* サスティン区間の自動検出
* 波形の周期・位相の整合性
* 始点・終点周辺の波形類似度
* スペクトルの類似度
* 音量および音量変化傾向の連続性
* 基本周波数およびピッチ変化の連続性
* ビブラートやトレモロなどの変調位相
* クロスフェード後のレンダリング結果
* ループ長に対するペナルティ

十分な品質のループを検出できた場合、元のWAVオーディオデータを変更せず、出力WAVにRIFF `smpl`チャンクを挿入する。

---

## 2. 用語

| 用語         | 定義                                                |
| ---------- | ------------------------------------------------- |
| サンプルフレーム   | 全チャンネル分をまとめた1時刻分のサンプル。`smpl`チャンクの位置はサンプルフレーム単位とする |
| ループ開始位置    | `smpl`チャンクの`dwStart`に格納するサンプルフレーム番号               |
| ループ終了位置    | `smpl`チャンクの`dwEnd`に格納する、終端を含むサンプルフレーム番号           |
| サスティン区間    | アタック後に音量、音色、ピッチなどの変化が比較的安定している連続区間                |
| ハードシーム     | クロスフェードを使用せず、ループ終了位置から開始位置へ直接ジャンプした継ぎ目            |
| クロスフェードシーム | ループ終端と先頭を一定時間重ねてレンダリングした継ぎ目                       |
| 候補         | ループ開始位置、終了位置、評価用クロスフェード長の組                        |
| 品質スコア      | ループの不自然さを0.0～1.0で表した値。小さいほど良い                     |
| 信頼度        | 検出結果の相対的な確からしさ。品質スコアそのものとは区別する                    |

---

## 3. 実装方針

### 3.1 必須方針

実装は以下を満たすこと。

1. Pythonで実装する。
2. プロジェクト管理には`uv`を使用する。
3. パッケージ設定は`pyproject.toml`へ記述する。
4. CLIフレームワークにはTyperを使用する。
5. 処理は完全にローカルで完結させる。
6. 外部API、クラウドサービス、学習済みモデルのダウンロードを使用しない。
7. FFmpegなどの外部実行ファイルに依存しない。
8. 機械学習モデルではなく、決定論的なDSPアルゴリズムを使用する。
9. 同じ入力と同じ設定に対して同一結果を返す。
10. ゼロクロスは候補生成の主条件にせず、最終的な微調整または同点候補のタイブレークにのみ使用する。
11. 候補が見つからない場合に、品質の低いループを強制的に出力しない。
12. WAVの`data`チャンクは、通常の検出・書き込み処理では変更しない。

### 3.2 対象音源

主な対象は以下とする。

* オルガン
* シンセサイザー
* シンセパッド
* ドローン
* ストリングス
* クワイア
* 木管楽器
* 金管楽器
* 持続音を持つソロ弦楽器
* 持続的なノイズテクスチャ
* ビブラートやトレモロを含む持続音

### 3.3 対象外

以下はMVPの対象外とし、自然な結果を保証しない。

* ピアノ
* ハープ
* 強い減衰のみで構成された撥弦楽器
* 打楽器
* 極端に短いワンショット
* 複数の異なるノートやフレーズを含む素材
* リズムループ
* RF64
* 圧縮形式のWAV
* MP3、FLAC、AIFFなどWAV以外の入力
* GUI
* SFZ、SF2、Kontaktなどの楽器定義ファイル生成
* 複数ループの書き込み
* リリーストリガーやサステインペダル情報
* 破壊的なクロスフェード加工

ツール内で楽器分類を実施する必要はない。

---

## 4. サポートする入力形式

### 4.1 必須対応

以下のWAVを対象とする。

* RIFF/WAVE
* モノラルまたはステレオ
* PCM整数

  * 8-bit
  * 16-bit
  * 24-bit
  * 32-bit
* IEEE float

  * 32-bit
  * 64-bit
* `WAVE_FORMAT_EXTENSIBLE`

  * PCMサブフォーマット
  * IEEE floatサブフォーマット
* サンプリング周波数: 8,000～384,000 Hz
* 1.5秒以上のファイル

### 4.2 非対応入力

次の場合は入力エラーとする。

* RIFFではなくRF64である
* `data`チャンクが存在しない
* `fmt `チャンクが存在しない
* 圧縮WAVである
* チャンネル数が1または2以外
* サンプル数またはチャンクサイズが不正
* NaNまたはInfinityを大量に含む
* 解析可能な有効信号が存在しない
* ファイルが短すぎる

---

## 5. CLI仕様

### 5.1 コマンド名

```console
sample-loop-detector
```

### 5.2 基本コマンド

```console
uv run sample-loop-detector detect INPUT.wav
```

デフォルト出力ファイル名は次の形式とする。

```text
<入力ファイル名>.looped.wav
```

例:

```text
violin_C4.wav
violin_C4.looped.wav
```

### 5.3 使用例

```console
uv run sample-loop-detector detect input.wav
```

```console
uv run sample-loop-detector detect input.wav \
  --output output.wav \
  --report output.json
```

```console
uv run sample-loop-detector detect input.wav \
  --search-start 1.5 \
  --search-end 8.0 \
  --min-loop 0.8 \
  --max-loop 6.0
```

```console
uv run sample-loop-detector detect input.wav \
  --preview-output preview.wav \
  --top-k 10 \
  --verbose
```

既存の`smpl`チャンクを置換する場合:

```console
uv run sample-loop-detector detect input.wav \
  --replace-existing-loop
```

解析だけを行う場合:

```console
uv run sample-loop-detector detect input.wav \
  --dry-run \
  --report result.json
```

### 5.4 CLIオプション

| オプション                     |     型 |               デフォルト | 説明                   |
| ------------------------- | ----: | ------------------: | -------------------- |
| `INPUT`                   |  Path |                  必須 | 入力WAV                |
| `--output`, `-o`          |  Path | `<stem>.looped.wav` | 出力WAV                |
| `--report`                |  Path |                  なし | JSON解析レポート           |
| `--preview-output`        |  Path |                  なし | 選択ループを反復した試聴用WAV     |
| `--search-start`          | float |                  自動 | 探索開始秒                |
| `--search-end`            | float |                  自動 | 探索終了秒                |
| `--min-sustain`           | float |              `0.75` | サスティン区間の最小秒数         |
| `--min-loop`              | float |              `0.50` | 最小ループ長               |
| `--max-loop`              | float |              `8.00` | 最大ループ長               |
| `--fmin`                  | float |              `40.0` | ピッチ検出下限Hz            |
| `--fmax`                  | float |            `4000.0` | ピッチ検出上限Hz            |
| `--crossfade-lengths`     |   str |     `20,50,100,200` | 評価するクロスフェード長、ms      |
| `--top-k`                 |   int |                `10` | レポートへ残す候補数           |
| `--quality-threshold`     | float |              `0.35` | 採用可能な最大品質スコア         |
| `--midi-unity-note`       |   int |                  自動 | `smpl`へ格納するMIDI基準ノート |
| `--replace-existing-loop` |  bool |               false | 既存`smpl`チャンクを置換      |
| `--force`                 |  bool |               false | 既存出力ファイルを上書き         |
| `--dry-run`               |  bool |               false | 出力WAVを書かない           |
| `--verbose`, `-v`         |  bool |               false | 詳細ログ                 |
| `--version`               |  bool |                   - | バージョン表示              |

### 5.5 秒数オプションの検証

以下を満たさない場合は引数エラーとする。

```text
0 <= search_start < search_end <= duration
0 < min_loop <= max_loop
min_loop < detected_sustain_duration
quality_threshold ∈ [0, 1]
top_k >= 1
```

---

## 6. 出力と終了コード

### 6.1 終了コード

| コード | 意味                          |
| --: | --------------------------- |
| `0` | ループを検出し、正常終了                |
| `2` | 採用可能なループが見つからなかった           |
| `3` | 入力ファイルまたは引数が不正              |
| `4` | 出力競合、既存`smpl`チャンクなどの書き込みエラー |
| `5` | 予期しない内部エラー                  |

### 6.2 検出失敗時

採用可能な候補がない場合は次の動作とする。

* 出力WAVを生成しない。
* `--report`が指定されている場合は失敗理由を含むJSONを生成する。
* 終了コード`2`を返す。
* 最低品質の候補を強制的に採用しない。

### 6.3 アトミックな書き込み

出力WAVは一時ファイルへ書き込んだ後、処理が成功した場合のみ正式な出力パスへ置換すること。

処理途中でエラーが発生した場合、不完全なWAVを残さないこと。

---

## 7. 全体処理フロー

```text
1. CLI引数を解析
2. RIFF/WAV構造を検証
3. オーディオデータをfloat64へデコード
4. 解析用信号を構築
5. フレーム特徴量を抽出
6. サスティン区間を検出
7. 基本周波数と周期性を推定
8. ループ候補を生成
9. 候補位置をサンプル単位で微調整
10. ハードシームをレンダリングして評価
11. 複数のクロスフェード長でレンダリングして評価
12. 総合スコアを算出
13. 採用可能性を判定
14. 最良候補と代替候補を選択
15. JSONレポートおよび試聴用プレビューを生成
16. smplチャンクを挿入したWAVを生成
```

---

## 8. オーディオデコードと前処理

### 8.1 デコード

分析用オーディオは次の形式に統一する。

```python
shape = (frame_count, channel_count)
dtype = numpy.float64
```

整数PCMは、ビット深度に応じておおむね`[-1.0, 1.0]`へ正規化する。

出力用WAVについてはデコード後の信号を書き戻してはならない。元ファイルの`data`チャンクをバイト列として保持し、出力へそのままコピーする。

### 8.2 DCオフセット

解析用信号についてのみ、チャンネルごとの平均値を減算する。

```python
analysis_audio = audio - np.mean(audio, axis=0, keepdims=True)
```

元の`data`チャンクは変更しない。

### 8.3 ステレオ処理

ステレオ信号では以下を使用する。

* エネルギー・スペクトル解析:

  * チャンネル別に特徴量を抽出して平均する
* ピッチ解析:

  * サスティン候補区間内でRMSが大きい方のチャンネルを使用する
* 継ぎ目評価:

  * 左右チャンネルを個別評価する
  * Mid信号とSide信号も評価する
  * 左右の位相関係や相関の急変を評価する

単純なモノラル化だけで全評価を行ってはならない。

### 8.4 無音判定

次のいずれかに該当する場合、解析不能とする。

* ファイル全体のピークが極端に小さい
* 有効信号区間が最小サスティン長より短い
* 音量床より上のフレームがほとんど存在しない

音量床の初期値:

```text
max(
    推定ノイズフロア + 12 dB,
    ファイル内ピークRMS - 45 dB
)
```

---

## 9. フレーム設定

サンプリング周波数に依存して以下を計算する。

```python
target_window_seconds = 0.046
frame_length = next_power_of_two(sample_rate * target_window_seconds)
frame_length = clamp(frame_length, 1024, 8192)

hop_length = round(sample_rate * 0.010)
```

STFTの設定:

```text
window = Hann
center = false
power = 2.0
```

`center=False`とし、フレーム番号からサンプル位置への対応を明確にする。

---

## 10. 特徴量抽出

各フレームについて最低限、以下を抽出する。

### 10.1 音量関連

* RMS
* log RMS dB
* log RMSの一階差分
* log RMSの局所傾き
* 局所線形回帰からの残差

ピアノのような強い減衰音は対象外だが、弦・管楽器にも緩やかな減衰が存在するため、RMSが一定であることを要求してはならない。

局所区間内のlog RMSに一次回帰を適用し、回帰直線からの残差を安定性として評価する。

### 10.2 スペクトル関連

* STFT magnitude
* log-Melスペクトログラム
* スペクトルフラックス
* スペクトル重心
* スペクトル平坦度
* 必要に応じてMFCC

Melバンド数のデフォルト:

```text
64
```

### 10.3 ピッチ関連

`librosa.pyin`を使用して以下を取得する。

* 基本周波数
* voiced flag
* voiced probability

基本周波数の範囲:

```text
fmin = CLI指定値
fmax = min(CLI指定値, sample_rate / 4)
```

ピッチをcentへ変換する。

```python
cents = 1200.0 * np.log2(f0 / reference_f0)
```

無声音またはピッチ検出信頼度が低い素材では、ピッチ関連の評価を無効化し、スペクトル評価を中心に処理する。

### 10.4 変調関連

以下の低周波変動を抽出する。

* RMS包絡
* F0時系列
* スペクトル重心時系列

おおむね0.5～12 Hzの変動を対象とする。

用途:

* ビブラート位相
* トレモロ位相
* 音色モジュレーション位相

---

## 11. サスティン区間検出

### 11.1 目的

アタックおよびリリースを避け、ループ候補を探索可能な定常区間を1つ選択する。

### 11.2 アタック位置の推定

以下を組み合わせたアタックスコアを使用する。

* 正方向のlog RMS差分
* スペクトルフラックス
* `librosa.onset.onset_strength`

ファイル先頭から以下の小さい方までを主なアタック探索範囲とする。

```text
2.0秒
ファイル長の35%
```

アタック候補位置から最低200 msを探索除外区間とする。

ただし、後述の安定性判定によって、スローアタックが継続している区間も除外されなければならない。

### 11.3 安定性評価窓

デフォルトで500 ms程度のローリング窓を使用する。

各ローリング窓について以下を計算する。

* log RMSの線形回帰残差
* スペクトルフラックス中央値
* スペクトル重心の変動
* log-Melスペクトルのフレーム間距離
* F0のMAD
* voiced probability中央値
* RMS包絡の急激な変化
* 音量床との差

### 11.4 ロバスト正規化

特徴量ごとに中央値とMADを使用してロバスト正規化する。

```python
robust_z = (value - median) / (1.4826 * mad + epsilon)
```

極端な外れ値はクリップする。

### 11.5 安定性スコア

概念的には以下の重みを初期値とする。

```text
energy_residual:       0.25
spectral_flux:         0.25
spectral_variation:    0.20
centroid_variation:    0.10
pitch_variation:       0.15
other_modulation:      0.05
```

ピッチが安定して検出できない場合は`pitch_variation`を除外し、残りの重みを正規化する。

スコアは0.0～1.0へ正規化する。

```text
0.0 = 非常に安定
1.0 = 非常に不安定
```

### 11.6 サスティン候補区間

以下をすべて満たす連続フレームを候補とする。

* 音量床より上
* アタック除外区間より後
* ファイル末尾のリリース候補区間より前
* 安定性スコアが既定閾値以下
* 連続時間が`min_sustain`以上

100 ms以下の短い不安定区間は、前後が安定している場合に限り連結してよい。

### 11.7 区間選択

複数のサスティン区間がある場合、次の順序で選択する。

1. 最小長を満たす
2. 平均安定性スコアが低い
3. 長い
4. 音量が十分にある
5. ファイル末尾のリリースから離れている

単純に最長区間だけを選択してはならない。末尾の無音区間をサスティンとして選択しないこと。

### 11.8 ユーザー指定範囲

`--search-start`または`--search-end`が指定された場合、その範囲外を候補から除外する。

ユーザー指定範囲内でもサスティン安定性評価を実施する。

---

## 12. 基本周期の推定

サスティン区間内でvoiced probabilityが十分に高い場合、F0中央値を使用する。

```python
f0_median = weighted_median(
    f0,
    weights=voiced_probability
)
```

基本周期:

```python
period_samples = sample_rate / f0_median
```

ピッチが安定していると判定する条件の初期値:

```text
voiced frame ratio >= 0.60
median voiced probability >= 0.60
F0 MAD <= 30 cents
```

これらを満たさない場合、周期制約を弱めるか無効化する。

---

## 13. ループ候補生成

### 13.1 候補の制約

候補は以下を満たすこと。

```text
sustain_start <= loop_start < loop_end <= sustain_end
min_loop <= loop_length <= max_loop
```

クロスフェード評価窓がサスティン範囲からはみ出さないようにする。

### 13.2 エンドポイント記述子

各候補位置について、前後100 ms程度から次の記述子を作成する。

* log-Melスペクトルの平均
* log-Melスペクトルの分散
* log-Melスペクトルの時間差分
* RMS
* RMS傾き
* スペクトル重心
* スペクトル重心傾き
* F0
* F0傾き
* voiced probability
* ステレオSide成分のRMS
* 左右相関

### 13.3 粗探索

すべてのフレーム対を無制限に比較するO(N²)実装は避ける。

以下のように候補数を制限する。

* ループ開始候補を最大100地点程度に間引く
* 各開始候補について終了候補の記述子距離をベクトル化して計算
* 各開始候補につき上位5件程度を残す
* 粗探索候補の総数を最大256件とする

長いファイルでも候補総数が上限を超えないこと。

### 13.4 記述子距離

次を組み合わせる。

```text
log-Mel cosine distance
RMS差
RMS傾き差
スペクトル重心差
F0差
F0傾き差
ステレオ特徴差
```

ピッチが信頼できない場合はF0関連項目を除外する。

### 13.5 周期長制約

F0が信頼できる場合、ループ長が基本周期の整数倍に近い候補を優先する。

```python
period_count = loop_length_samples / period_samples
period_error = abs(period_count - round(period_count))
```

`period_error`はペナルティとして使用する。完全な整数倍を必須条件にはしない。

ビブラートやトレモロが検出された場合は、それらの変調周期にも近いループ長を優先する。

### 13.6 短いループへのペナルティ

候補スコアが同程度の場合は長いループを優先する。

デフォルトでは次のように扱う。

```text
0.5秒未満: 候補外
0.5～1.0秒: 強いペナルティ
1.0～2.0秒: 軽いペナルティ
2.0秒以上: 原則ペナルティなし
```

CLIの`--min-loop`が0.5秒未満に設定された場合でも、短いループへのペナルティは残す。

---

## 14. サンプル単位の候補微調整

粗探索で選択された各候補について、サンプル単位で開始位置・終了位置を微調整する。

### 14.1 探索範囲

F0が信頼できる場合:

```text
±0.5基本周期
```

F0が信頼できない場合:

```text
±10 ms
```

最大探索範囲は20 msとする。

### 14.2 正規化相互相関

開始位置周辺と終了位置周辺の20～50 ms程度の窓について、平均除去およびRMS正規化後に正規化相互相関を計算する。

```python
cost_waveform = (1.0 - correlation) / 2.0
```

ステレオの場合は左右チャンネルを別々に評価し、平均と最大値の両方を考慮する。

### 14.3 ゼロクロスの扱い

ゼロクロスは必須条件にしない。

次の場合のみ使用する。

* 総合スコアがほぼ同じ候補間のタイブレーク
* 最終位置から±2 ms程度の範囲で、他の品質指標を悪化させない微調整
* ハードシームの振幅差をわずかに改善できる場合

ステレオでは両チャンネルが同時にゼロになることを要求しない。

---

## 15. ハードシーム評価

`smpl`チャンクにはクロスフェード長を保存できないため、出力WAVを一般的なサンプラーで再生した際の品質を考慮し、ハードシーム評価を最終スコアの主要項目とする。

ループ区間:

```python
loop_audio = audio[loop_start : loop_end + 1]
```

これを4回以上反復した仮想レンダリングを作成する。

### 15.1 振幅差

```python
amplitude_jump = abs(audio[loop_end] - audio[loop_start])
```

局所RMSで正規化する。

### 15.2 一階微分差

```python
end_slope = audio[loop_end] - audio[loop_end - 1]
start_slope = audio[loop_start + 1] - audio[loop_start]
derivative_jump = abs(end_slope - start_slope)
```

### 15.3 波形相関

終端直前と開始直後の窓の正規化相互相関を使用する。

### 15.4 スペクトルシーム

ループ境界前後のlog-Melスペクトル距離を計算する。

絶対距離だけではなく、ループ内部の通常の隣接フレーム距離と比較する。

```python
relative_spectral_cost = (
    boundary_distance
    / (median_internal_adjacent_distance + epsilon)
)
```

境界変化が内部の自然な変化と同程度なら、絶対距離が大きくても過度に減点しない。

### 15.5 音量連続性

以下を評価する。

* 境界前後のRMS dB差
* 境界前後のRMS傾き差
* 反復時に音量が周期的に上昇または下降しないか

### 15.6 ピッチ連続性

ピッチが有効な場合、以下を評価する。

* 境界前後のF0差
* cent単位のピッチ差
* F0の上昇・下降方向
* ビブラート位相

### 15.7 ステレオ連続性

ステレオの場合、以下を評価する。

* Side成分のRMS差
* 左右相関の差
* Mid/Side比の差
* 左右チャンネル間の位相関係の急変

---

## 16. クロスフェード後のレンダリング評価

### 16.1 目的

ループ開始・終了位置の組み合わせが、クロスフェードによって安定したループへ改善可能かを評価する。

MVPでは、このクロスフェードを出力WAVの`data`チャンクへ焼き込まない。

### 16.2 評価対象のクロスフェード長

デフォルト:

```text
20 ms
50 ms
100 ms
200 ms
```

次の制約を適用する。

```text
crossfade_length <= ループ長の20%
crossfade_length <= 400 ms
crossfade_length >= 8 samples
```

制約を満たさない長さは除外する。

### 16.3 クロスフェードカーブ

相関の高い持続音を主対象とするため、デフォルトでは相補的なcosineカーブを使用する。

```python
phase = np.linspace(0.0, np.pi, crossfade_frames)

fade_in = 0.5 - 0.5 * np.cos(phase)
fade_out = 1.0 - fade_in
```

同一信号が重なった場合に、振幅が不必要に増加しないことを優先する。

### 16.4 レンダリング方法

ループ区間を最低4回反復し、各接続部分をオーバーラップ・アド方式でクロスフェードする。

レンダリングした音声に対し、以下を評価する。

* 継ぎ目の振幅差
* 継ぎ目の一階・二階微分差
* log-Melスペクトルの急変
* RMSの急変
* ピッチの急変
* 反復による周期的なポンピング
* ビブラートおよびトレモロ位相
* ステレオ像の急変

複数のクロスフェード長のうち、最良スコアを候補のクロスフェードスコアとして採用する。

### 16.5 ハードシームとの関係

出力する`smpl`チャンクはクロスフェード情報を保持しないため、クロスフェード評価だけが良好な候補を採用してはならない。

総合スコアではハードシームを優先する。

```text
hard_seam_score:       0.55
crossfade_seam_score:  0.30
sustain_quality:       0.10
loop_length_penalty:   0.05
```

クロスフェード後のスコアが良好でも、ハードシームスコアが既定の上限を超える場合は不採用とする。

---

## 17. スコアリング

### 17.1 スコア範囲

すべての主要スコアは0.0～1.0へ正規化する。

```text
0.0 = 理想的
1.0 = 非常に不自然
```

各正規化関数の閾値は`config.py`へ集約し、コード中へマジックナンバーを分散させない。

### 17.2 ハードシームスコアの初期重み

```text
waveform_correlation:     0.25
amplitude_jump:           0.10
derivative_jump:          0.10
spectral_continuity:      0.25
level_continuity:         0.10
pitch_continuity:         0.10
modulation_continuity:    0.05
stereo_continuity:        0.05
```

無効な特徴項目は除外し、残りの重みを再正規化する。

### 17.3 クロスフェードスコア

ハードシームと同様の特徴を使うが、クロスフェード済みレンダリング上の境界を評価する。

特に以下を重視する。

* スペクトルの不連続
* 音量ポンピング
* 位相キャンセル
* 短い周期での反復感
* ステレオ像の移動

### 17.4 採用条件

初期条件:

```text
total_score <= 0.35
hard_seam_score <= 0.45
sustain_confidence >= 0.50
loop_length >= min_loop
```

閾値は暫定値であり、テスト用サンプルによる調整を前提とする。

### 17.5 同程度の候補

最良候補と別候補の総合スコア差が`0.02`以下の場合、以下の順で選ぶ。

1. 長いループ
2. ハードシームスコアが低い
3. サスティン区間中央に近い
4. ゼロクロス近傍
5. 開始位置がアタックから遠い

---

## 18. 信頼度

信頼度は品質スコアとは別に算出する。

次を入力とする。

* サスティン区間の安定性
* 最良候補の絶対スコア
* 最良候補と2位候補のスコア差
* 候補数
* F0検出信頼度
* 複数のクロスフェード長で一貫した結果が得られたか
* 微調整前後で位置が大きく変化していないか

出力形式:

```text
high
medium
low
```

または0.0～1.0の数値もJSONへ含める。

低信頼度でも品質閾値を満たしている場合は出力してよいが、警告を表示する。

---

## 19. `smpl`チャンク仕様

### 19.1 基本方針

検出成功時、RIFF/WAVEへ`smpl`チャンクを1つ挿入する。

既存のオーディオデータ、`fmt `、LIST、INFO、bext、iXMLなどの未知チャンクは可能な限りそのまま保持する。

`smpl`チャンクは原則として`data`チャンクの直前へ挿入する。

### 19.2 バイトオーダー

すべてリトルエンディアンとする。

Pythonでは`struct.pack("<...")`を使用する。

### 19.3 `smpl`ヘッダー

以下の9個の32-bit unsigned integerを格納する。

| フィールド                  |                                    値 |
| ---------------------- | -----------------------------------: |
| Manufacturer           |                                  `0` |
| Product                |                                  `0` |
| Sample Period          | `round(1_000_000_000 / sample_rate)` |
| MIDI Unity Note        |                         自動推定またはCLI指定 |
| MIDI Pitch Fraction    |                           自動推定または`0` |
| SMPTE Format           |                                  `0` |
| SMPTE Offset           |                                  `0` |
| Number of Sample Loops |                                  `1` |
| Sampler Data           |                                  `0` |

### 19.4 ループ構造体

以下の6個の32-bit unsigned integerを格納する。

| フィールド        |                    値 |
| ------------ | -------------------: |
| Cue Point ID |                  `0` |
| Type         |                  `0` |
| Start        |       検出した開始サンプルフレーム |
| End          | 検出した終了サンプルフレーム、終端を含む |
| Fraction     |                  `0` |
| Play Count   |                  `0` |

`Type=0`は前方向ループとする。

`Play Count=0`は無限ループとする。

### 19.5 チャンクサイズ

ループ1件、追加Sampler Dataなしの場合:

```text
smpl payload size = 36 + 24 = 60 bytes
```

RIFFチャンク形式:

```text
"smpl"
uint32 payload_size
payload
padding_if_odd
```

### 19.6 MIDI Unity Note

`--midi-unity-note`が指定された場合、その値を使用し、Pitch Fractionは`0`とする。

指定されておらずF0推定が信頼できる場合:

```python
midi_float = 69.0 + 12.0 * log2(f0 / 440.0)
midi_note = floor(midi_float)
fraction = midi_float - midi_note
pitch_fraction = round(fraction * 2**32)
```

丸めの結果が`2**32`になった場合:

```python
midi_note += 1
pitch_fraction = 0
```

F0が信頼できない場合:

```text
MIDI Unity Note = 60
MIDI Pitch Fraction = 0
```

### 19.7 サンプル位置の意味

`Start`および`End`は、インターリーブされた個々の数値の位置ではなく、サンプルフレーム番号とする。

ステレオでも次のように数える。

```text
frame 0 = L0 + R0
frame 1 = L1 + R1
...
```

ループ長:

```python
loop_length = end - start + 1
```

### 19.8 RIFFサイズ

`smpl`チャンク挿入後、RIFFヘッダーのファイルサイズフィールドを更新する。

```text
RIFF size = file_size - 8
```

各チャンクが奇数サイズの場合、パディングバイトを考慮する。

### 19.9 既存`smpl`チャンク

デフォルトでは既存`smpl`チャンクが存在した場合、終了コード`4`で停止する。

`--replace-existing-loop`が指定された場合:

* 既存のすべての`smpl`チャンクを除去する。
* 新しい`smpl`チャンクを1つ挿入する。
* その他のチャンクは維持する。

重複した`smpl`チャンクを生成してはならない。

---

## 20. WAV書き込み時の非破壊要件

通常モードでは、入力と出力について以下を満たすこと。

* `data`チャンクの内容がバイト単位で一致する
* `fmt `チャンクを変更しない
* 未知チャンクを削除しない
* チャンクの内容を書き換えない
* 既存`smpl`を置換する場合を除き、元チャンクの順序を維持する
* RIFFサイズおよび追加チャンクのパディングのみ適切に変更する

オーディオを`float64`へ変換して再エンコードする実装は禁止する。

---

## 21. 試聴用プレビュー

`--preview-output`が指定された場合、選択したループを4回以上反復したWAVを生成する。

プレビューには以下の順で含める。

```text
1. ループ開始前の短い文脈
2. ハードシーム反復
3. 500 ms程度の無音
4. 最良クロスフェードによる反復
```

プレビューは元ファイルとは別の補助ファイルであり、`smpl`チャンク付き出力の`data`チャンクには影響させない。

プレビューWAVは32-bit floatで出力してよい。

---

## 22. JSONレポート

### 22.1 例

```json
{
  "version": "0.1.0",
  "status": "success",
  "input": {
    "path": "input.wav",
    "sample_rate": 48000,
    "channels": 2,
    "frames": 576000,
    "duration_seconds": 12.0,
    "format": "PCM_24"
  },
  "analysis": {
    "attack_end_seconds": 0.84,
    "sustain_start_seconds": 1.22,
    "sustain_end_seconds": 9.71,
    "sustain_confidence": 0.82,
    "f0_hz": 261.48,
    "f0_confidence": 0.91,
    "voiced_ratio": 0.95
  },
  "selected_loop": {
    "start_frame": 122304,
    "end_frame": 408959,
    "start_seconds": 2.548,
    "end_seconds": 8.520,
    "length_frames": 286656,
    "length_seconds": 5.972,
    "best_crossfade_ms": 100,
    "score": {
      "total": 0.148,
      "hard_seam": 0.164,
      "crossfade_seam": 0.071,
      "sustain": 0.120,
      "length_penalty": 0.0,
      "waveform": 0.102,
      "spectral": 0.138,
      "level": 0.091,
      "pitch": 0.075,
      "modulation": 0.182,
      "stereo": 0.133
    },
    "confidence": {
      "value": 0.86,
      "label": "high"
    }
  },
  "alternatives": [],
  "warnings": [],
  "configuration": {
    "min_loop_seconds": 0.5,
    "max_loop_seconds": 8.0,
    "quality_threshold": 0.35,
    "crossfade_lengths_ms": [20, 50, 100, 200]
  }
}
```

### 22.2 失敗例

```json
{
  "version": "0.1.0",
  "status": "no_acceptable_loop",
  "input": {
    "path": "input.wav"
  },
  "failure": {
    "reason": "no_stable_sustain_region",
    "message": "A sufficiently stable sustain region was not found."
  },
  "best_rejected_candidate": {
    "start_frame": 48000,
    "end_frame": 96000,
    "score": {
      "total": 0.62,
      "hard_seam": 0.71
    }
  },
  "warnings": []
}
```

### 22.3 失敗理由コード

最低限、以下を定義する。

```text
unsupported_wave_format
audio_too_short
no_active_signal
no_stable_sustain_region
sustain_region_too_short
no_loop_candidates
all_candidates_above_threshold
hard_seam_above_threshold
existing_smpl_chunk
invalid_arguments
write_failed
```

---

## 23. データモデル

`dataclasses`を使用し、最低限以下を定義する。

```python
@dataclass(frozen=True)
class AudioMetadata:
    sample_rate: int
    channels: int
    frame_count: int
    duration_seconds: float
    format_tag: int
    bits_per_sample: int
    subtype: str


@dataclass(frozen=True)
class SustainRegion:
    start_frame: int
    end_frame: int
    stability_score: float
    confidence: float


@dataclass(frozen=True)
class PitchEstimate:
    f0_hz: float | None
    confidence: float
    voiced_ratio: float
    period_samples: float | None


@dataclass(frozen=True)
class LoopCandidate:
    start_frame: int
    end_frame: int
    crossfade_frames: int
    coarse_score: float


@dataclass(frozen=True)
class LoopScore:
    total: float
    hard_seam: float
    crossfade_seam: float
    waveform: float
    spectral: float
    level: float
    pitch: float | None
    modulation: float | None
    stereo: float | None
    sustain: float
    length_penalty: float


@dataclass(frozen=True)
class LoopResult:
    selected: LoopCandidate
    score: LoopScore
    confidence: float
    confidence_label: str
    alternatives: tuple[LoopCandidate, ...]
```

内部で辞書を乱用せず、処理境界を明確にする。

---

## 24. 推奨ディレクトリ構成

```text
sample-loop-detector/
├── pyproject.toml
├── uv.lock
├── README.md
├── src/
│   └── sample_loop_detector/
│       ├── __init__.py
│       ├── __main__.py
│       ├── cli.py
│       ├── config.py
│       ├── models.py
│       ├── pipeline.py
│       ├── exceptions.py
│       ├── analysis/
│       │   ├── __init__.py
│       │   ├── preprocessing.py
│       │   ├── framing.py
│       │   ├── features.py
│       │   ├── sustain.py
│       │   ├── pitch.py
│       │   ├── modulation.py
│       │   ├── candidates.py
│       │   ├── refinement.py
│       │   ├── render.py
│       │   └── scoring.py
│       ├── audio/
│       │   ├── __init__.py
│       │   ├── decoder.py
│       │   ├── riff.py
│       │   ├── smpl.py
│       │   └── preview.py
│       └── reporting/
│           ├── __init__.py
│           └── json_report.py
└── tests/
    ├── unit/
    │   ├── test_riff.py
    │   ├── test_smpl.py
    │   ├── test_sustain.py
    │   ├── test_pitch.py
    │   ├── test_candidates.py
    │   ├── test_render.py
    │   └── test_scoring.py
    ├── integration/
    │   ├── test_cli_success.py
    │   ├── test_cli_failure.py
    │   └── test_wav_preservation.py
    └── fixtures/
```

---

## 25. 外部依存パッケージ

### 25.1 ランタイム依存

| パッケージ       | 用途                             |
| ----------- | ------------------------------ |
| `numpy`     | 信号配列、ベクトル演算、相関、統計              |
| `scipy`     | 信号処理、フィルター、補間、距離計算             |
| `librosa`   | STFT、Melスペクトル、RMS、pYIN、オンセット特徴 |
| `soundfile` | WAVオーディオの分析用デコード、プレビュー出力       |
| `typer`     | CLI                            |

RIFFチャンクの解析および`smpl`チャンク挿入には標準ライブラリの`struct`、`pathlib`、`tempfile`を使用し、外部WAVメタデータ編集ライブラリには依存しない。

### 25.2 開発依存

| パッケージ        | 用途            |
| ------------ | ------------- |
| `pytest`     | テスト           |
| `pytest-cov` | カバレッジ         |
| `ruff`       | lintおよびformat |
| `mypy`       | 型検査           |

---

## 26. `pyproject.toml`

```toml
[build-system]
requires = ["uv_build>=0.11.29,<0.12"]
build-backend = "uv_build"

[project]
name = "sample-loop-detector"
version = "0.1.0"
description = "Automatic sustain loop point detector for sampled instrument WAV files"
readme = "README.md"
requires-python = ">=3.12,<3.14"
license = "MIT"
authors = [
    { name = "Your Name" }
]
dependencies = [
    "numpy>=2.0,<3",
    "scipy>=1.14,<2",
    "librosa>=0.11,<0.12",
    "soundfile>=0.13,<0.14",
    "typer>=0.16,<1",
]

[project.scripts]
sample-loop-detector = "sample_loop_detector.cli:app"

[dependency-groups]
dev = [
    "pytest>=8,<10",
    "pytest-cov>=6,<8",
    "ruff>=0.12,<1",
    "mypy>=1.16,<2",
]

[tool.uv]
package = true

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = [
    "E",
    "F",
    "I",
    "B",
    "UP",
    "SIM",
    "RUF",
]

[tool.ruff.format]
quote-style = "double"
indent-style = "space"

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = [
    "--strict-config",
    "--strict-markers",
]

[tool.coverage.run]
branch = true
source = ["sample_loop_detector"]

[tool.coverage.report]
show_missing = true
skip_covered = true
fail_under = 85

[tool.mypy]
python_version = "3.12"
strict = true
packages = ["sample_loop_detector"]
```

依存関係の追加後は`uv.lock`を生成し、バージョン管理へ含める。

```console
uv lock
uv sync --group dev
```

---

## 27. 例外設計

アプリケーション内部では最低限、以下の例外型を定義する。

```python
class LoopDetectorError(Exception):
    pass


class InvalidWaveError(LoopDetectorError):
    pass


class UnsupportedWaveFormatError(InvalidWaveError):
    pass


class SustainNotFoundError(LoopDetectorError):
    pass


class LoopCandidateNotFoundError(LoopDetectorError):
    pass


class ExistingSmplChunkError(LoopDetectorError):
    pass


class WaveWriteError(LoopDetectorError):
    pass
```

CLI境界で例外を終了コードへ変換する。

解析ロジック内部で直接`sys.exit`を呼ばない。

---

## 28. ログ

通常時は以下を簡潔に表示する。

```text
Input: input.wav
Format: 48000 Hz / stereo / PCM 24-bit
Sustain: 1.22 s - 9.71 s
Loop: 2.548 s - 8.520 s
Length: 5.972 s
Score: 0.148
Confidence: high
Output: input.looped.wav
```

`--verbose`では以下も表示する。

* 特徴抽出設定
* サスティン候補
* F0推定結果
* 粗探索候補数
* 微調整前後の位置
* 各スコア内訳
* 棄却理由
* 選択したクロスフェード長
* WAVチャンク一覧

大きなNumPy配列そのものをログ出力しない。

---

## 29. テスト仕様

### 29.1 RIFFテスト

以下を検証する。

* RIFFヘッダー解析
* `fmt `チャンク解析
* `data`チャンク検出
* 未知チャンクの保持
* 奇数サイズチャンクのパディング
* RIFFサイズ更新
* 破損チャンクの検出
* RF64の拒否
* WAVE_FORMAT_EXTENSIBLEの識別

### 29.2 `smpl`チャンクテスト

以下を検証する。

* ペイロードサイズが60バイト
* リトルエンディアン
* ループ数が1
* ループタイプが0
* Play Countが0
* StartおよびEndが正しい
* Endが終端を含む
* ステレオでもサンプルフレーム番号になる
* MIDI Unity Noteの計算
* Pitch Fractionの計算
* RIFFサイズの更新
* 既存`smpl`の拒否
* `--replace-existing-loop`による置換
* 重複`smpl`が生成されない

### 29.3 非破壊テスト

出力WAVについて以下を検証する。

```python
input_data_chunk == output_data_chunk
input_fmt_chunk == output_fmt_chunk
```

既存`smpl`以外の各チャンク内容が一致すること。

最低限、以下の入力を用意する。

* 16-bit mono
* 24-bit stereo
* 32-bit PCM
* 32-bit float
* WAVE_FORMAT_EXTENSIBLE
* LIST/INFO付きWAV
* 奇数サイズの未知チャンク付きWAV

### 29.4 合成信号による解析テスト

#### 安定した正弦波

構成:

```text
短いアタック
安定した正弦波
短いリリース
```

期待結果:

* アタックおよびリリースを除外
* 周期の整数倍に近いループ
* 低いハードシームスコア

#### 倍音を含む持続音

基本波と複数倍音を合成する。

期待結果:

* 基本波だけでなく波形全体の相関が高い候補を選択
* 単純なゼロクロスだけに依存しない

#### ビブラート付き持続音

5～7 Hz程度のF0変調を追加する。

期待結果:

* ビブラート位相が大きく異なる候補を避ける
* 短すぎるループを避ける

#### トレモロ付き持続音

RMS包絡へ周期変調を追加する。

期待結果:

* 音量変調位相が近い候補を優先
* 反復時のポンピングが少ない

#### ステレオ持続音

左右で位相または音量変化を少し変える。

期待結果:

* モノラル評価だけでは不自然な候補を棄却
* Side成分が連続する候補を選択

#### ノイズパッド

周期的F0を持たない持続ノイズを生成する。

期待結果:

* ピッチ制約を無効化
* スペクトルと音量の自己類似性で候補を選択

#### 非サスティン素材

短い減衰音または打撃音を生成する。

期待結果:

* 無理にループを生成しない
* 終了コード`2`

### 29.5 CLI統合テスト

以下を検証する。

* 正常な検出
* `--dry-run`
* JSONレポート
* プレビュー生成
* 出力ファイル競合
* `--force`
* 既存`smpl`
* 不正な探索範囲
* 候補なし
* 終了コード

### 29.6 決定性

同一入力を複数回処理し、以下が一致すること。

* サスティン区間
* ループ開始位置
* ループ終了位置
* スコア
* JSONレポートの解析値

タイムスタンプや一時パスなど、非決定的な項目は比較対象外とする。

---

## 30. 性能要件

厳密な実行時間はハードウェアに依存するため受け入れ判定には使用しないが、以下を設計目標とする。

* 候補探索を無制限なO(N²)にしない
* 30秒程度のステレオWAVを一般的なデスクトップPCで実用時間内に処理する
* 特徴量行列を必要以上に複製しない
* すべての候補について長時間プレビューを生成しない
* 粗探索後の上位候補だけを詳細レンダリングする
* 候補数を設定値で上限管理する
* 長いファイルでメモリ使用量が急増しない

初期実装では可読性と正確性を優先し、プロファイリング結果に基づいて最適化する。

---

## 31. 受け入れ条件

MVP完成の条件は以下とする。

### 31.1 プロジェクト

* `uv sync --group dev`が成功する
* `uv run sample-loop-detector --help`が成功する
* `uv run pytest`が成功する
* `uv run ruff check .`が成功する
* `uv run ruff format --check .`が成功する
* `uv run mypy src`が成功する

### 31.2 解析

* アタックとリリースを除外したサスティン区間を検出できる
* 安定した単音素材で周期整合した候補を生成できる
* ピッチ不明素材でスペクトル中心の評価へ切り替えられる
* ハードシームとクロスフェードシームの両方を評価する
* 品質閾値を満たさない場合は出力しない
* 上位候補をJSONへ記録できる

### 31.3 WAV出力

* 検出成功時に`smpl`チャンクを挿入できる
* `data`チャンクが入力とバイト単位で一致する
* 24-bit PCMを破壊しない
* 未知チャンクを保持する
* RIFFサイズとパディングが正しい
* 主要なWAV解析ツールで出力WAVを開ける
* ループ開始・終了位置がサンプルフレーム単位で正しい
* `smpl`チャンクが重複しない

### 31.4 テスト品質

* コア処理のカバレッジが85%以上
* RIFFおよび`smpl`処理は分岐を含め重点的にテストする
* 合成音による成功・失敗ケースを含む
* 実ファイルがなくても主要ロジックをテストできる

---

## 32. 実装順序

エージェントは次の順序で実装すること。

### フェーズ1: プロジェクト基盤

1. `uv`プロジェクト作成
2. `pyproject.toml`
3. パッケージ構造
4. Typer CLIの骨格
5. lint、format、型検査、テスト設定

### フェーズ2: RIFFおよび`smpl`

1. RIFFチャンクパーサー
2. WAV形式検証
3. `smpl`チャンク生成
4. 非破壊チャンクコピー
5. 既存`smpl`処理
6. 単体テスト

このフェーズでは、固定された仮のループ位置を書き込む統合テストまで作成する。

### フェーズ3: 特徴量とサスティン検出

1. オーディオデコード
2. フレーム処理
3. RMS、スペクトル、ピッチ特徴
4. アタック推定
5. サスティン安定性評価
6. 合成音テスト

### フェーズ4: 候補生成

1. エンドポイント記述子
2. 粗探索
3. 周期ペナルティ
4. 短いループへのペナルティ
5. 候補数制限

### フェーズ5: 詳細評価

1. サンプル単位の位置調整
2. ハードシームレンダリング
3. クロスフェードレンダリング
4. スペクトル・音量・ピッチ評価
5. ステレオ評価
6. 総合スコア

### フェーズ6: 出力とレポート

1. 採用判定
2. JSONレポート
3. プレビューWAV
4. `smpl`付き出力
5. CLI統合テスト

### フェーズ7: 調整

1. 合成音で閾値を調整
2. 複数種類の実サンプルで試聴
3. 誤検出理由をレポートへ追加
4. 性能プロファイリング
5. README作成

---

## 33. エージェントへの実装上の注意

* 最初から大規模な抽象化を導入しない。
* RIFF処理とDSP処理を分離する。
* WAV書き込みに`scipy.io.wavfile.write`や`soundfile.write`を使用して元ファイル全体を再生成しない。
* `data`チャンクをコピーする独自RIFFライターを実装する。
* `librosa.load`による自動リサンプリングを使用しない。
* 入力のサンプリング周波数を維持する。
* `center=False`を基本とし、サンプル位置変換のオフセットを曖昧にしない。
* フレーム番号、時刻、サンプルフレーム番号を混同しない。
* `smpl`の終了位置が包含終端であることをテストする。
* ステレオの位置はインターリーブ要素番号ではなくフレーム番号とする。
* ピッチが検出できないことをエラー扱いにしない。
* クロスフェード後だけ良好になる候補を無条件で採用しない。
* 候補なしは正常に起こり得る結果として扱う。
* 解析パラメーターを`config.py`へ集約する。
* 各スコアの内訳をJSONへ残し、調整可能にする。
* スコア閾値は経験的な初期値であり、絶対的な確率として表示しない。
* 処理を乱数に依存させない。
* 実装途中でも各フェーズのテストが通る状態を維持する。

---

## 34. 将来拡張

MVP完成後の候補であり、初期実装へ含める必要はない。

* バッチ処理
* ディレクトリ再帰処理
* 複数ループ候補の`smpl`格納
* 破壊的クロスフェードの焼き込み
* 双方向ループ
* リバースループ
* 自己類似度行列の可視化
* HTML解析レポート
* 波形および候補位置の画像出力
* 楽器タイプ別プリセット
* ビブラート周期の高精度推定
* トレモロ周期の高精度推定
* 複数マイクチャンネル対応
* BWF/RF64対応
* AIFFのMARK/INSTチャンク対応
* SFZマッピング出力
* 人間による候補選択用TUI
* 既存ループの品質検査コマンド

---

## 35. 技術選定に関する補足

`uv`では依存関係を`pyproject.toml`へ記述し、解決された正確なバージョンを`uv.lock`へ保存できる。公式ドキュメントでは`uv.lock`をバージョン管理へ含める運用が示されている。

`uv_build`は純粋なPythonプロジェクト向けの公式ビルドバックエンドであり、公式の現行例では`uv_build>=0.11.29,<0.12`が使用されている。

librosa 0.11には、本仕様で使用するSTFT、Melスペクトログラム、RMS、スペクトル特徴、pYIN、自己類似度関連処理が含まれている。

SoundFileはlibsndfileを利用したクロスプラットフォームの音声入出力ライブラリであり、分析用デコードとプレビュー生成に使用する。ただし、`smpl`挿入時は元WAVの再エンコードを避けるため、独自のRIFFチャンク処理を使用する。
