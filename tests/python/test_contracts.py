import asyncio
from contextlib import asynccontextmanager
from typing import Any

import pytest

from python_contracts_rs import (
    ContractViolationError,
    contract,
    get_contract_metadata,
    invariant,
    invariant_class,
    metadata_to_dict,
    metadata_to_json,
    panic_free,
    post,
    pre,
    pure,
    raises,
    violation_to_dict,
    violation_to_json,
    violation_to_sarif_result,
    violations_to_sarif,
    violations_to_sarif_json,
)


def is_even(value: int) -> bool:
    return value % 2 == 0


def result_exceeds_value(result: int, value: int) -> bool:
    return result > value


def positive_value(value: int) -> bool:
    return value > 0


def incremented_value(result: int, value: int) -> bool:
    return result == value + 1


def non_negative_start(start: int) -> bool:
    return start >= 0


def result_not_below_start(result: int, start: int) -> bool:
    return result >= start


def context_has_prefix(result: str) -> bool:
    return result.startswith("ctx:")


def context_ends_with_ok(result: str) -> bool:
    return result.endswith("ok")


def balance_is_non_negative(self: Any) -> bool:
    return self.balance >= 0


def amount_is_non_negative(amount: int) -> bool:
    return amount >= 0


@contract(
    pre(is_even),
    pure(),
)
def only_even(value: int) -> int:
    return value // 2


@contract(
    post(result_exceeds_value),
)
def broken_increment(value: int) -> int:
    return value


@contract(
    raises(ZeroDivisionError),
)
def checked_divide(dividend: int, divisor: int) -> int:
    if divisor == 0:
        raise ZeroDivisionError("division by zero")
    return dividend // divisor


@contract(
    raises(ZeroDivisionError),
)
def broken_error(flag: bool) -> int:
    if flag:
        raise ValueError("unexpected value")
    return 1


@contract(
    panic_free(),
)
def panic_if_requested(flag: bool) -> int:
    if flag:
        raise RuntimeError("boom")
    return 1


@contract(
    pre(positive_value),
    post(incremented_value),
)
async def async_increment(value: int) -> int:
    await asyncio.sleep(0)
    return value + 1


@contract(
    raises(ValueError),
)
async def async_broken_error(flag: bool) -> int:
    await asyncio.sleep(0)
    if flag:
        raise RuntimeError("unexpected async error")
    return 1


@contract(
    pre(non_negative_start),
    post(result_not_below_start),
)
async def async_counter(start: int) -> Any:
    for offset in range(2):
        await asyncio.sleep(0)
        yield start + offset


@contract(
    raises(ValueError),
)
async def async_counter_with_error(flag: bool) -> Any:
    await asyncio.sleep(0)
    if flag:
        raise RuntimeError("unexpected generator error")
    yield 1


@contract(
    post(context_has_prefix),
)
@asynccontextmanager
async def managed_resource(name: str) -> Any:
    await asyncio.sleep(0)
    yield f"ctx:{name}"


@contract(
    post(context_has_prefix),
)
@asynccontextmanager
async def broken_managed_resource() -> Any:
    await asyncio.sleep(0)
    yield "broken"


@asynccontextmanager
@contract(
    post(context_ends_with_ok),
)
async def managed_resource_contract_inside() -> Any:
    await asyncio.sleep(0)
    yield "ctx:ok"


class Wallet:
    def __init__(self, balance: int) -> None:
        self.balance = balance

    @contract(
        invariant(balance_is_non_negative),
    )
    def debit(self, amount: int) -> None:
        self.balance -= amount


@invariant_class(
    invariant(balance_is_non_negative),
)
class AutoWallet:
    def __init__(self, balance: int) -> None:
        self.balance = balance

    @contract(pre(amount_is_non_negative))
    def debit(self, amount: int) -> None:
        self.balance -= amount

    def _set_negative(self) -> None:
        self.balance = -1


