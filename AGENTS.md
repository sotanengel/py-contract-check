# AGENTS Guide

このリポジトリで AI が変更を行うときの優先ガイドです。

このプロジェクトは **Python library implemented in Rust** です。Rust 単独ライブラリとして
解釈してはいけません。主成果物は Python API です。

## 最初に読む順序

1. `README.md`
2. `docs/contracts.md`
3. `ARCHITECTURE.md`
4. `examples/quickstart.py`
5. `tests/python/test_contracts.py`
6. `tests/contracts.rs`

## AI方針

- 内部推論を英語で行う運用は許容
- 最終回答文は日本語
- コード中のコメントは日本語
- Python API を主成果物として扱う
- README / examples / tests / docs は Python 優先で更新する
- 仕様変更時は README / examples / tests / docs を一緒に更新する

## コード規約

- 公開APIは `python/python_contracts_rs/` に集約する
- Rust crate は内部実装とバインディング支援として扱う
- 契約違反と通常エラーを混同しない
- Python の期待例外は `raises(...)` または `error(...)` で表す
- `panic_free(...)` と `pure(...)` は現段階では意図表明または軽い runtime 補助として扱う
- `unsafe` は禁止

## テスト規約

- 新機能には正常系と違反系の両方を追加
- 可能なら property-based test を検討
- Python と Rust の両方で examples が壊れていないことを確認

## 禁止事項

- 既存の unrelated change を巻き戻さない
- 公開APIを silently break しない
- README に書かれた Python-first 方針を崩さない

## 変更チェックリスト

- `make setup`
- `cargo fmt --all --check`
- `cargo clippy --workspace --all-targets --all-features -- -D warnings`
- `cargo test --workspace --all-features --all-targets`
- `cargo test -p rust-contract-checks --doc`
- `.venv/bin/python -m pytest tests/python`
- `.venv/bin/python -m mypy python`
- `.venv/bin/python examples/quickstart.py`
