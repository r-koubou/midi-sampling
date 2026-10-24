# sample-loop-detector

サンプリング音源として使用されるWAVファイルを解析し、自然なサスティンループの開始・終了位置を自動検出するコマンドラインツールです。検出に成功すると、元のオーディオデータを一切変更せずに、RIFF `smpl` チャンクを挿入した出力WAVを生成します。

## 特徴

- ゼロクロス探索ではなく、複数のDSP指標を組み合わせた決定論的なループ評価
  - サスティン区間の自動検出(アタック・リリースの除外)
  - 波形の周期・位相整合性(pYINによる基本周波数推定)
  - 始点・終点周辺の波形類似度(正規化相互相関)
  - log-Melスペクトルの類似度と境界不連続性
  - 音量・ピッチ・変調(ビブラート/トレモロ)位相の連続性
  - ステレオ(Mid/Side・左右相関)の連続性
  - クロスフェードレンダリングによる検証と、ループ長ペナルティ
- ハードシーム(クロスフェードなしの直接ジャンプ)品質を最優先で評価
- `data`チャンクをバイト単位で保持する非破壊書き込み(再エンコードなし)
- 完全ローカル処理。外部API・学習済みモデル・FFmpeg不使用
- 同じ入力と設定に対して常に同一の結果(決定論的)

## 動作要件

- Python 3.12 – 3.13
- [uv](https://docs.astral.sh/uv/)

## セットアップ

```console
uv sync --group dev
```

## 使い方

基本:

```console
uv run sample-loop-detector detect input.wav
```

デフォルトの出力ファイル名は `<入力ファイル名>.looped.wav` です。

出力先・レポート・試聴用プレビューを指定:

```console
uv run sample-loop-detector detect input.wav \
  --output output.wav \
  --report result.json \
  --preview-output preview.wav
```

探索範囲やループ長を制御:

```console
uv run sample-loop-detector detect input.wav \
  --search-start 1.5 \
  --search-end 8.0 \
  --min-loop 0.8 \
  --max-loop 6.0
```

既存の `smpl` チャンクを置換:

```console
uv run sample-loop-detector detect input.wav --replace-existing-loop
```

解析のみ(WAVを書き出さない):

```console
uv run sample-loop-detector detect input.wav --dry-run --report result.json
```

### 主なオプション

| オプション | デフォルト | 説明 |
| --- | ---: | --- |
| `--output`, `-o` | `<stem>.looped.wav` | 出力WAV |
| `--report` | なし | JSON解析レポート |
| `--preview-output` | なし | ループを反復した試聴用WAV (32-bit float) |
| `--search-start` / `--search-end` | 自動 | 探索範囲 (秒) |
| `--min-sustain` | `0.75` | サスティン区間の最小秒数 |
| `--min-loop` / `--max-loop` | `0.50` / `8.00` | ループ長の範囲 (秒) |
| `--fmin` / `--fmax` | `40` / `4000` | ピッチ検出範囲 (Hz) |
| `--crossfade-lengths` | `20,50,100,200` | 評価するクロスフェード長 (ms) |
| `--quality-threshold` | `0.35` | 採用可能な最大品質スコア (小さいほど良い) |
| `--midi-unity-note` | 自動 | `smpl` に格納するMIDI基準ノート |
| `--replace-existing-loop` | false | 既存 `smpl` チャンクを置換 |
| `--force` | false | 既存出力ファイルを上書き |
| `--dry-run` | false | 出力WAVを書かない |
| `--verbose`, `-v` | false | 詳細ログ |

### 終了コード

| コード | 意味 |
| --: | --- |
| `0` | ループを検出し、正常終了 |
| `2` | 採用可能なループが見つからなかった |
| `3` | 入力ファイルまたは引数が不正 |
| `4` | 出力競合・既存 `smpl` チャンクなどの書き込みエラー |
| `5` | 予期しない内部エラー |

## 対応入力

- RIFF/WAVE (モノラルまたはステレオ、1.5秒以上、8,000〜384,000 Hz)
- PCM整数 8/16/24/32-bit、IEEE float 32/64-bit
- `WAVE_FORMAT_EXTENSIBLE` (PCM / IEEE floatサブフォーマット)

RF64・圧縮WAV・MP3/FLAC/AIFF等は非対応です。ピアノ・打楽器のような減衰主体の素材、フレーズ・リズムループは対象外で、その場合は無理にループを生成せず終了コード `2` を返します。

## 対象音源

オルガン、シンセ、パッド、ドローン、ストリングス、クワイア、木管・金管、持続音を持つソロ弦、持続的なノイズテクスチャ、ビブラート/トレモロを含む持続音など。

## 開発

```console
uv run pytest          # テスト (カバレッジ85%必須)
uv run ruff check .    # lint
uv run ruff format .   # format
uv run mypy src        # 型検査 (strict)
```

## ライセンス

MIT
