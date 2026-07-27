# MIT ライセンス採用可否の確認

## Context

ユーザーから「実行可能形式での配布はせず、ユーザー側で uv により依存関係をインストールする形態で、本ソフトを MIT ライセンスにして問題ないか」という質問を受けた。

## 結論(回答済み)

MIT ライセンスで問題ない。

- NumPy / SciPy / python-soundfile は BSD-3-Clause(寛容型)で MIT と完全に両立。帰属表示は作成済みの NOTICE.md で充足。
- libsndfile は LGPL だが、ソース配布のみで LGPL コードを再配布しないため義務が発生しない。将来バイナリ同梱する場合も動的リンクのため MIT のまま対応可能。

## 実装作業

なし。LICENSE ファイルと pyproject.toml の `license = "MIT"` はユーザー自身が追加済みのため、追加作業は不要。
