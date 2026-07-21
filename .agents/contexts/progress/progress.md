# 現在の状態(2026-07-21 15:00 更新)

## 現状
- `.agents/specs/midi-sampling/sampling_implementation.md` の初期実装が完了
- `src/midi_sampling/sampling/` 以下に仕様書 §18 のモジュール構成どおり実装済み
  - definitions(Pydantic DTO)/ loading / resolving / validation / planning / naming / hashing / manifest / audit / sampling_executor / exceptions
- CLI `src/midi_sampling/cli.py` に `run` / `audit` サブコマンドを実装(pyproject の `midi_sampling.cli:app` と接続)
- `tests/` に単体・結合テスト一式(Fakeデバイス使用、実デバイス不使用)133件、全て成功
- pyproject に `[dependency-groups] dev = pytest` と `[tool.pytest.ini_options]`(pythonpath=src)を追加
- `AudioDevice.start_recording` の引数を秒数 float に変更し、SdAudioDevice 側で `round(duration * sample_rate)` でフレーム変換(仕様 §8.5)

## 未完了
- 実デバイスでの動作確認(SC-8850 等での実録音)は未実施

## 重要な判断・制約(なぜそうなっているか)
- 既存出力チェック(§12.3/§16.5)は SamplingExecutor.execute の先頭で実施。AuditService はプランのみ受け取り読み取り専用のため builder には置かない
- DefinitionResolver は AudioDeviceInformationLoader を注入する設計(テストでは Fake、CLI では SdAudioDeviceInformationLoader)。ハッシュにオーディオ形式を含めるため resolver がオーディオ定義を読む
- ファイル名テンプレートは str.format を直接使わず、string.Formatter.parse による限定フォーマッター(属性/インデックス/変換/入れ子拒否)
- ハッシュは正規化 dict → canonical JSON(sort_keys, separators, ensure_ascii=False, allow_nan=False)→ SHA-256。時間値は全て float 化して表現を統一

## 次回やること
1. 実デバイスでの `run` 動作確認

## 補足
- examples/sessions/ に定義サンプル一式を追加済み(audit で解決確認済み。2音色26サンプル)
- 初期化SMF examples/sessions/midi/gs_reset.mid は mido で生成した GS Reset sysex 入りSMF
- pyproject に `[build-system]`(uv_build)を追加しパッケージ化。`uv run midi-sampling run/audit` で実行可能
  - `[project.gui-scripts]` は `[project.scripts]` へ変更(gui-scripts だとWindowsで pythonw 起動になりコンソール出力が出ないため)
  - uv_build の要件で src/midi_sampling ほか欠けていた `__init__.py` を追加、readme 宣言に対応する README.md を新規作成
  - CLI終了コード実測: audit 未録音=1、定義エラー=2、--help=0
