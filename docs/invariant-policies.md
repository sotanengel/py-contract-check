# Invariant Policies

invariant は常に重いとは限りません。`contract-check` では policy と cost を分けて、
安全性とコストのバランスを選べます。

## policy

- `always`: 常に評価します。
- `mutating_only`: mutating と判定されたメソッドだけで評価します。
- `read_only_opt_out`: `@read_only` が付いたメソッドでは評価しません。
- `debug_only`: `contract_runtime(debug_invariants=True)` のときだけ評価します。

判定は `@mutating` / `@read_only` を最優先し、未指定時は `get_...` / `list_...` /
`debit...` / `save_...` のような代表的メソッド名を軽く推定に使います。

## cost

- `cheap`: 常に候補です。
- `expensive`: `contract_runtime(expensive_invariants=False)` で停止できます。

## 例

```python
from contract_check import contract_runtime, invariant, invariant_class, read_only


def balance_is_non_negative(self) -> bool:
    return self.balance >= 0


def snapshot_matches_store(self) -> bool:
    return self.snapshot == self.store.read(self.id)


@invariant_class(
    invariant(balance_is_non_negative, policy="mutating_only", cost="cheap"),
    invariant(snapshot_matches_store, policy="debug_only", cost="expensive"),
    exclude={"list_history"},
)
class Wallet:
    def __init__(self, balance: int, snapshot, store, wallet_id: str) -> None:
        self.balance = balance
        self.snapshot = snapshot
        self.store = store
        self.id = wallet_id

    def debit(self, amount: int) -> None:
        self.balance -= amount

    @read_only
    def get_balance(self) -> int:
        return self.balance


with contract_runtime(debug_invariants=True, expensive_invariants=True):
    wallet = Wallet(10, snapshot={}, store=store, wallet_id="w1")
    wallet.debit(1)
```
