# midi-sampling

外部MIDI音源を自動サンプリングし、KONTAKT、SFZ、UVI Falcon などのサンプラー形式へ
変換可能な中間成果物(WAV + マニフェスト)を生成するツール。

## 必要環境

- Python 3.14+
- [uv](https://docs.astral.sh/uv/)

## セットアップ

```bash
uv sync
```

## 使い方

```bash
# 定義ファイルに記述するためのデバイス名をリストアップ
uv run list-devices

# サンプリング実行
uv run midi-sampling run <session.yaml>

# 既存成果物と現在の定義の整合性を監査(読み取り専用)
uv run midi-sampling audit <session.yaml>
```

定義ファイルのサンプルは [examples/sessions/](examples/sessions/) を参照。

## 開発

```bash
# テスト実行
uv run pytest
```

仕様・設計ドキュメントは [.agents/](.agents/) を参照。

## ライセンス

MIT
