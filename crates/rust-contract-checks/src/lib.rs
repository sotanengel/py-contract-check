#![doc = r#"
Rustで Design by Contract を扱うための軽量ライブラリです。

`life4/deal` の思想をRust向けに再設計し、前提条件、事後条件、不変条件、
失敗条件、純粋性の意図をコードとテストに埋め込めるようにします。

```rust
use rust_contract_checks::contract;

#[derive(Debug, Clone, PartialEq, Eq)]
enum DivideError {
    DivisionByZero,
}

#[contract(
    pre(divisor != 0, "0で割る入力は許可しない"),
    post(*ret * divisor == dividend, "戻り値から元の被除数を復元できる"),
    error(matches!(err, DivideError::DivisionByZero), "許可された失敗は0除算のみ"),
    pure("入力以外の状態に依存しない"),
    panic_free("契約違反を除きpanicしない")
)]
fn divide(dividend: i32, divisor: i32) -> Result<i32, DivideError> {
    if divisor == 0 {
        return Err(DivideError::DivisionByZero);
    }

    Ok(dividend / divisor)
}

assert_eq!(divide(8, 2), Ok(4));
```
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
pub use crate::runtime::{handle_violation, input_snapshot, invariant_violation, violation};

#[cfg(feature = "macros")]
pub use rust_contract_checks_macros::contract;

/// 実行時不変条件を自前でまとめたい型向けの補助トレイトです。
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
