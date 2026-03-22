from __future__ import annotations

from typing import Protocol

from contract_check import (
    ContractViolationError,
    InvariantPredicate,
    ViolationDetail,
    contract,
    invariant,
    invariant_class,
    pre,
    read_only,
)


class HasBalance(Protocol):
    balance: int


def balance_is_non_negative(self: HasBalance) -> bool:
    return self.balance >= 0


typed_balance_invariant: InvariantPredicate[HasBalance] = balance_is_non_negative


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


@contract(pre(value_is_positive))
def increment(value: int) -> int:
    return value + 1


@invariant_class(
    invariant(typed_balance_invariant, policy="mutating_only"),
)
class Wallet:
    def __init__(self, balance: int) -> None:
        self.balance = balance

    def debit(self, amount: int) -> None:
        self.balance -= amount

    @read_only
    def current_balance(self) -> int:
        return self.balance


def main() -> None:
    assert increment(1) == 2

    wallet = Wallet(10)
    wallet.debit(3)
    assert wallet.current_balance() == 7

    try:
        increment(0)
    except ContractViolationError as exc:
        print(exc.to_json())


if __name__ == "__main__":
    main()
