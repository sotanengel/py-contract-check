# Changelog

## 0.1.0 - 2026-03-22

- Python 公開 API `python_contracts_rs` を追加
- PyO3 バインディング `_native` を追加
- `pre` / `post` / `invariant` / `raises` / `error` / `pure` / `panic_free` を Python-first で再設計
- sync / async 関数の契約検証を追加
- async generator / async context manager の契約検証を追加
- `violation_to_dict` / `violation_to_json` / `metadata_to_dict` / `metadata_to_json` を追加
- `violation_to_sarif_result` / `violations_to_sarif` / `violations_to_sarif_json` を追加
- README / examples / tests / Docker / devcontainer / CI を Python-first に再構成
