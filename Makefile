.PHONY: setup fmt lint test doc examples bench audit license ci

setup:
	cargo fetch

fmt:
	cargo fmt --all

lint:
	cargo clippy --workspace --all-targets --all-features -- -D warnings

test:
	cargo test --workspace --all-features --all-targets

doc:
	cargo doc --workspace --all-features --no-deps

examples:
	cargo test -p rust-contract-checks --all-features --examples

bench:
	cargo bench -p rust-contract-checks --all-features --features always-contracts

audit:
	cargo audit

license:
	cargo deny check licenses bans sources

ci: fmt lint test doc examples
