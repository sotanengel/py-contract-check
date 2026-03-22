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


def remaining_is_non_negative(self: "Budget") -> bool:
    return self.remaining >= 0


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
    invariant(remaining_is_non_negative, policy="mutating_only"),
)
class Budget:
    def __init__(self, remaining: int) -> None:
        self.remaining = remaining

    @contract(
        raises(ValueError),
    )
    def spend(self, amount: int) -> None:
        if amount < 0:
            raise ValueError("amount must be non-negative")
        if amount > self.remaining:
            raise ValueError("overdraft")
        self.remaining -= amount

    @read_only
    def remaining_balance(self) -> int:
        return self.remaining


def main() -> None:
    assert divide(12, 3) == 4
    assert asyncio.run(async_increment(2)) == 3

    budget = Budget(10)
    budget.spend(3)
    assert budget.remaining_balance() == 7

    try:
        asyncio.run(async_increment(0))
    except ContractViolationError as exc:
        print(exc.to_json())


if __name__ == "__main__":
    main()
