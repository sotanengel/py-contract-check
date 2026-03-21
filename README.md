# rust-contract-checks

Rust向けの Design by Contract ライブラリです。`life4/deal` の主要思想を参考にしつつ、
Rustの型システム、`Result`、macro展開、CI運用に合わせて再設計しています。

## 1. ライブラリ概要

`rust-contract-checks` は、関数やメソッドに対して以下の契約を宣言し、デバッグ時または
`always-contracts` feature 有効時に実行時検証するライブラリです。

- 前提条件
- 事後条件
- 不変条件
- 許可された失敗条件
- 純粋性の意図
- panic方針の意図

## 2. 何ができるか

- `#[contract(...)]` で契約を関数定義に近い位置へ書ける
- 契約違反を `ContractViolation` として構造化し、panic payload に載せられる
- `Result` を返すAPIの失敗経路を `error(...)` で明示できる
- 状態保持メソッドへ `invariant(...)` を付与できる
- 契約メタデータを `ContractMetadata` / `ContractClause` として表現できる
- property-based testing、examples、CIへ接続しやすい構成を持つ

## 3. 参考ライブラリへの謝意

このライブラリは Python 向け Design by Contract ライブラリ
[`life4/deal`](https://github.com/life4/deal) の思想と主要機能に敬意を払いつつ、
Rust向けに再設計したものです。

参考にした点:

- 前提条件、事後条件、不変条件、失敗条件を明示する設計
- テスト支援と解析接続を意識した契約メタデータの扱い
- 仕様意図をコード近傍へ置くことで、保守とAI支援をしやすくする方針

本実装は `deal` の表面的な移植ではなく、`Result`、stable Rust、feature flag、
proc-macro を前提にした Rust 流の再構成です。

## 4. クイックスタート

```bash
cargo add rust-contract-checks
```

```rust
use rust_contract_checks::contract;

#[derive(Debug, Clone, PartialEq, Eq)]
enum DivideError {
    DivisionByZero,
}

#[contract(
    pre(divisor != 0, "0で割る入力は許可しない"),
    post(*ret * divisor == dividend, "戻り値から元の被除数を復元できる"),
    error(matches!(err, DivideError::DivisionByZero), "0除算のみ許可する"),
    pure("入力以外の状態に依存しない"),
    panic_free("契約違反以外ではpanicしない")
)]
fn divide(dividend: i32, divisor: i32) -> Result<i32, DivideError> {
    if divisor == 0 {
        return Err(DivideError::DivisionByZero);
    }

    Ok(dividend / divisor)
}
```

標準挙動:

- デバッグビルドでは契約検証が有効
- リリースビルドでは無効
- `--features always-contracts` でリリースビルドでも有効
- `RUST_CONTRACT_CHECKS=0` で実行時無効化

## 5. 契約機能一覧

| 機能 | 記法 | 補足 |
| --- | --- | --- |
| 前提条件 | `pre(condition, "説明")` | 実行前に全件評価 |
| 事後条件 | `post(condition, "説明")` | `ret` を参照可能 |
| 不変条件 | `invariant(condition, "説明")` | メソッド前後で評価 |
| 失敗条件 | `error(condition, "説明")` | `Result::Err` のみ評価 |
| 純粋性 | `pure("説明")` | 現在は意図表明と軽いシグネチャ検査 |
| panic方針 | `panic_free("説明")` | 現在は意図表明 |

詳細は [docs/contracts.md](docs/contracts.md) を参照してください。

## 6. 例外・失敗表現

契約違反は通常の `Result` エラーと混同せず、`ContractViolation` として構造化して扱います。
attribute macro 経由では `panic_any` で送出されるため、テストでは panic payload を downcast して検査できます。

`error(...)` は `Result` ベースの失敗経路を対象とします。panic系は `panic_free(...)` で別枠の
メタデータとして扱い、将来的な静的解析やlint連携の拡張点としています。

## 7. テスト / CI 連携

- `cargo test --workspace --all-features --all-targets`
- `cargo test -p rust-contract-checks --doc`
- `cargo test -p rust-contract-checks --examples`
- `cargo clippy --workspace --all-targets --all-features -- -D warnings`
- `cargo fmt --all --check`
- `cargo audit`
- `cargo deny check licenses bans sources`

GitHub Actions では Linux / macOS / Windows の stable Rust を対象に検証します。

## 8. 生成AI向けの読み方

生成AIがこのリポジトリを読むときは、次の順序を推奨します。

1. この `README.md` の概要とクイックスタート
2. [docs/contracts.md](docs/contracts.md) の契約機能一覧
3. [examples/quickstart.rs](examples/quickstart.rs) と [tests/contracts.rs](tests/contracts.rs)
4. [ARCHITECTURE.md](ARCHITECTURE.md) の設計意図
5. [AGENTS.md](AGENTS.md) の変更方針

AI運用方針:

- 内部的な推論を英語で進める運用は許容
- 最終回答とコードコメントは日本語
- 公開API変更時は tests / examples / README を同時更新

## 9. 開発方法

ローカル:

```bash
make ci
```

Docker:

```bash
docker build -t rust-contract-checks .
docker run --rm -it -v "$PWD:/workspace" rust-contract-checks make ci
```

Dev Container は [`.devcontainer/devcontainer.json`](.devcontainer/devcontainer.json) を参照してください。

## 10. 制限事項

- 現時点では sync な関数 / メソッドのみ対応
- `const fn` は未対応
- `pure(...)` と `panic_free(...)` は主に意図表明であり、完全な静的保証ではない
- `no_std` は未対応
- 自動JSON / SARIF出力は未実装だが、`ContractViolation` の構造は拡張しやすい形にしている

## 11. ライセンス

MIT License。詳細は [LICENSE](LICENSE) を参照してください。
