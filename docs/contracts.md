# 契約機能一覧

`contract-check` は Python decorator と Rust 製の構造化違反データを組み合わせて契約を表現します。
sync / async 関数、async generator、async context manager を同じ記法で扱えます。

配布名は `contract-check`、Python import 名は `python_contracts_rs` です。

## 基本記法

```python
from python_contracts_rs import contract, error, invariant, panic_free, post, pre, raises


def positive_value(value: int) -> bool:
    return value > 0


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
```

## `pre(...)`

- 関数実行前にすべて評価します。
- 偽になった時点で `ContractViolationError` を送出します。
- `pre(...)` は predicate callable だけを受け取ります。

## `post(...)`

- 正常終了時だけ評価します。
- 戻り値は `result` または `ret` で参照できます。
- 入力との関係を表現したいときに使います。
- async generator では yield ごとの値に対して評価します。
- async context manager では `__aenter__()` が返した値に対して評価します。

## `invariant(...)`

- 関数またはメソッドの前後で評価します。
- 例外送出時でも、ラッパーを抜ける前に再評価します。

## `@invariant_class(...)`

- class 全体に invariant を注入する decorator です。
- デフォルトでは public instance method と `__init__` をラップします。
- `include_private=True` を指定すると `_private` な method にも適用できます。
- `staticmethod` / `classmethod` / `property` / dunder method は既定では対象外です。

## `raises(...)` / `error(...)`

- `raises(ValueError)` は例外型による許可宣言です。
- `error(is_value_error)` のように predicate callable で細かく書くこともできます。
- 宣言した例外に一致しない場合は `kind="error"` の契約違反になります。

## `pure(...)`

- 現段階では意図表明です。
- Python API では lint や静的解析連携のためのメタデータとして残します。

## `panic_free(...)`

- 宣言済み例外に一致しない予期しない例外を `kind="panic"` の契約違反へ変換します。
- Python での「panic」は、ここでは想定外例外のラップを意味します。

## 契約違反の扱い

`ContractViolationError` は `_native.ContractViolation` を保持します。参照できる主な情報:

- `kind`
- `function`
- `condition`
  callable 名または例外型名のような導出ラベルです。
- `details`
- `location`
- `inputs`

`ContractViolation.to_log_line()` は監査ログや CI ログに流しやすい単一行フォーマットを返します。

構造化出力:

- `violation_to_dict(...)` / `violation_to_json(...)`
- `metadata_to_dict(...)` / `metadata_to_json(...)`
- `ContractViolationError.to_dict()` / `ContractViolationError.to_json()`

SARIF 出力:

- `violation_to_sarif_result(...)`
- `violations_to_sarif(...)`
- `violations_to_sarif_json(...)`

## 実行時設定

- `PYTHON_CONTRACTS_RS=0|false|off` で契約チェックを停止できます
- 旧環境変数 `RUST_CONTRACT_CHECKS` も後方互換として解釈します

## 将来拡張

- tracing backend
- `pure(...)` / `panic_free(...)` の lint 化
