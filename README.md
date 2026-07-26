# midi-sampling

外部MIDI音源を自動サンプリングし、KONTAKT、SFZ、UVI Falcon などのサンプラー形式へ
変換可能な中間成果物(WAV + マニフェスト)を生成するツール。

## 必要環境

- Python 3.12 以上 3.14 未満
- [uv](https://docs.astral.sh/uv/)

## セットアップ

### サンプリングのみ

```bash
uv sync
```

### ポストプロセス(トリミング・ループ検出)も使う場合

ポストプロセスが依存する2つのパッケージは **PyPI 未公開**のため、
リポジトリを手元に clone し、`pyproject.toml` の `[tool.uv.sources]` に
**相対パス**で場所を教える必要があります。

#### 1. DSP リポジトリを clone する

既定では midi-sampling と**同じ親ディレクトリ**に並んでいることを想定しています。

```bash
cd ..   # midi-sampling の親ディレクトリへ
git clone git@github.com:r-koubou/sample-loop-detector.git
git clone git@github.com:r-koubou/sample-trimmer.git
cd midi-sampling
```

```text
<親ディレクトリ>/
├─ midi-sampling/          ← このリポジトリ
├─ sample-loop-detector/
└─ sample-trimmer/
```

#### 2. 必要なら `pyproject.toml` の相対パスを編集する

上記と異なる場所に clone した場合は、`[tool.uv.sources]` のパスを実際の配置に
合わせて書き換えてください。

```toml
[tool.uv.sources]
sample-loop-detector = { path = "../sample-loop-detector", editable = true }
wav-silence-trimmer  = { path = "../sample-trimmer",       editable = true }
```

- パスは `pyproject.toml` の所在ディレクトリが基準です。
- `wav-silence-trimmer` の clone 先ディレクトリ名は `sample-trimmer` です
  (パッケージ名とディレクトリ名が異なる点に注意)。
- `editable = true` なので、DSP 側を編集すると再インストールなしで反映されます。

#### 3. extra を指定して同期する

```bash
uv sync --extra postprocess
```

`postprocess` は optional extra なので、**素の `uv sync` では入りません**。
それどころか、既に入っている場合は削除されます。
`uv run --extra postprocess <command>` で単発指定もできます。

`[tool.uv.sources]` は「どこから取得するか」を指定するだけで、
インストール対象に含めるかどうかは `--extra` の指定で決まります。

## 使い方

```bash
# 定義ファイルに記述するためのデバイス名をリストアップ
uv run list-devices

# サンプリング実行
uv run midi-sampling run <session.yaml>

# 既存成果物と現在の定義の整合性を監査(読み取り専用)
uv run midi-sampling audit <session.yaml>

# 録音済み成果物をトリミング・ループ検出して派生成果物を生成
# (事前に「ポストプロセスも使う場合」のセットアップが必要)
uv run midi-sampling postprocess <postprocess_session.yaml>
```

定義ファイルのサンプルは [examples/sessions/](examples/sessions/) を参照。

## ポストプロセス

`postprocess` は録音済みの WAV とマニフェストを入力として、トリミングとサステインループ
検出(`smpl` チャンク埋め込み)を適用し、**別ディレクトリ**へ派生成果物を出力する。
`recorded/` は決して書き換えない。

```text
recorded/<tone-id>/manifest.yaml     kind: sample_manifest
        ↓ postprocess
processed/<tone-id>/manifest.yaml    kind: postprocess_manifest
```

波形処理そのものは、midi-sampling を知らない汎用 WAV ライブラリとして独立している。

| パッケージ | clone 先ディレクトリ名 | 役割 |
|---|---|---|
| [wav-silence-trimmer](https://github.com/r-koubou/sample-trimmer) | `sample-trimmer` | 前後の無音トリミングとフェード |
| [sample-loop-detector](https://github.com/r-koubou/sample-loop-detector) | `sample-loop-detector` | サステインループ検出と `smpl` チャンク埋め込み |

いずれも PyPI 未公開のため、導入手順は
[セットアップ](#ポストプロセストリミングループ検出も使う場合)を参照。

マニフェストには収録時に送信したノート番号が記録されているため、
`midi_unity_note: from_manifest` を使えば音高推定のオクターブ誤りが起こらない。

派生マニフェストだけでキーレンジ・ベロシティレンジ・ルートノート・ループ点を
再構築できるため、後続のパッチ生成はファイル名を解析する必要がない。

## 開発

```bash
# テスト実行
uv run pytest
```

仕様・設計ドキュメントは [.agents/](.agents/) を参照。

## ライセンス

MIT