@invariant_class(
    invariant(balance_is_non_negative),
    include_private=True,
)
class StrictWallet:
    def __init__(self, balance: int) -> None:
        self.balance = balance

    def _set_negative(self) -> None:
        self.balance = -1


@invariant_class(
    invariant(balance_is_non_negative),
)
class AsyncWallet:
    def __init__(self, balance: int) -> None:
        self.balance = balance

    async def debit(self, amount: int) -> None:
        await asyncio.sleep(0)
        self.balance -= amount


def test_precondition_violation_contains_context() -> None:
    with pytest.raises(ContractViolationError) as exc_info:
        only_even(3)

    violation = exc_info.value.violation
    assert violation.kind == "precondition"
    assert violation.condition == "is_even"
    assert violation.inputs[0].name == "value"
    assert violation.inputs[0].summary == "3"


def test_postcondition_violation_is_reported() -> None:
    with pytest.raises(ContractViolationError) as exc_info:
        broken_increment(5)

    violation = exc_info.value.violation
    assert violation.kind == "postcondition"
    assert violation.condition == "result_exceeds_value"


def test_declared_exception_passes_through() -> None:
    with pytest.raises(ZeroDivisionError):
        checked_divide(8, 0)


def test_unexpected_exception_is_reported_as_error_contract() -> None:
    with pytest.raises(ContractViolationError) as exc_info:
        broken_error(True)

    violation = exc_info.value.violation
    assert violation.kind == "error"
    assert violation.condition == "ZeroDivisionError"
    assert violation.details == "ValueError: unexpected value"


def test_panic_free_wraps_unexpected_exception() -> None:
    with pytest.raises(ContractViolationError) as exc_info:
        panic_if_requested(True)

    violation = exc_info.value.violation
    assert violation.kind == "panic"
    assert violation.condition == "panic_free"
    assert violation.details == "RuntimeError: boom"


def test_async_contract_checks_pre_and_post_conditions() -> None:
    assert asyncio.run(async_increment(2)) == 3

    with pytest.raises(ContractViolationError) as exc_info:
        asyncio.run(async_increment(0))

    assert exc_info.value.violation.kind == "precondition"


def test_async_unexpected_exception_is_reported_as_error_contract() -> None:
    with pytest.raises(ContractViolationError) as exc_info:
        asyncio.run(async_broken_error(True))

    violation = exc_info.value.violation
    assert violation.kind == "error"
    assert violation.details == "RuntimeError: unexpected async error"


def test_async_generator_checks_yielded_values() -> None:
    async def collect() -> list[int]:
        values = []
        async for value in async_counter(1):
            values.append(value)
        return values

    assert asyncio.run(collect()) == [1, 2]

    with pytest.raises(ContractViolationError) as exc_info:
        async_counter(-1)

    assert exc_info.value.violation.kind == "precondition"


def test_async_generator_reports_iteration_errors() -> None:
    async def collect() -> None:
        async for _ in async_counter_with_error(True):
            pass

    with pytest.raises(ContractViolationError) as exc_info:
        asyncio.run(collect())

    assert exc_info.value.violation.details == "RuntimeError: unexpected generator error"


def test_async_context_manager_supports_both_decorator_orders() -> None:
    async def use_manager() -> tuple[str, str]:
        async with managed_resource("demo") as first:
            async with managed_resource_contract_inside() as second:
                return first, second

    assert asyncio.run(use_manager()) == ("ctx:demo", "ctx:ok")


def test_async_context_manager_reports_enter_value_violation() -> None:
    async def use_manager() -> None:
        async with broken_managed_resource():
            pass

    with pytest.raises(ContractViolationError) as exc_info:
        asyncio.run(use_manager())

    assert exc_info.value.violation.kind == "postcondition"


