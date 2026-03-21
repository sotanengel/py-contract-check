#![doc = r#"
`rust-contract-checks` は `python-contracts-rs` 向けの内部 Rust コアです。

主成果物は Python パッケージであり、この crate では契約種別、構造化違反情報、
設定判定、Rust 側の補助 API を提供します。Python 利用例はリポジトリ直下の
`README.md` と `examples/quickstart.py` を参照してください。
"#]
#![forbid(unsafe_code)]

extern crate self as rust_contract_checks;

mod config;
mod metadata;
mod report;
mod runtime;

pub use crate::config::{compile_time_contracts_enabled, contracts_enabled};
pub use crate::metadata::{ContractClause, ContractKind, ContractMetadata};
pub use crate::report::{ContractLocation, ContractViolation, InputSnapshot};
pub use crate::runtime::{
    handle_panic, handle_violation, input_snapshot, invariant_violation, violation,
};

#[cfg(feature = "macros")]
pub use rust_contract_checks_macros::contract;

/// 実行時不変条件を自前でまとめたい型向けの補助トレイトです。
#[allow(clippy::result_large_err)]
pub trait Invariant {
    /// 不変条件を検証し、違反時は `ContractViolation` を返します。
    fn check_invariants(&self) -> Result<(), ContractViolation>;
}

/// `Invariant` 実装を持つ値に対して契約違反panicを発生させます。
pub fn assert_invariants<T>(value: &T)
where
    T: Invariant,
{
    if !contracts_enabled() {
        return;
    }

    if let Err(violation) = value.check_invariants() {
        handle_violation(violation);
    }
}
