# contract-check

[![Sponsor](https://img.shields.io/badge/Sponsor-GitHub-ea4aaa?logo=githubsponsors&logoColor=white)](https://github.com/sponsors/sotanengel)

This is a design-by-contract library for Python, implemented in Rust.

`contract-check` は、Python 向けの契約プログラミングライブラリです。公開 API は
Python の decorator 中心で設計し、内部の構造化違反情報と実行時基盤を Rust で実装します。
思想面では [`life4/deal`](https://github.com/life4/deal) を参考にしつつ、配布、監査性、
AI 補助開発、Python/Rust 混成運用を前提に再設計しています。

## クイックスタート

```bash
pip install contract-check
```

```python
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
    invariant("self.balance >= 0", lambda self: self.balance >= 0, "残高は非負"),
)
class Wallet:
    def __init__(self, balance: int) -> None:
        self.balance = balance

    def debit(self, amount: int) -> None:
        self.balance -= amount


assert divide(12, 3) == 4
assert asyncio.run(async_increment(2)) == 3
```

配布名と import 名:

- PyPI distribution 名は `contract-check` です
- Python import 名は現時点では `python_contracts_rs` です

標準挙動:

- 契約は sync / async 関数の両方で有効です
- `PYTHON_CONTRACTS_RS=0` で実行時に無効化できます
- 契約違反は `ContractViolationError` として送出され、`to_dict()` / `to_json()` で構造化出力できます

## 提供機能

| 機能 | Python API | 補足 |
| --- | --- | --- |
| 前提条件 | `pre(...)` | sync / async / async generator の実行前に検証 |
| 事後条件 | `post(...)` | 戻り値は `result` / `ret` で参照 |
| 不変条件 | `invariant(...)` / `@invariant_class(...)` | method 単位または class 全体へ注入 |
| 期待例外 | `raises(...)` / `error(...)` | 許可された例外のみ通過 |
| 純粋性 | `pure(...)` | 現段階では意図表明 |
| panic 方針 | `panic_free(...)` | 予期しない例外を契約違反へ変換 |
| 契約メタデータ | `get_contract_metadata(...)` | ドキュメント生成やテスト補助向け |
| 構造化出力 | `violation_to_dict(...)` / `violation_to_json(...)` | CI や監査ログ向け |
| SARIF 出力 | `violation_to_sarif_result(...)` / `violations_to_sarif(...)` | GitHub code scanning 連携向け |

詳細は [docs/contracts.md](docs/contracts.md) を参照してください。

## リポジトリ構成

- `python/python_contracts_rs/`
  Python 公開 API と decorator 実装です。
- `bindings/python-contracts-rs/`
  PyO3 ベースの Python/Rust バインディングです。
- `crates/rust-contract-checks/`
  Rust 側の低レベルな契約種別・違反情報・設定判定です。
- `examples/quickstart.py`
  Python 利用者向けの最短例です。
- `tests/python/test_contracts.py`
  Python 公開 API の統合テストです。
- `tests/contracts.rs`
  Rust コアの回帰テストです。

## 生成 AI 向け案内

このプロジェクトは **Python library implemented in Rust** です。Rust 単独ライブラリとして
読まないでください。読む順序は次を推奨します。

1. この `README.md`
2. [docs/contracts.md](docs/contracts.md)
3. [examples/quickstart.py](examples/quickstart.py)
4. [tests/python/test_contracts.py](tests/python/test_contracts.py)
5. [ARCHITECTURE.md](ARCHITECTURE.md)
6. [AGENTS.md](AGENTS.md)

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

Dev Container は [`.devcontainer/devcontainer.json`](.devcontainer/devcontainer.json) を参照してください。

## 現状の制限

- `@invariant_class(...)` は public instance method と `__init__` を対象にします
- private / dunder / staticmethod / classmethod への自動適用は明示設定または将来拡張の対象です
- `pure(...)` は意図表明です
- tracing backend は未実装です

## ライセンス

MIT License。詳細は [LICENSE](LICENSE) を参照してください。
