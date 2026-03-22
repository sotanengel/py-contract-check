# contract-check

[![Sponsor](https://img.shields.io/badge/Sponsor-GitHub-ea4aaa?logo=githubsponsors&logoColor=white)](https://github.com/sponsors/sotanengel)

This is a design-by-contract library for Python, implemented in Rust.

`contract-check` is a Python-first design-by-contract library. The public API is built around
Python decorators, while Rust provides the runtime core and structured violation payloads.
The project is inspired by [`life4/deal`](https://github.com/life4/deal), but is redesigned for
distribution, observability, AI-assisted development, and mixed Python/Rust workflows.

## Quick Start

```bash
pip install contract-check
```

PyPI wheels are published for:

- `macOS`
- `Linux`
- `Windows`

`macOS` wheels use `universal2` to support both Apple Silicon and Intel.

```python
from __future__ import annotations

import asyncio

from contract_check import (
    ContractViolationError,
    ViolationDetail,
    contract,
    invariant,
    invariant_class,
    post,
    pre,
    pure,
    raises,
    read_only,
)


def divisor_is_not_zero(divisor: int) -> bool:
    return divisor != 0


def quotient_matches_dividend(result: int, dividend: int, divisor: int) -> bool:
    return result * divisor == dividend


def value_is_positive(value: int) -> ViolationDetail | None:
    if value > 0:
        return None
    return ViolationDetail(
        code="value.non_positive",
        message="value must be positive",
        field_path="/value",
        actual=value,
        expected="value > 0",
    )


def result_is_incremented(result: int, value: int) -> bool:
    return result == value + 1


def balance_is_non_negative(self: "Wallet") -> bool:
    return self.balance >= 0


@contract(
    pre(divisor_is_not_zero),
    post(quotient_matches_dividend),
    raises(ZeroDivisionError),
    pure(),
)
def divide(dividend: int, divisor: int) -> int:
    if divisor == 0:
        raise ZeroDivisionError("division by zero")
    return dividend // divisor


@contract(
    pre(value_is_positive),
    post(result_is_incremented),
)
async def async_increment(value: int) -> int:
    await asyncio.sleep(0)
    return value + 1


@invariant_class(
    invariant(balance_is_non_negative, policy="mutating_only"),
)
class Wallet:
    def __init__(self, balance: int) -> None:
        self.balance = balance

    def debit(self, amount: int) -> None:
        self.balance -= amount

    @read_only
    def current_balance(self) -> int:
        return self.balance


assert divide(12, 3) == 4
assert asyncio.run(async_increment(2)) == 3
```

Distribution and import names:

- The PyPI distribution name is `contract-check`
- The primary Python import name is `contract_check`
- The legacy `python_contracts_rs` import remains supported as a backwards-compatible alias
- `python_contracts_rs` will not be silently removed before a future `1.x` migration plan is documented

Default behavior:

- Contracts work for both sync and async call paths
- Set `PYTHON_CONTRACTS_RS=0` to disable runtime checks
- Contract violations are raised as `ContractViolationError` with structured fields such as `code`, `message`, `field_path`, `actual`, `expected`, `contract_phase`, and `predicate_name`
- Predicates may return either `bool` or `ViolationDetail | None`
- `pre(...)`, `post(...)`, `invariant(...)`, and `error(...)` accept callables rather than handwritten condition strings
- `condition` stores a derived label such as a callable name or exception type name

## Features

| Feature | Python API | Notes |
| --- | --- | --- |
- Preconditions | `pre(...)` | Validated before sync, async, and async-generator execution |
- Postconditions | `post(...)` | Return values are available as `result` or `ret` |
- Invariants | `invariant(...)` / `@invariant_class(...)` | Controlled with `policy=`, `cost=`, `@read_only`, and `@mutating` |
- Expected exceptions | `raises(...)` / `error(...)` | Only declared exceptions are allowed through |
- Purity marker | `pure(...)` | Currently an intent marker |
- Panic policy | `panic_free(...)` | Converts unexpected exceptions into contract violations |
- Rich violations | `ViolationDetail` | Structured payloads for APIs and logs |
- Typed predicates | `PrePredicate` / `PostPredicate` / `InvariantPredicate` / `ErrorPredicate` | Typing support for `Protocol`, mypy, and pyright |
- Testing helpers | `collect_violations(...)` / `assert_valid(...)` / `validate_payload(...)` | Evaluate predicates directly without decorators |
- Runtime controls | `contract_runtime(...)` | Toggle `debug_only` and `expensive` invariants per context |
- Contract metadata | `get_contract_metadata(...)` | Useful for documentation and test helpers |
- Structured output | `violation_to_dict(...)` / `violation_to_json(...)` | CI- and audit-log-friendly output |
- SARIF output | `violation_to_sarif_result(...)` / `violations_to_sarif(...)` | Integration with GitHub code scanning |

Further reading:

- [docs/contracts.md](https://github.com/sotanengel/py-contract-check/blob/main/docs/contracts.md)
- [docs/typed-predicates.md](https://github.com/sotanengel/py-contract-check/blob/main/docs/typed-predicates.md)
- [docs/invariant-policies.md](https://github.com/sotanengel/py-contract-check/blob/main/docs/invariant-policies.md)
- [docs/testing.md](https://github.com/sotanengel/py-contract-check/blob/main/docs/testing.md)

## Repository Layout

- `python/python_contracts_rs/`
  Python public API and decorator implementation.
- `python/contract_check/`
  Primary import alias that re-exports the legacy `python_contracts_rs` package.
- `bindings/python-contracts-rs/`
  PyO3-based Python/Rust bindings.
- `crates/rust-contract-checks/`
  Rust core for contract kinds, violation reporting, and runtime config.
- `examples/quickstart.py`
  Minimal Python user example.
- `examples/typed_predicates.py`
  Typed predicate and `Protocol` example.
- `tests/python/test_contracts.py`
  Python API integration tests.
- `tests/contracts.rs`
  Rust core regression tests.

## 生成 AI 向け案内

このプロジェクトは **Python library implemented in Rust** です。Rust 単独ライブラリとして
読まないでください。読む順序は次を推奨します。

1. この `README.md`
2. [docs/contracts.md](https://github.com/sotanengel/py-contract-check/blob/main/docs/contracts.md)
3. [examples/quickstart.py](https://github.com/sotanengel/py-contract-check/blob/main/examples/quickstart.py)
4. [tests/python/test_contracts.py](https://github.com/sotanengel/py-contract-check/blob/main/tests/python/test_contracts.py)
5. [ARCHITECTURE.md](https://github.com/sotanengel/py-contract-check/blob/main/ARCHITECTURE.md)
6. [AGENTS.md](https://github.com/sotanengel/py-contract-check/blob/main/AGENTS.md)

AI 運用方針:

- 主成果物は Python API として扱う
- 内部推論を英語で行う運用は許容
- 最終回答とコードコメントは日本語
- 仕様変更時は README / examples / tests / docs を同時更新

## 開発

ローカル開発:

```bash
make setup
make ci
```

Docker:

```bash
docker build -t contract-check .
docker run --rm -it -v "$PWD:/workspace" contract-check make ci
```

Dev Container は [`.devcontainer/devcontainer.json`](https://github.com/sotanengel/py-contract-check/blob/main/.devcontainer/devcontainer.json) を参照してください。

## 現状の制限

- `@invariant_class(...)` は public instance method と `__init__` を対象にします
- private / dunder / staticmethod / classmethod への自動適用は明示設定または将来拡張の対象です
- `pure(...)` は意図表明です
- tracing backend は未実装です

## ライセンス

Apache License 2.0。詳細は [LICENSE](https://github.com/sotanengel/py-contract-check/blob/main/LICENSE) を参照してください。
