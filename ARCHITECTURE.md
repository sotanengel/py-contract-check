# Architecture

## 目的

このリポジトリの主成果物は Python パッケージ `contract-check` です。Rust は
実装言語と安全性基盤として使い、Python 利用者には decorator ベースの自然な API を提供します。
配布名は `contract-check`、import 名は `python_contracts_rs` を維持します。
MVP では次を優先します。

- Python から自然に書ける契約 API
- 例外と契約違反を分離した構造化エラー
- Python/Rust の両方で回るテストと CI 導線

## モジュール構成

- `python/python_contracts_rs/contracts.py`
  Python 公開 decorator と runtime orchestration を担当します。
- `python/python_contracts_rs/__init__.py`
  Python 公開 API のエクスポート面です。
- `bindings/python-contracts-rs/src/lib.rs`
  PyO3 で `ContractViolation`、`ContractMetadata`、設定関数を Python へ公開します。
- `crates/rust-contract-checks/src/config.rs`
  契約検証の有効 / 無効判定を担当します。
- `crates/rust-contract-checks/src/metadata.rs`
  Rust 側の契約種別と条項表現です。
- `crates/rust-contract-checks/src/report.rs`
  Rust 側の構造化違反データとログフォーマットです。

## データの流れ

1. Python 利用者が `@contract(...)` に clause を宣言します。
2. `contracts.py` が sync / async 関数、async generator、async context manager の呼び出し前後で predicate を評価します。
3. 違反時は PyO3 側の `_native.ContractViolation` を生成します。
4. Python 側では `ContractViolationError` として送出し、`to_dict()` / `to_json()` や helper 関数で構造化情報を検査します。

## 設計上の判断

- 主語は常に Python 利用者です。Rust crate は内部実装として扱います。
- `raises(...)` / `error(...)` は Python の例外フローに合わせて設計します。
- 契約条項に手書きの説明文字列は持たせず、predicate callable 自体を仕様として扱います。
- 構造化出力の `condition` には callable 名や例外型名のような導出ラベルを使います。
- `pure(...)` は現段階では意図表明に留め、将来 lint や静的解析へ接続します。
- `panic_free(...)` は想定外例外を契約違反へ変換する宣言です。
- `@invariant_class(...)` は class 定義時に public instance method へ invariant を注入します。

## 将来の拡張ポイント

- Hypothesis などとの自動連携
- tracing backend
