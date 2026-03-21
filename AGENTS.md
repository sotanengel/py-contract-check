# AGENTS Guide

このリポジトリで AI が変更を行うときの優先ガイドです。

## 最初に読む順序

1. `README.md`
2. `docs/contracts.md`
3. `ARCHITECTURE.md`
4. `examples/quickstart.rs`
5. `tests/contracts.rs`

## AI方針

- 内部推論を英語で行う運用は許容
- 最終回答文は日本語
- コード中のコメントは日本語
- 仕様変更時は README / examples / tests を一緒に更新

## コード規約

- 公開APIは `rust-contract-checks` crate に集約する
- 契約違反と通常エラーを混同しない
- `Result` の失敗契約は `error(...)` で表す
- `panic_free(...)` と `pure(...)` は現段階では意図表明として扱う
- `unsafe` は禁止

## テスト規約

- 新機能には正常系と違反系の両方を追加
- 可能なら property-based test を検討
- examples が壊れていないことを確認

## 禁止事項

- 既存の unrelated change を巻き戻さない
- 公開APIを silently break しない
- README に書かれた feature flag 方針を崩さない

## 変更チェックリスト

- `cargo fmt --all --check`
- `cargo clippy --workspace --all-targets --all-features -- -D warnings`
- `cargo test --workspace --all-features --all-targets`
- `cargo test -p rust-contract-checks --doc`
- `cargo test -p rust-contract-checks --examples`
