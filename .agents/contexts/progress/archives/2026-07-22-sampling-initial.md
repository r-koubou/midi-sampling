# アーカイブ: サンプリング初期実装(〜2026-07-22)

`sampling_implementation.md` の初期実装完了時点のコンテキスト。

## 実装内容
- `src/midi_sampling/sampling/` 以下に仕様書 §18 のモジュール構成どおり実装
  - definitions(Pydantic DTO)/ loading / resolving / validation / planning / naming / hashing / manifest / audit / sampling_executor / exceptions
- CLI `src/midi_sampling/cli.py` に `run` / `audit` サブコマンドを実装(pyproject の `midi_sampling.cli:app` と接続)
- `tests/` に単体・結合テスト一式(Fakeデバイス使用、実デバイス不使用)134件
- pyproject に `[dependency-groups] dev = pytest` と `[tool.pytest.ini_options]`(pythonpath=src)を追加
- `AudioDevice.start_recording` の引数を秒数 float に変更し、SdAudioDevice 側で `round(duration * sample_rate)` でフレーム変換(仕様 §8.5)

## 重要な判断・制約
- 既存出力チェック(§12.3/§16.5)は SamplingExecutor.execute の先頭で実施。AuditService はプランのみ受け取り読み取り専用のため builder には置かない
- DefinitionResolver は AudioDeviceInformationLoader を注入する設計(テストでは Fake、CLI では SdAudioDeviceInformationLoader)。ハッシュにオーディオ形式を含めるため resolver がオーディオ定義を読む
- ファイル名テンプレートは str.format を直接使わず、string.Formatter.parse による限定フォーマッター(属性/インデックス/変換/入れ子拒否)
- ハッシュは正規化 dict → canonical JSON(sort_keys, separators, ensure_ascii=False, allow_nan=False)→ SHA-256。時間値は全て float 化して表現を統一

## 実デバイス検証(2026-07-22)
- SC-8850 + Yamaha Steinberg USB ASIO で `run` 実録音成功(cello 1ゾーン×2レイヤー、8.0s×2本、PCM_24/48kHz/2ch、無音でないことをRMSで確認)、audit も up_to_date / exit 0
- 修正: SdAudioDevice.export_audio に `format="WAV"` を明示指定
  (一時ファイル `*.wav.part` は拡張子からフォーマット推定できず TypeError になっていた)。
  リグレッションテスト tests/test_sd_audio_device_export.py 追加

## パッケージ化
- examples/sessions/ に定義サンプル一式を追加(audit で解決確認済み。2音色26サンプル)
- 初期化SMF examples/sessions/midi/gs_reset.mid は mido で生成した GS Reset sysex 入りSMF
- pyproject に `[build-system]`(uv_build)を追加しパッケージ化。`uv run midi-sampling run/audit` で実行可能
  - `[project.gui-scripts]` は `[project.scripts]` へ変更(gui-scripts だとWindowsで pythonw 起動になりコンソール出力が出ないため)
  - uv_build の要件で src/midi_sampling ほか欠けていた `__init__.py` を追加、readme 宣言に対応する README.md を新規作成
  - CLI終了コード実測: audit 未録音=1、定義エラー=2、--help=0
