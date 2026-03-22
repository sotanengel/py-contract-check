# 契約機能一覧

`contract-check` は Python decorator と Rust 製の構造化違反データを組み合わせて契約を表現します。
sync / async 関数、async generator、async context manager を同じ記法で扱えます。

配布名は `contract-check`、公式 import 名は `contract_check` です。既存の
`python_contracts_rs` も後方互換 alias として利用できます。

## 基本記法

```python
from __future__ import annotations

from contract_check import (
    ViolationDetail,
    contract,
    error,
    invariant,
    invariant_class,
    panic_free,
    post,
    pre,
    read_only,
)


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


def result_not_below_input(result: int, value: int) -> bool:
    return result >= value


def balance_is_non_negative(self) -> bool:
    return self.balance >= 0


def is_value_error(exc: Exception) -> bool:
    return isinstance(exc, ValueError)


@contract(
    pre(positive_value),
    post(result_not_below_input),
    error(is_value_error),
    invariant(balance_is_non_negative),
    panic_free(),
)
def example(value: int) -> int:
    return value


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
```

## `pre(...)`

- 関数実行前にすべて評価します。
- 偽になった時点で `ContractViolationError` を送出します。
- predicate は `bool` だけでなく `ViolationDetail | None` を返せます。

## `post(...)`

- 正常終了時だけ評価します。
- 戻り値は `result` または `ret` で参照できます。
- async generator では yield ごとの値、async context manager では `__aenter__()` の戻り値を検証します。

## `invariant(...)`

- 関数またはメソッドの前後で評価します。
- `policy=` に `always` / `mutating_only` / `read_only_opt_out` / `debug_only` を指定できます。
- `cost=` に `cheap` / `expensive` を指定できます。

## `@invariant_class(...)`

- class 全体に invariant を注入する decorator です。
- デフォルトでは public instance method と `__init__` をラップします。
- `include_private=True`、`include_dunder=True`、`include=...`、`exclude=...` で適用対象を制御できます。
- `@read_only` と `@mutating` を使うと、invariant policy の判定を明示できます。

## `raises(...)` / `error(...)`

- `raises(ValueError)` は例外型による許可宣言です。
- `error(is_value_error)` のように predicate callable で細かく書くこともできます。
- 宣言した例外に一致しない場合は `kind="error"` の契約違反になります。

## rich violation

`ContractViolationError` は `_native.ContractViolation` を保持しつつ、次の詳細 payload を
`to_dict()` / `to_json()` / SARIF へ反映します。

- `code`
- `message`
- `field_path`
- `actual`
- `expected`
- `subject_id`
- `subject_type`
- `contract_phase`
- `predicate_name`
- `predicate_module`
- `severity`
- `hint`
- `causes`

## typed predicates

- `PrePredicate`
- `PostPredicate`
- `InvariantPredicate`
- `ErrorPredicate`
- `ValidationResult`

代表例は [docs/typed-predicates.md](https://github.com/sotanengel/py-contract-check/blob/main/docs/typed-predicates.md) を参照してください。

## testing API

- `collect_violations(...)`
- `assert_valid(...)`
- `validate_payload(...)`

decorator を通さず predicate を直接検証できます。詳細は
[docs/testing.md](https://github.com/sotanengel/py-contract-check/blob/main/docs/testing.md) を参照してください。

## 実行時設定

- `PYTHON_CONTRACTS_RS=0|false|off` で契約チェックを停止できます。
- 旧環境変数 `RUST_CONTRACT_CHECKS` も後方互換として解釈します。
- `contract_runtime(debug_invariants=..., expensive_invariants=...)` で invariant policy を文脈単位に切り替えられます。

## 関連ガイド

- [typed predicates](https://github.com/sotanengel/py-contract-check/blob/main/docs/typed-predicates.md)
- [invariant policies](https://github.com/sotanengel/py-contract-check/blob/main/docs/invariant-policies.md)
- [testing](https://github.com/sotanengel/py-contract-check/blob/main/docs/testing.md)
