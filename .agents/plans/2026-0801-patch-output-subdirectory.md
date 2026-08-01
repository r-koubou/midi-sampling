# パッチのサブディレクトリ配置（output.subdirectory）

- 関連仕様: `.agents/specs/export_implementation.md` §3 / §3.2 / §7.1、`.agents/specs/kontakt1_nki_export.md`
- 前提プラン: `.agents/plans/2026-0731-shared-export-layout.md`
- 実行結果の記録: `.agents/contexts/progress/progress.md`「export パッチのサブディレクトリ配置(2026-08-01)」

## 全体のゴール

前回の改修で成果物はフォーマットごとに 1 箇所へまとまったが、`Instruments/` 直下は平坦なままである。10〜20 パッチなら問題ないが、**数百レベルになると視認・検索の負荷が上がる**。`name` の命名規則でソート順を整える工夫はできても平坦であること自体は変わらない。

パッチのみサブディレクトリへ配置できるようにする。

```
path/to/export/${format}/
├── Samples/${tone-id}/*.wav|.flac        ← 変わらずフラットな共有ツリー
└── Instruments/
    ├── <name>.<ext>                      ← output.subdirectory 省略時
    ├── 8850/Piano/8850-00-00-Piano1.nki
    └── 8850/Organ/8850-00-16-Organ1.nki
```

## 設計方針

### 1. `name` にスラッシュを許す案は採らない

`name` はファイル名だけでなく**パッチ内部のメタデータにも埋め込まれている**:

- NKI: `nki_xml.py` の `<NiSS_Program name="...">` — KONTAKT のラックに表示されるプログラム名
- SFZ: `sfz_patch_writer.py` の先頭コメント

`name` をパスとして解釈すると、KONTAKT の表示名が `8850/Piano/Piano1` になるか、最終セグメントだけを採ると `8850/…/Piano1` と `8851/…/Piano1` がラック上で区別できなくなる。**表示名と配置先は直交する概念**なので、専用フィールドで分離する（ユーザー決定）。

```yaml
name: 8850-00-00-Piano1     # ファイル名＋プログラム名
output:                     # 省略可
  subdirectory: 8850/Piano  # Instruments/ からの相対サブディレクトリ
```

省略時は従来どおり `Instruments/` 直下。**既存の定義ファイルは無修正で動く。**

### 2. `Samples/` は対象外

同じ tone-id を複数のインストゥルメントが共有するため、サンプルの置き場所は一意に定まらない。`Samples/<tone-id>/` はフラットな共有ツリーのまま維持する。

### 3. 検証は resolver に寄せ、共有バリデータを再利用する

`sources[].manifest` と同じく `ExportResolver` で検証し、例外は `ExportDefinitionError` に統一する。

- 既存の `_reject_unsupported_reference` — 空文字・URL・`~`・glob・絶対パスを拒否
- 各セグメントを `OutputPathValidator.validate_component`（`sampling/validation/`）へ — これ 1 本で不正文字・末尾ドット/スペース（**`.` と `..` はこれで弾かれ、出力ルート外への脱出を防ぐ**）・Windows 予約デバイス名・255 文字超を網羅
- 検証済みのセグメント列を `ResolvedInstrument.patch_subdirectory: tuple[str, ...]` に保持

### 4. `../` の深さを可変にする

`PATCH_TO_ROOT_PREFIX`（1 階層固定）を `PATCH_TO_ROOT_STEP` に改め、`1 + len(patch_subdirectory)` ぶん繰り返す。`Instruments/` の 1 階層＋サブディレクトリ階層。

### 5. Writer は無変更

executor が `patch_directory = output_root / Instruments / *subdirectory` を `mkdir(parents=True)` して渡すだけで、writer の契約（「パッチを `patch_directory` に書く」「`sample_path` はパッチからの相対」）は不変。前回の `PatchWriteContext` 再設計がそのまま効く。

## タスクリスト

### 実装

- [x] `export/definitions/instrument_definition.py`: `PatchOutputDefinition`（`extra="forbid"`、`subdirectory: StrictStr | None`）と `InstrumentDefinition.output` を追加、`definitions/__init__.py` へ re-export
- [x] `export/resolving/export_resolver.py`: `ResolvedInstrument.patch_subdirectory` と `_resolve_patch_subdirectory()`
- [x] `export/planning/export_plan.py`: `ExportPlan.patch_subdirectory`、`PATCH_TO_ROOT_PREFIX` → `PATCH_TO_ROOT_STEP`
- [x] `export/planning/export_plan_builder.py`: `_sample_reference_path` を深さ対応に
- [x] `export/export_executor.py`: サブディレクトリ連結と `validate_full_path`
- [x] `cli.py`: `--output` ヘルプと `export` docstring

### テスト

- [x] `tests/test_export_definitions.py`: `output` の既定値・受理・`extra="forbid"`
- [x] `tests/test_export_resolver.py`: 分割の正常系＋不正値 15 パターン（`..` / `.` / 絶対パス / `\` / URL / `~` / glob / 空 / 末尾スラッシュ / 連続スラッシュ / 予約名 / 末尾スペース）＋未クォート数値
- [x] `tests/test_export_plan_builder.py`: 深さ 0/1/2 で `../` の数が追従すること
- [x] `tests/test_export_executor.py`: ネスト作成・参照解決・異なるサブディレクトリの共存・パス長超過
- [x] `tests/test_export_cli.py`: e2e のネスト出力と不正値の exit 2
- [x] `tests/test_export_nki_writer.py`: 多階層で `..\..\..\Samples\…`、プログラム名にパスが混ざらないこと

### ドキュメント

- [x] `.agents/specs/export_implementation.md`: §3 スキーマ、§3.1 `name` の役割、§3.2 検証規則、§6、§7.1 に「パッチのサブディレクトリ」節
- [x] `.agents/specs/kontakt1_nki_export.md`: サブディレクトリ時の `file` 値とプログラム名
- [x] `examples/sessions/instrument.yaml`: コメント付きサンプル
- [x] `.agents/contexts/progress/progress.md`
- [x] 本プランの永続化

## 実行時に判明したこと

- **YAML の型の落とし穴**: `subdirectory: 8850` は YAML の整数になり `StrictStr` に弾かれる。プロジェクト共通の StrictStr 方針は維持し（`name` / `tone` も同様）、数字だけの階層はクォートが必要な旨を仕様と examples に明記、テストで挙動を固定した
- エラーメッセージは、値が単一セグメントのときに `'CON' (in 'CON')` と冗長になったため、全体値の併記はセグメントと異なる場合のみに絞った

## 懸念点

- ~~**多階層 `..` の実機解決は未検証**~~ → **解消**。2 階層構成（`Instruments/8850/Piano/`）で KONTAKT / Sforzando ともにサンプル missing なくロードできることを確認済み（ユーザー、2026-08-01）
- **stale ファイル**: `output.subdirectory` を変更すると旧パスのパッチが残留する。掃除機能は引き続きスコープ外
- 同一パスへのパッチ上書きは警告を出さない（再エクスポートは日常操作のため）。サンプル側のディレクトリ単位警告は現状維持
