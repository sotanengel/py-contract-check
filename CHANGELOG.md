# Changelog

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
