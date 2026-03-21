# Architecture

## 目的

このリポジトリは、`life4/deal` の主要思想を Rust へ移し替える初期版です。
MVP段階では「契約を宣言できる」「違反を構造化できる」「テストとCIへ接続できる」
ことを優先しています。

## モジュール構成

- `crates/rust-contract-checks/src/config.rs`
  契約検証の有効 / 無効判定を担当します。
- `crates/rust-contract-checks/src/metadata.rs`
  契約種別と条項メタデータを保持します。
- `crates/rust-contract-checks/src/report.rs`
  `ContractViolation` とログ表現を定義します。
- `crates/rust-contract-checks/src/runtime.rs`
  入力スナップショット生成と違反送出を担当します。
- `crates/rust-contract-checks-macros/src/lib.rs`
  `#[contract(...)]` を展開して実行時検証コードへ落とし込みます。

## 現在のAPI設計

- 主要APIは `#[contract(...)]`
- free function では hidden metadata const を生成
- method では直接ラップのみ行い、trait impl でも壊れないことを優先
- `Result` 失敗条件は OR 条件として扱う
- 契約違反は `panic_any(ContractViolation)` で送出する

## 監査性

`ContractViolation::to_log_line()` は単一行フォーマットを返します。今後 JSON / SARIF を追加する場合も、
`ContractViolation` を共通データ構造として流用できます。

## 将来の拡張ポイント

- async / const fn 対応
- 生成した契約メタデータの収集用 `cargo contract-checks` サブコマンド
- `pure` / `panic_free` の lint 化
- property-based testing の自動入力生成補助
- JSON / SARIF / tracing 出力
