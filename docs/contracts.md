# 契約機能一覧

`rust-contract-checks` は、attribute macro と構造化エラー型を中心に契約を表現します。

## 記法

```rust
#[contract(
    pre(value > 0, "入力は正"),
    post(*ret >= value, "戻り値は入力以上"),
    error(matches!(err, MyError::Rejected), "定義済みエラーのみ"),
    invariant(self.balance >= 0, "残高は非負"),
    pure("外部状態に依存しない"),
    panic_free("契約違反以外ではpanicしない")
)]
```

## `pre(...)`

- 実行前にすべて評価します。
- 1件でも偽なら `ContractViolation` を panic payload として送出します。
- 条件文は `stringify!` 互換の形で保持され、ログ出力へ載ります。

## `post(...)`

- 非 `Result` 関数では常に評価します。
- `Result<T, E>` を返す関数では `Ok(ret)` のときだけ評価します。
- 事後条件式では `ret` を参照できます。

## `error(...)`

- `Result<T, E>` を返す関数にのみ指定できます。
- `Err(err)` のとき、列挙した条件のいずれかを満たせば成功です。
- 1件も一致しなければ `ErrorContract` 違反になります。

## `invariant(...)`

- メソッド前後で評価します。
- 状態保持オブジェクトの整合性確認に向きます。
- 型レベル不変条件ではなく、現段階では実行時不変条件です。

## `pure(...)`

- 現状は意図表明と軽いシグネチャ検査です。
- `&mut self` や `&mut` 引数を受ける関数に付けるとコンパイルエラーにします。
- 将来的な lint / 静的解析連携の拡張点として扱います。

## `panic_free(...)`

- 現状は意図表明用メタデータです。
- panic と `Result` エラーの契約を分けて記述したい場合の土台として残しています。

## 契約違反の扱い

契約違反は [`ContractViolation`](../crates/rust-contract-checks/src/report.rs)
へ集約されます。

保持情報:

- 契約種別
- 関数名
- 条件文字列
- 任意メッセージ
- 発生位置
- 入力値概要

## feature flag

- デフォルト: デバッグビルドで有効
- `always-contracts`: リリースでも有効

## 将来拡張

- async 関数対応
- JSON / SARIF 出力
- `cargo` サブコマンド経由の静的解析
- `panic_free` / `pure` のlint化
