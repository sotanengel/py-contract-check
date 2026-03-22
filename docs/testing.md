# Testing Guide

契約ロジックをテストするときに、毎回 decorator を通す必要はありません。
`contract-check.testing` では predicate を直接評価できます。

## API

- `collect_violations(...)`: 契約違反をリストで返します。
- `assert_valid(...)`: 違反があれば `ContractViolationError` を送出します。
- `validate_payload(...)`: 単一 payload を特定引数名で評価します。

## 例

```python
from __future__ import annotations

from dataclasses import dataclass

from contract_check import ViolationDetail
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
    )


valid = Catalog(catalog_id="cat-1", assets={"asset-1"}, links=["asset-1"])
invalid = Catalog(catalog_id="cat-2", assets={"asset-1"}, links=["asset-9"])

assert_valid(refs_are_resolved, catalog=valid)

violations = collect_violations(refs_are_resolved, catalog=invalid)
assert violations[0].code == "refs.missing"

payload_violations = validate_payload(refs_are_resolved, invalid, argument_name="catalog")
assert payload_violations[0].field_path == "/links"
```
