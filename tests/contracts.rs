#![allow(missing_docs)]

use std::panic::{catch_unwind, AssertUnwindSafe};

use rust_contract_checks::{
    assert_invariants, ContractKind, ContractLocation, ContractViolation, InputSnapshot, Invariant,
};

#[derive(Debug)]
struct Balance {
    amount: i32,
}

impl Invariant for Balance {
    fn check_invariants(&self) -> Result<(), ContractViolation> {
        if self.amount >= 0 {
            return Ok(());
        }

        Err(ContractViolation::new(
            "python_contracts_rs.Balance",
            ContractKind::Invariant,
            "self.amount >= 0",
            Some("残高は負になってはいけない"),
            ContractLocation::new("tests/contracts.rs", 1, 1),
            vec![InputSnapshot::described(
                "amount",
                "int",
                self.amount.to_string(),
            )],
        ))
    }
}

#[test]
fn violation_log_line_contains_expected_fields() {
    let violation = ContractViolation::new(
        "python_contracts_rs.divide",
        ContractKind::Precondition,
        "divisor != 0",
        Some("0で割る入力は許可しない"),
        ContractLocation::new("tests/python/test_contracts.py", 10, 1),
        vec![InputSnapshot::described("divisor", "int", "0")],
    )
    .with_details("ZeroDivisionError: division by zero");

    let line = violation.to_log_line();

    assert!(line.contains("kind=precondition"));
    assert!(line.contains("function=python_contracts_rs.divide"));
    assert!(line.contains("condition=divisor != 0"));
    assert!(line.contains("details=ZeroDivisionError: division by zero"));
}

#[test]
fn display_includes_inputs() {
    let violation = ContractViolation::new(
        "python_contracts_rs.only_even",
        ContractKind::Precondition,
        "value % 2 == 0",
        Some("偶数のみ受け付ける"),
        ContractLocation::new("tests/python/test_contracts.py", 20, 1),
        vec![InputSnapshot::described("value", "int", "3")],
    );

    let rendered = violation.to_string();

    assert!(rendered.contains("契約違反 [precondition]"));
    assert!(rendered.contains("入力: value: int (3)"));
}

#[test]
fn assert_invariants_panics_with_contract_violation() {
    let balance = Balance { amount: -1 };
    let result = catch_unwind(AssertUnwindSafe(|| assert_invariants(&balance)));

    let violation = extract_violation(result);
    assert_eq!(violation.kind, ContractKind::Invariant);
    assert_eq!(violation.condition, "self.amount >= 0");
}

fn extract_violation<T>(result: Result<T, Box<dyn std::any::Any + Send>>) -> ContractViolation {
    match result {
        Ok(_) => panic!("契約違反を期待したが成功しました"),
        Err(payload) => match payload.downcast::<ContractViolation>() {
            Ok(violation) => *violation,
            Err(_) => panic!("panic payload が ContractViolation ではありませんでした"),
        },
    }
}
