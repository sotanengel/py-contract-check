#![allow(missing_docs)]

use criterion::{black_box, criterion_group, criterion_main, Criterion};
use rust_contract_checks::contract;

fn plain_abs(value: i32) -> i32 {
    value.abs()
}

#[contract(
    pre(value >= 0, "入力は非負"),
    post(*ret >= 0, "戻り値は非負"),
    pure("入力だけで結果が決まる")
)]
fn checked_abs(value: i32) -> i32 {
    value.abs()
}

fn runtime_overhead(c: &mut Criterion) {
    c.bench_function("plain_abs", |b| b.iter(|| plain_abs(black_box(42))));
    c.bench_function("checked_abs", |b| b.iter(|| checked_abs(black_box(42))));
}

criterion_group!(benches, runtime_overhead);
criterion_main!(benches);
