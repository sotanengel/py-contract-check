# Changelog

## 0.3.8 - 2026-03-22

- リポジトリの `LICENSE` 実体に合わせて package metadata を `Apache-2.0` へ修正
- PyPI README の相対リンクを GitHub の絶対 URL に置き換え、`LICENSE` を含むリンク切れを修正

## 0.3.7 - 2026-03-22

- `maturin` の `include` 設定で `LICENSE` を `sdist` へ明示同梱
- PyPI が `License-File LICENSE` を検証する際に `sdist` を reject する問題を修正

## 0.3.6 - 2026-03-22

- `sdist` を artifact 経由ではなく publish / release job 内で直接 build する構成へ変更
- `wheel` と `sdist` の公開入力を単純化し、PyPI で source distribution が欠落する問題を修正

## 0.3.5 - 2026-03-22

- `macOS` wheel を `universal2` build へ変更し、Apple Silicon と Intel の両方へ対応
- wheel と sdist の PyPI publish job を統合し、公開競合で sdist が落ちる問題を修正

## 0.3.4 - 2026-03-22

- release workflow から不安定な `macos-13` matrix を外し、`macOS` / `Linux` / `Windows` wheel 公開を優先
- `v0.3.3` の公開失敗を踏まえて release 導線を再調整

## 0.3.3 - 2026-03-22

- ソースツリーに混入した固定 `.so` を除去し、OS 依存バイナリをリポジトリへ含めない構成へ修正
- `pytest` をインストール済み拡張モジュール前提に変更し、開発時に in-tree ネイティブ成果物へ依存しないように調整
- CI / release workflow を `macOS` / `Linux` / `Windows` の wheel 配布へ拡張

## 0.3.2 - 2026-03-22

- release workflow を wheel / sdist 分離構成へ refactor
- sdist upload failure が GitHub release と wheel 配布を止めないように調整

## 0.3.1 - 2026-03-22

- release workflow に PyPI token fallback と配布物確認 step を追加
- `0.3.0` の callable-only 契約 API をそのまま再リリース

## 0.3.0 - 2026-03-22

- Python の `pre(...)` / `post(...)` / `invariant(...)` / `error(...)` から手書きの条件文字列引数を削除
- 構造化出力の `condition` を callable 名または例外型名ベースの導出ラベルへ統一
- README / docs / examples / tests を callable-only API に更新

## 0.2.0 - 2026-03-22

- 契約条項の補足 `message` を削除
- PyPI へのリリース導線を整備
- dependabot と PyO3 0.28 対応を反映

## 0.1.0 - 2026-03-22

- Python 公開 API `python_contracts_rs` を追加
- PyO3 バインディング `_native` を追加
- `pre` / `post` / `invariant` / `raises` / `error` / `pure` / `panic_free` を Python-first で再設計
- sync / async 関数の契約検証を追加
- async generator / async context manager の契約検証を追加
- `violation_to_dict` / `violation_to_json` / `metadata_to_dict` / `metadata_to_json` を追加
- `violation_to_sarif_result` / `violations_to_sarif` / `violations_to_sarif_json` を追加
- README / examples / tests / Docker / devcontainer / CI を Python-first に再構成
