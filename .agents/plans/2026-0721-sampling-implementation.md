# MIDI Sampling 初期実装:実装プラン

> **注記**: 本ドキュメントは実装セッション(2026-07-21〜22)で立てた作業計画の記録である。
> セッション中はエージェント内部のタスクリストとして保持していたものを、実施後に文書化した。
> 確定仕様の正本は `.agents/specs/midi-sampling/sampling_implementation.md` であり、本書は
> 作業手順・実装順序・計画段階の判断のみを扱う。

## Context

`.agents/specs/midi-sampling/sampling_implementation.md`(仕様バージョン1)の初期実装を行う。

着手時点の状態:

- `src/midi_sampling/sampling/` は `SamplingExecutor` の空クラスのみ
- デバイス層(`AudioDevice` / `MidiDevice` とその実装)は既存・流用
- `pyproject.toml` の `midi_sampling.cli:app` は参照先未実装
- テスト基盤なし

## 実装順序

依存関係の下流(葉)から上流へ積み上げる。各段階は前段のみに依存するため、
この順に実装すれば常にテスト可能な状態を保てる。

1. `exceptions.py` — 例外定義(仕様 §19)。全モジュールが参照する土台
2. `definitions/` — Pydantic DTO 4種(§4〜§8)。共有フィールド型
   (StrictInt ベースの MIDI 値、有限 float の秒値)を `field_types.py` に分離
3. `loading/` — YamlDefinitionLoader(§3.1)。UTF-8 / safe_load / 位置情報付きエラー変換
4. `validation/` — SemanticValidator(§5.3, §6.3)と OutputPathValidator(§12)
5. `resolving/` — DefinitionResolver(§9)。ResolvedSession / ResolvedTone への展開
6. `naming/` — SampleFilenameFormatter(§11.4)。限定フォーマッター
7. `hashing/` — ResolvedDefinitionHasher(§16)。canonical JSON → SHA-256
8. `planning/` — SamplingTarget / SamplingPlan / SamplingPlanBuilder(§10〜§12)
9. `manifest/` — SampleManifest モデルと SampleManifestRepository(§15)
10. `sampling_executor.py` — 実行シーケンス(§13〜§14)
11. `audit/` — AuditResult / AuditService(§17.2〜§17.3)
12. `cli.py` — typer による `run` / `audit`(§17)
13. テスト一式 — 仕様 §21 の全項目。実デバイス不使用(Fake デバイス)
14. pytest 導入・全テスト実行

## 計画段階の主要な判断

### 既存出力チェック(§12.3 / §16.5)の配置

SamplingExecutor.execute の先頭で行う。SamplingPlanBuilder には置かない。

- audit も builder を通るが、audit にとって既存出力は「エラー」ではなく「監査対象」
- builder は決定的・副作用なし(読み取り専用)を保ち、run / audit で共用する
- ハッシュ比較表示(§16.5)にはマニフェスト読込が必要で、executor は
  manifest repository を既に持っている

### DefinitionResolver への AudioDeviceInformationLoader 注入

ハッシュ対象に「オーディオ形式」(§16.3)が含まれるため、resolver が
オーディオデバイス定義を読む必要がある。sounddevice 実装への直接依存を避け、
既存の `AudioDeviceInformationLoader` プロトコルをコンストラクタ注入とする。
CLI は `SdAudioDeviceInformationLoader`、テストは Fake を渡す。

### 限定フォーマッターの実装方式(§11.4)

`str.format` を直接使わず、`string.Formatter().parse()` でテンプレートを分解し、
許可プレースホルダー集合との照合・属性/インデックスアクセス拒否・変換(`!r`)拒否・
入れ子拒否を検証してから、値ごとに `format(value, spec)` を適用する。

### 実行モデルの型

SamplingTarget / SamplingPlan は frozen dataclass(§10.2 の例示どおり)。
YAML 構造・外部参照・Pydantic モデルを保持しない。ゾーン等は planning 層の
ZoneSpec / VelocityLayerSpec に変換して持つ。

### 録音時間のフレーム変換(§8.5)

既存 `AudioDevice.start_recording(duration: int)` を `float`(秒)へ変更し、
`round(sample_rate * total_seconds)` の変換は SdAudioDevice 内で行う。
executor はデバイス実装の詳細(サンプルレート)を知らないままにする。

### テスト戦略(§21.9)

Fake デバイスは共有イベントリストへ全呼出しを記録し、呼出し順序
(録音開始 → pre_roll → Note On/Off → release_capture → 停止 → `.part` 書出 →
リネーム → マニフェスト更新 → inter_sample_wait)をリストの並びとして検証する。
sleep は注入可能にして実時間待機を排除する。

## 検証手順

1. `uv run pytest` — 全テスト成功(最終 134 件)
2. `midi-sampling audit examples/sessions/session.yaml` — 定義解決と終了コード(0/1/2)確認
3. 実デバイス(SC-8850 + Yamaha Steinberg USB ASIO)で `run` — 実録音・
   マニフェスト completed・audit up_to_date を確認(2026-07-22 実施済み)

## 結果

- 仕様 §22 の受入条件 14 項目すべて充足
- 実装中の追加修正: SdAudioDevice.export_audio に `format="WAV"` 明示
  (`*.wav.part` は拡張子からフォーマット推定不可のため)
- 経緯の詳細は `.agents/contexts/progress/progress.md` を参照
