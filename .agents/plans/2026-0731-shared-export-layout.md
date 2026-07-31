# エクスポート出力レイアウトの共有化（Samples / Instruments）

- 関連仕様: `.agents/specs/export_implementation.md` §7.1、`.agents/specs/kontakt1_nki_export.md`
- 実行結果の記録: `.agents/contexts/progress/progress.md`「export 出力レイアウトの共有化(2026-07-31)」

## 全体のゴール

エクスポート成果物を「パッチ単位の自己完結ディレクトリ」から「フォーマット単位の共有ツリー」へ変更する。

変更前:

```
path/to/export/${format}/${name}/
├── ${name}.${ext}
└── Samples/${tone-id}/*.wav|.flac
```

変更後:

```
path/to/export/${format}/
├── Samples/
│   ├── ${tone-id1}/*.wav|.flac
│   └── ${tone-id2}/*.wav|.flac
└── Instruments/
    ├── ${name1}.${ext}
    └── ${name2}.${ext}
```

**背景**: インストゥルメントが増えるほどサンプルとパッチが分散し、実際のサンプラーソフト（KONTAKT / sforzando）上でファイルを探しにくい。1 箇所にまとめる。これは KONTAKT ライブラリの慣習的レイアウト（`Instruments/` + `Samples/` がライブラリルート直下）とも一致する。

**既存仕様とのバッティング**: 複数インストゥルメントが同じフォーマットルートへ追記していく運用が前提になるため、**export に限り**「出力先が空でなければエラー」の既存ルールを撤廃する。サンプリング・ポストプロセスの既存出力チェックはそのまま維持する。

### 確定済みの方針（ユーザー判断）

- 新レイアウトは無条件に置き換える（旧レイアウトは残さない／CLI オプションも追加しない）
- `Samples/${tone-id}/` はインストゥルメント間で共有する。既存サンプルを上書きする際は警告ログを出したうえで処理を継続する

## 設計方針

### 1. 2 種類の相対パスを分離する

変更前は 1 本の文字列を `AudioExportTask.relative_path` と `InstrumentRegion.sample_path` の両方に使い回していた。新レイアウトでは基準が異なるため分離する。

| 用途 | 基準 | 値 |
|---|---|---|
| `AudioExportTask.relative_path` | フォーマットルート | `Samples/${tone-id}/${stem}${suffix}`（変更なし） |
| `InstrumentRegion.sample_path` | **パッチファイル** | `../Samples/${tone-id}/${stem}${suffix}` |

`sample_path` の契約は `instrument_model.py` に元から「パッチファイルからの相対 POSIX パス」と書かれているため、**契約は不変で値だけが変わる**。SFZ の `sample=` は POSIX 区切りのまま、NKI は `nki_xml.py` の `replace("/", "\\")` により `..\Samples\...` になる。

### 2. Writer へ渡すのはパッチ配置先ディレクトリ

`PatchWriteContext.output_directory` を `patch_directory`（＝ `<root>/Instruments`）へ置き換える。「パッチは `patch_directory` に書く」「`sample_path` はパッチからの相対」という 1 つの一貫した契約になり、writer 側にレイアウト知識（`Instruments` という名前）が漏れない。NKI writer のエクスポート済み WAV 読み戻しも `patch_directory / region.sample_path` で解決する（`..` は pathlib がそのまま扱える）。

## タスクリスト

### 実装

- [x] `export/planning/export_plan.py`: `INSTRUMENTS_DIRECTORY_NAME` と `PATCH_TO_ROOT_PREFIX` を追加。`AudioExportTask.relative_path` の docstring を「出力ルート基準」と明記。`planning/__init__.py` へ re-export
- [x] `export/planning/export_plan_builder.py`: `_relative_sample_path` を `_sample_output_path`（ルート基準）と `_sample_reference_path`（パッチ基準）に分離
- [x] `export/abstractions/instrument_patch_writer.py`: `PatchWriteContext.output_directory` → `patch_directory`。`directory_name` の docstring を新レイアウトへ
- [x] `export/sfz_impl/sfz_patch_writer.py` / `export/nki_impl/nki_patch_writer.py`: `context.patch_directory` を使用
- [x] `export/export_executor.py`: 引数を `output_root` へ改名、既存出力チェックを削除、`Instruments/` を作成、`Samples/<tone-id>/` 単位の上書き警告を追加
- [x] `export/exceptions.py`: `ExportExistingOutputError` を削除
- [x] `cli.py`: 出力先を `output_root / writer.directory_name` へ。`--output` ヘルプとコマンド docstring を更新

### テスト

- [x] `tests/test_export_cli.py`: 全レイアウト期待値を更新。`test_existing_output_is_refused` を撤去し、再エクスポート成功と 2 楽器のフォーマットルート共有を検証するテストへ差し替え
- [x] `tests/test_export_plan_builder.py`: `sample_path` == `../` + `relative_path` を明示検証するテストを追加
- [x] `tests/test_export_sfz_writer.py` / `tests/test_export_nki_writer.py`: `patch_directory` へ移行。NKI フィクスチャは `Instruments/` を作ってそこから `../Samples/...` を解決
- [x] `tests/test_export_executor.py` を新規作成（レイアウト分割・上書き許容・警告の粒度）

### ドキュメント

- [x] `.agents/specs/export_implementation.md`: §2-4（既存出力の扱い）・§4（writer 契約）・§5（サンプル出力先）・§6（`sample=`）・§7 + §7.1 新設（出力レイアウト）
- [x] `.agents/specs/kontakt1_nki_export.md`: レイアウト図と WAV 読み戻しの記述
- [x] `.agents/contexts/progress/progress.md`: 実行結果を記録
- [x] `examples/sessions/instrument.yaml`: 出力先コメントを新レイアウトへ
- [x] 本プランの永続化

## 懸念点

- ~~**KONTAKT 1 / sforzando が `..` を解決するか**は実機未検証~~ → **解消**。実機で読み込み確認済み（ユーザー、2026-07-31）。`Instruments/` 配下のパッチから `../Samples/...` を正しく参照できる
- **パス長**: `Instruments/` 階層が増える一方 `<name>/` 階層が減るため、Windows の 260 文字制限に対しては概ね中立。export は元々 `output_path_validator` を使っていないため本改修でも導入しない（スコープ外）
- **上書き許容の副作用**: 定義から削除された tone のサンプルが `Samples/` に残留する。掃除機能はスコープ外とし、仕様書に既知の挙動として明記した

## 実行時に判明したこと

- 上書き警告を**サンプル 1 件ごと**に出す実装では、90 サンプルの再エクスポートで警告が 90 行出て実用に耐えなかった。衝突の単位は tone-id であるため、`Samples/<tone-id>/` **ディレクトリにつき 1 回**へ集約した（`ExportExecutor._warn_on_occupied_sample_directories`）
