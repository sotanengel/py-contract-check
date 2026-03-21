#![allow(missing_docs)]

use rust_contract_checks::{ContractKind, ContractLocation, ContractViolation, InputSnapshot};

fn main() {
    let violation = ContractViolation::new(
        "python_contracts_rs.divide",
        ContractKind::Precondition,
        "divisor != 0",
        ContractLocation::new("examples/quickstart.py", 8, 1),
        vec![InputSnapshot::described("divisor", "int", "0")],
    );

    println!("{}", violation.to_log_line());
}
