# Contributing

## 前提

- Python 3.9+
- Rust stable
- `make`
- Docker は任意

## 基本コマンド

```bash
make setup
make fmt
make lint
make typecheck
make test
make doc
make ci
```

## 変更方針

- 公開API変更時は `CHANGELOG.md` を更新
- examples と tests を同時に更新
- Python 利用例を先に確認し、Rust 側の変更は内部実装として整理する
- 契約違反のメッセージ変更時はテストも見直す

## PR前チェック

```bash
cargo fmt --all --check
cargo clippy --workspace --all-targets --all-features -- -D warnings
cargo test --workspace --all-features --all-targets
cargo test -p rust-contract-checks --doc
.venv/bin/python -m pytest tests/python
.venv/bin/python -m mypy python
```
