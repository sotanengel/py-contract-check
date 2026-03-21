import asyncio

from python_contracts_rs import (
    ContractViolationError,
    contract,
    invariant,
    invariant_class,
    post,
    pre,
    pure,
    raises,
)


@contract(
    pre("divisor != 0", lambda divisor: divisor != 0, "0で割る入力は許可しない"),
    post(
        "result * divisor == dividend",
        lambda result, dividend, divisor: result * divisor == dividend,
        "戻り値から元の被除数を復元できる",
    ),
    raises(ZeroDivisionError, message="0除算だけを許可する"),
    pure("入力以外の状態に依存しない"),
)
def divide(dividend: int, divisor: int) -> int:
    if divisor == 0:
        raise ZeroDivisionError("division by zero")
    return dividend // divisor


@contract(
    pre("value > 0", lambda value: value > 0, "正の値だけを許可する"),
    post("result == value + 1", lambda result, value: result == value + 1, "結果は入力+1"),
)
async def async_increment(value: int) -> int:
    await asyncio.sleep(0)
    return value + 1


@invariant_class(
    invariant("self.remaining >= 0", lambda self: self.remaining >= 0, "残高は常に0以上"),
)
class Budget:
    def __init__(self, remaining: int) -> None:
        self.remaining = remaining

    @contract(
        raises(ValueError, message="定義済みの支出エラーだけを許可する"),
    )
    def spend(self, amount: int) -> None:
        if amount < 0:
            raise ValueError("amount must be non-negative")
        if amount > self.remaining:
            raise ValueError("overdraft")
        self.remaining -= amount


def main() -> None:
    assert divide(12, 3) == 4
    assert asyncio.run(async_increment(2)) == 3

    budget = Budget(10)
    budget.spend(3)
    assert budget.remaining == 7

    try:
        asyncio.run(async_increment(0))
    except ContractViolationError as exc:
        print(exc.to_json())


if __name__ == "__main__":
    main()
