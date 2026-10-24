# 初期実装計画: wav-silence-trimmer

> 注: 初期実装(2026-07-18)はプランモードを経由せず、仕様書(現 `.agents/specs/trimming.md`)から直接実装した。
> 本ファイルは実装開始時に組み立てた計画と設計判断を、後から参照できるよう文書化したもの。

## Context

音声ファイル(WAV)の先頭・末尾の無音部分を自動削除する CLI ツールを新規実装する。
サスティンループ検出処理の前処理として使用し、固定 dB 閾値ではなく端部余白からのノイズフロア推定 + ヒステリシス閾値で有音区間を検出する。仕様書に全アルゴリズム・CLI 仕様・テスト観点が定義済み。

## 実装手順

1. **pyproject.toml** — 既存スタブ(`sample-trimmer`)を仕様のパッケージ名 `wav-silence-trimmer` に書き換え。
   hatchling ビルド、`wav-trim = "wav_silence_trimmer.cli:main"` エントリポイント、
   依存 numpy / scipy / soundfile、dev グループに pytest / pytest-cov。
2. **モジュール分割**(CLI 層と信号処理層を分離、src レイアウト):
   - `errors.py` — 独自例外階層(`WavTrimmerError` 基底 + Invalid/Unsupported/NoSignal/OutputExists/InvalidConfiguration)
   - `config.py` — デフォルト定数と `validate_config()`(引数妥当性検証)
   - `models.py` — `TrimConfig` / `AudioMetadata` / `DetectionResult` / `TrimResult` / `ProcessingResult`(frozen dataclass)
   - `detector.py` — 検出パイプライン本体
   - `fade.py` — 線形フェード
   - `audio_io.py` — soundfile による読み書き
   - `cli.py` — argparse、単一/ディレクトリ処理、JSON レポート、終了コード
3. **テスト**(合成信号を `tests/conftest.py` で生成) → `uv sync` → `uv run pytest` で検証
4. **README.md** — セットアップ、使用例、パラメーター、設計判断の記載

## detector.py の設計判断

パイプライン(仕様 §8 準拠):

1. DC 除去は**中央値**減算(有音部の大振幅で平均が偏るのを防ぐ)。解析用コピーのみで、出力は原音から切り出す
2. フレーム RMS は**二乗累積和**で全フレーム一括計算(10ms フレーム / 2ms ホップ)。
   末尾の端数フレームは実長で正規化。代表値は**チャンネル間最大**(片側定位・片側リリース保護)
3. dBFS 変換(epsilon 下限)+ 3点メディアンフィルタ
4. ノイズフロア = 先頭・終端 各 `edge_noise_seconds` のフレームレベルの **20パーセンタイル**、
   `minimum_noise_floor_dbfs` でクランプ。端部が入力長を超える場合は警告して全フレーム使用
5. ヒステリシス: `threshold_on = floor + 15dB` / `threshold_off = floor + 8dB`
6. 開始シード = on 閾値以上が `minimum_on_ms` 以上連続する区間(クリック除外)
7. off 閾値マスクに `bridge_gap_ms` 幅の **binary_closing** で短ギャップ連結(トレモロ対策)。
   閉包結果は元マスクと OR し、境界効果で真の有音フレームが消えないことを保証
8. シードを含む連結成分のみ採用。**最初の成分の先頭〜最後の成分の末尾**を有音区間とする(曲中の休符は削除しない)
9. 境界再探索: 開始 ±50ms / 終了 ±100ms を 1ms 窓・0.25ms ホップで off 閾値と比較し高精度化
10. プリロール 8ms / ポストロール 40ms を付加し [0, total] にクランプ

## その他の設計判断

- **audio_io**: float64 / always_2d で読み込み。サブタイプ(PCM_16 等)維持。
  書き込みは同一ディレクトリの一時ファイル経由で `os.replace`(原子的置換、失敗時に不完全ファイルを残さない)
- **fade**: 全チャンネル同一ゲインの線形フェード。実際にトリミングした側のみ適用。長さは出力長にクランプ
- **終了コード**: 0=成功 / 1=一部失敗 / 2=引数不正 / 3=入力不正 / 4=有音検出不能 / 5=書き込み失敗。
  有音検出不能はデフォルトで警告スキップ(レポートには error として記録)、`--fail-on-no-signal` 時のみ失敗扱い
- **「全体が有音」のファイル**は、端部ノイズフロア推定の帰結として検出不能(仕様 §8.5/§8.7)。
  前提条件(約1秒の余白)違反の入力であり、これを正とする

## 検証

- ユニットテスト: フレーム RMS(サイン波/ステレオ片側/無音/短入力)、DC 除去、ノイズフロア(無音/白色ノイズ/インパルス混入/残響混入)、
  検出(明確なアタック/遅いアタック/長いリリース/トレモロ連結/休符保持/クリック非開始/全無音/ノイズのみ)、
  フェード、audio_io(ラウンドトリップ/上書き制御/非WAV拒否)、CLI(終了コード全種/dry-run/レポート/再帰/大文字拡張子)
- E2E: 合成 WAV(48kHz ステレオ PCM_24、1秒ノイズ + 2秒トーン + 1秒ノイズ)を `uv run wav-trim` で処理し、
  境界精度・サブタイプ維持・レポート内容を確認

## 実装結果(記録)

- 全テスト成功。E2E で境界誤差 約0.75ms、ノイズフロア -80.0 dBFS を正しく推定
- 追補(2026-07-27): WAVEX(WAVE_FORMAT_EXTENSIBLE)入力が拒否される不具合を修正。
  読み込みで WAV / WAVEX / RF64 を許可し、書き込みで元のコンテナ種別を維持
