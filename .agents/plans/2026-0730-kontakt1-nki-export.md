# KONTAKT 1 NKI エクスポート

## 全体のゴール

SFZ エクスポートと同様に、export 階層へ KONTAKT 1 形式（`.nki`）の具象
`InstrumentPatchWriter` を追加する。`instrument_definition` の
`exclusive_groups` / `release_triggers` を KONTAKT 1 の Group / VoiceGroup /
releaseTrigger で表現し、自己完結した `patches/nki/<name>/` 出力を生成する。

## 確定事項

| 項目 | 決定 |
|---|---|
| format_id | `nki`（directory_name は既定のまま） |
| 既定 Group 名 | `default`（index 0、常に出力） |
| exclusive_groups | Group `exec_%02d`（0 オリジン、定義順）。実体は Polyphony の VoiceGroup（maxNumVoices=1）への参照 |
| release_triggers | Group `release_%02d`（0 オリジン、regions 初出順）+ `releaseTrigger=yes` |
| 併存 | 複合 Group `exec_%02d_release_%02d`、両方を設定 |
| rt_decay | KONTAKT 1 に相当パラメーターなし → 無視して警告ログ |
| audio.format=flac | nki では無視して警告ログ、常に WAV を使用 |
| エンベロープ | Group の volume AHDSR。attack/release 秒→ミリ秒、hold=0、decay=500ms、sustain=1.0 |
| XML 細部 | `examples/kontakt/example_kontakt_v1.nki` の実ファイルをテンプレートとして踏襲（CRLF、version 属性、パラメーター順序） |

## タスクリスト

- [x] 実 .nki（examples/kontakt/example_kontakt_v1.nki）を解析し XML 構造・version・パラメーターを確定
- [x] .agents/plans / .agents/specs ドキュメント作成
- [x] `InstrumentPatchWriter` に `supported_audio_formats` プロパティ追加 + SFZ テスト拡張
- [x] `ExportPlanBuilder.build` に音声フォーマットフォールバック追加 + テスト
- [x] cli.py で `supported_audio_formats` を builder へ配線
- [x] `nki_impl/wav_info.py`（RIFF スキャン）+ テスト
- [x] `nki_impl/nki_grouping.py`（Group 分割純関数）+ テスト
- [x] `nki_impl/nki_xml.py` / `nki_impl/nki_binary.py`
- [x] `nki_impl/nki_patch_writer.py`（NkiPatchWriter 本体）
- [x] `export/__init__.py` ファクトリ更新（`SUPPORTED_PATCH_FORMATS` に nki 追加）
- [x] `tests/test_export_nki_writer.py` 作成
- [x] `tests/test_export_cli.py` 修正（偽フォーマット ID 変更・nki E2E・flac→wav 強制）
- [x] `uv run pytest` 全緑（309 件）
- [x] `.agents/specs/export_implementation.md` 更新・contexts へ記録・本プランのチェック更新
- [x] 受け入れ: 生成 .nki を実 KONTAKT で読み込み確認（人間側、2026-07-30 ロード・演奏可を確認）
- [x] 実機フィードバック反映: loopTuning 0→1（周波数比。0 は -12st と解釈されループ停止）、
      filterCutoff/pitch モジュレーター削除、インサート FX（Program FX・Group Filter/FX）削除
- [x] FX 完全削除はパーサエラー（固定順読み）と判明 → FX スロット復元・Filter は bypass=yes 化
- [x] フィードバック反映後ビルドの再読み込み確認（人間側、2026-07-30 ロード・サスティンループ動作を確認）

## 懸念点・設計方針

- 実ファイル照合により version 属性・yes/no・CRLF・`<Loops/>`（空要素）は確定済み。
- `sampleEnd` は実ファイルでは 0 だったが、本実装では実フレーム数を書く
  （0 は変換元ツールの省略の可能性。KONTAKT 読み込み確認で要検証）。
- ループありの `Loop` 要素は実ファイルに例が無く、研究文書 §13 準拠 +
  `version="0.60"`（推定）。KONTAKT 読み込み確認で要検証。
- 排他表現は VoiceGroup（maxNumVoices=1, kill_oldest）方式。
  `exclusionGroup` パラメーターは -1 のまま使用しない。
- KONTAKT 1 全リビジョンでの互換性は保証外（研究文書 §16.3）。
