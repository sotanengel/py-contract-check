# Typed Predicates

`contract-check` は `Protocol` と generic な predicate 型を公開し、mypy / pyright で
補完と整合性確認をしやすくしています。

## 代表型

- `PrePredicate[TParams]`
- `PostPredicate[TReturn, TParams]`
- `InvariantPredicate[TSelf]`
- `ErrorPredicate[TException, TParams]`
- `ValidationResult`

## `Protocol` を使う例

```python
from __future__ import annotations

from typing import Protocol

from contract_check import InvariantPredicate, ViolationDetail, contract, invariant, pre


class HasBalance(Protocol):
    balance: int


def balance_is_non_negative(self: HasBalance) -> bool:
    return self.balance >= 0


typed_balance_invariant: InvariantPredicate[HasBalance] = balance_is_non_negative


def positive_value(value: int) -> ViolationDetail | None:
    if value > 0:
        return None
    return ViolationDetail(
        code="value.non_positive",
        message="value must be positive",
        field_path="/value",
        actual=value,
        expected="value > 0",
    )


@contract(
    pre(positive_value),
    invariant(typed_balance_invariant),
)
def example(value: int, wallet: HasBalance) -> int:
    return value + wallet.balance
```

## ガイドライン

- 単純な条件なら `bool` を返してください。
- 調査しやすい payload が必要なら `ViolationDetail | None` を返してください。
- `Any` や `getattr` に逃げるより、`Protocol` で必要な属性だけを表現してください。
