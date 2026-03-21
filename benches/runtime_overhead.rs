#![allow(missing_docs)]

use criterion::{criterion_group, criterion_main, Criterion};
use rust_contract_checks::{ContractKind, ContractLocation, ContractViolation, InputSnapshot};

fn plain_log_line() -> String {
    String::from("contract_violation|kind=precondition|function=python_contracts_rs.divide")
}

fn structured_log_line() -> String {
    ContractViolation::new(
        "python_contracts_rs.divide",
        ContractKind::Precondition,
        "divisor != 0",
        ContractLocation::new("examples/quickstart.py", 4, 1),
        vec![InputSnapshot::described("divisor", "int", "0")],
    )
    .to_log_line()
}

fn runtime_overhead(c: &mut Criterion) {
    c.bench_function("plain_log_line", |b| b.iter(plain_log_line));
    c.bench_function("structured_log_line", |b| b.iter(structured_log_line));
}

criterion_group!(benches, runtime_overhead);
criterion_main!(benches);