def test_invariant_is_checked_after_state_change() -> None:
    wallet = Wallet(1)

    with pytest.raises(ContractViolationError) as exc_info:
        wallet.debit(2)

    violation = exc_info.value.violation
    assert violation.kind == "invariant"
    assert violation.condition == "balance_is_non_negative"


def test_metadata_is_available_from_wrapped_function() -> None:
    metadata = get_contract_metadata(only_even)

    assert metadata is not None
    assert metadata.function.endswith("only_even")
    assert [clause.kind for clause in metadata.clauses] == ["precondition", "purity"]


def test_environment_flag_disables_runtime_checks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PYTHON_CONTRACTS_RS", "0")
    assert only_even(3) == 1


def test_violation_serializers_return_json_safe_payload() -> None:
    with pytest.raises(ContractViolationError) as exc_info:
        only_even(3)

    payload = exc_info.value.to_dict()
    assert payload["kind"] == "precondition"
    assert payload["inputs"][0]["name"] == "value"
    assert payload["message"] == "前提条件 'is_even' が失敗しました"
    assert payload["code"] == "contract.pre.failed"
    assert payload["contract_phase"] == "pre"
    assert '"kind": "precondition"' in exc_info.value.to_json()
    assert violation_to_dict(exc_info.value.violation)["condition"] == "is_even"
    assert violation_to_dict(exc_info.value.violation)["code"] == "contract.pre.failed"
    assert violation_to_json(exc_info.value.violation).startswith("{")


def test_metadata_serializers_return_clause_payloads() -> None:
    metadata = get_contract_metadata(only_even)
    assert metadata is not None

    payload = metadata_to_dict(metadata)
    assert payload["function"].endswith("only_even")
    assert payload["clauses"][0]["kind"] == "precondition"
    assert '"clauses"' in metadata_to_json(metadata)


def test_sarif_helpers_return_valid_document_shape() -> None:
    with pytest.raises(ContractViolationError) as exc_info:
        only_even(3)

    result = violation_to_sarif_result(exc_info.value)
    assert result["ruleId"] == "contract/precondition"
    assert result["locations"][0]["physicalLocation"]["region"]["startColumn"] == 1

    document = violations_to_sarif([exc_info.value])
    assert document["version"] == "2.1.0"
    assert document["runs"][0]["results"][0]["ruleId"] == "contract/precondition"
    assert '"version": "2.1.0"' in violations_to_sarif_json([exc_info.value])


def test_invariant_class_checks_constructor_and_public_methods() -> None:
    with pytest.raises(ContractViolationError) as exc_info:
        AutoWallet(-1)

    assert exc_info.value.violation.kind == "invariant"

    wallet = AutoWallet(2)
    with pytest.raises(ContractViolationError) as debit_info:
        wallet.debit(3)

    assert debit_info.value.violation.condition == "balance_is_non_negative"


def test_invariant_class_merges_metadata_and_supports_bound_methods() -> None:
    metadata = get_contract_metadata(AutoWallet.debit)
    bound_metadata = get_contract_metadata(AutoWallet(4).debit)

    assert metadata is not None
    assert bound_metadata is not None
    assert [clause.kind for clause in metadata.clauses] == ["precondition", "invariant"]
    assert [clause.kind for clause in bound_metadata.clauses] == ["precondition", "invariant"]


def test_invariant_class_skips_private_methods_by_default() -> None:
    wallet = AutoWallet(3)
    wallet._set_negative()
    assert wallet.balance == -1


def test_invariant_class_can_wrap_private_methods_when_enabled() -> None:
    wallet = StrictWallet(3)

    with pytest.raises(ContractViolationError) as exc_info:
        wallet._set_negative()

    assert exc_info.value.violation.kind == "invariant"


def test_invariant_class_wraps_async_methods() -> None:
    wallet = AsyncWallet(1)

    with pytest.raises(ContractViolationError) as exc_info:
        asyncio.run(wallet.debit(2))

    assert exc_info.value.violation.kind == "invariant"
