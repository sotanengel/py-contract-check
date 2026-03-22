from __future__ import annotations

from dataclasses import dataclass

import pytest

import contract_check
from contract_check import (
    ContractViolationError,
    ViolationDetail,
    contract,
    contract_runtime,
    invariant,
)
from contract_check import invariant_class, pre, read_only
from contract_check.testing import assert_valid, collect_violations, validate_payload


@dataclass
class Catalog:
    catalog_id: str
    assets: set[str]
    links: list[str]


def refs_are_resolved(catalog: Catalog) -> ViolationDetail | None:
    missing = sorted(link for link in catalog.links if link not in catalog.assets)
    if not missing:
        return None

    return ViolationDetail(
        code="refs.missing",
        message="catalog contains unresolved asset references",
        field_path="/links",
        actual={"missing_asset_ids": missing},
        expected="all link values must exist in catalog.assets",
        subject_id=catalog.catalog_id,
        subject_type="catalog",
        hint="assets を先に登録してください",
    )


def positive_value(value: int) -> bool:
    return value > 0


@contract_check.contract(contract_check.pre(positive_value))
def alias_increment(value: int) -> int:
    return value + 1


def test_contract_check_import_alias_is_supported() -> None:
    assert alias_increment(1) == 2

    with pytest.raises(ContractViolationError):
        alias_increment(0)


def test_testing_api_collects_rich_violation_detail() -> None:
    invalid_catalog = Catalog(catalog_id="cat-1", assets={"asset-1"}, links=["asset-2"])

    violations = collect_violations(refs_are_resolved, catalog=invalid_catalog)

    assert len(violations) == 1
    violation = violations[0]
    assert violation.code == "refs.missing"
    assert violation.field_path == "/links"
    assert violation.actual == {"missing_asset_ids": ["asset-2"]}
    assert violation.subject_id == "cat-1"

    payload = violation.to_dict()
    assert payload["predicate_name"] == "refs_are_resolved"
    assert payload["subject_type"] == "catalog"
    assert payload["hint"] == "assets を先に登録してください"


def test_testing_api_supports_assert_valid_and_validate_payload() -> None:
    valid_catalog = Catalog(catalog_id="cat-2", assets={"asset-1"}, links=["asset-1"])
    invalid_catalog = Catalog(catalog_id="cat-3", assets={"asset-1"}, links=["asset-9"])

    assert_valid(refs_are_resolved, catalog=valid_catalog)

    violations = validate_payload(refs_are_resolved, invalid_catalog, argument_name="catalog")
    assert len(violations) == 1
    assert violations[0].code == "refs.missing"


def test_mutating_only_invariant_skips_read_methods() -> None:
    calls = {"count": 0}

    def audited_balance(self: "Ledger") -> bool:
        calls["count"] += 1
        return True

    @invariant_class(
        invariant(audited_balance, policy="mutating_only"),
    )
    class Ledger:
        def __init__(self, balance: int) -> None:
            self.balance = balance

        def get_balance(self) -> int:
            return self.balance

        def debit(self, amount: int) -> None:
            self.balance -= amount

    ledger = Ledger(10)
    calls["count"] = 0

    assert ledger.get_balance() == 10
    assert calls["count"] == 0

    ledger.debit(1)
    assert calls["count"] == 2


def test_read_only_marker_can_opt_out_invariant_checks() -> None:
    calls = {"count": 0}

    def audited_balance(self: "Ledger") -> bool:
        calls["count"] += 1
        return True

    @invariant_class(
        invariant(audited_balance, policy="read_only_opt_out"),
    )
    class Ledger:
        def __init__(self, balance: int) -> None:
            self.balance = balance

        @read_only
        def refresh(self) -> int:
            return self.balance

        def debit(self, amount: int) -> None:
            self.balance -= amount

    ledger = Ledger(10)
    calls["count"] = 0

    assert ledger.refresh() == 10
    assert calls["count"] == 0

    ledger.debit(1)
    assert calls["count"] == 2


def test_debug_and_expensive_invariants_are_runtime_switchable() -> None:
    calls = {"count": 0}

    def audited_balance(self: "Ledger") -> bool:
        calls["count"] += 1
        return True

    @invariant_class(
        invariant(audited_balance, policy="debug_only", cost="expensive"),
    )
    class Ledger:
        def __init__(self, balance: int) -> None:
            self.balance = balance

        def debit(self, amount: int) -> None:
            self.balance -= amount

    ledger = Ledger(10)
    calls["count"] = 0

    ledger.debit(1)
    assert calls["count"] == 0

    with contract_runtime(debug_invariants=True, expensive_invariants=False):
        ledger.debit(1)
    assert calls["count"] == 0

    with contract_runtime(debug_invariants=True, expensive_invariants=True):
        ledger.debit(1)
    assert calls["count"] == 2


def test_precondition_can_return_rich_detail_through_alias_package() -> None:
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
    def checked_increment(value: int) -> int:
        return value + 1

    with pytest.raises(ContractViolationError) as exc_info:
        checked_increment(0)

    assert exc_info.value.code == "value.non_positive"
    assert exc_info.value.field_path == "/value"
    assert exc_info.value.to_dict()["expected"] == "value > 0"
