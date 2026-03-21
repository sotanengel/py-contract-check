#![allow(missing_docs)]

use std::{
    any::Any,
    panic::{catch_unwind, AssertUnwindSafe},
};

use proptest::prelude::*;
use rust_contract_checks::{contract, ContractKind, ContractViolation};

#[derive(Debug, Clone, PartialEq, Eq)]
enum MathError {
    DivisionByZero,
    Overflow,
}

#[contract(pre(value % 2 == 0, "偶数のみ受け付ける"), pure("副作用を持たない"))]
fn halve_even(value: i32) -> i32 {
    value / 2
}

#[contract(post(*ret > value, "戻り値は入力より大きくなければならない"))]
fn broken_increment(value: i32) -> i32 {
    value
}

#[contract(error(matches!(err, MathError::DivisionByZero), "0除算のみ許可"))]
fn checked_divide(dividend: i32, divisor: i32) -> Result<i32, MathError> {
    if divisor == 0 {
        return Err(MathError::DivisionByZero);
    }

    Ok(dividend / divisor)
}

#[contract(error(matches!(err, MathError::DivisionByZero), "0除算のみ許可"))]
fn broken_error(flag: bool) -> Result<i32, MathError> {
    if flag {
        return Err(MathError::Overflow);
    }

    Ok(1)
}

#[contract(
    pre(limit >= 0, "上限は非負"),
    post(*ret >= 0 && *ret <= limit, "結果は範囲内"),
    pure("入力のみで決まる")
)]
fn clamp_non_negative(value: i32, limit: i32) -> i32 {
    value.clamp(0, limit)
}

#[derive(Debug)]
struct Wallet {
    balance: i32,
}

impl Wallet {
    #[contract(invariant(self.balance >= 0, "残高は常に非負"))]
    fn debit(&mut self, amount: i32) {
        self.balance -= amount;
    }
}

#[test]
fn precondition_violation_contains_context() {
    let result = catch_unwind(AssertUnwindSafe(|| {
        let _ = halve_even(3);
    }));

    let violation = extract_violation(result);
    assert_eq!(violation.kind, ContractKind::Precondition);
    assert_eq!(violation.condition, "value % 2 == 0");
    assert_eq!(violation.inputs.len(), 1);
    assert_eq!(violation.inputs[0].name, "value");
    assert!(
        violation.function.ends_with("halve_even"),
        "unexpected function path: {}",
        violation.function
    );
}

#[test]
fn metadata_is_available_for_free_functions() {
    assert_eq!(
        __RUST_CONTRACT_CHECKS_METADATA_halve_even.clauses[0].kind,
        ContractKind::Precondition
    );
    assert_eq!(
        __RUST_CONTRACT_CHECKS_METADATA_halve_even.clauses[1].kind,
        ContractKind::Purity
    );
}

#[test]
fn postcondition_violation_is_reported() {
    let result = catch_unwind(AssertUnwindSafe(|| {
        let _ = broken_increment(5);
    }));

    let violation = extract_violation(result);
    assert_eq!(violation.kind, ContractKind::Postcondition);
    assert_eq!(violation.condition, "* ret > value");
}

#[test]
fn declared_error_contract_is_accepted() {
    assert_eq!(checked_divide(8, 0), Err(MathError::DivisionByZero));
}

#[test]
fn unexpected_error_contract_is_rejected() {
    let result = catch_unwind(AssertUnwindSafe(|| {
        let _ = broken_error(true);
    }));

    let violation = extract_violation(result);
    assert_eq!(violation.kind, ContractKind::ErrorContract);
    assert_eq!(
        violation.condition,
        "matches!(err, MathError::DivisionByZero)"
    );
}

#[test]
fn invariant_is_checked_after_state_change() {
    let mut wallet = Wallet { balance: 1 };

    let result = catch_unwind(AssertUnwindSafe(|| wallet.debit(2)));
    let violation = extract_violation(result);

    assert_eq!(violation.kind, ContractKind::Invariant);
    assert_eq!(violation.condition, "self.balance >= 0");
}

proptest! {
    #[test]
    fn property_test_keeps_range(value in -1000i32..1000, limit in 0i32..1000) {
        let result = clamp_non_negative(value, limit);
        prop_assert!(result >= 0);
        prop_assert!(result <= limit);
    }
}

fn extract_violation<T>(result: Result<T, Box<dyn Any + Send>>) -> ContractViolation {
    match result {
        Ok(_) => panic!("契約違反を期待したが成功しました"),
        Err(payload) => match payload.downcast::<ContractViolation>() {
            Ok(violation) => *violation,
            Err(_) => panic!("panic payload が ContractViolation ではありませんでした"),
        },
    }
}
