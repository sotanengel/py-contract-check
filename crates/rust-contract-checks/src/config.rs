/// コンパイル時に契約検証コードが有効かどうかを返します。
///
/// デフォルトではデバッグビルドで有効、リリースビルドでは無効です。
/// `always-contracts` feature を有効にするとリリースビルドでも検証します。
#[must_use]
#[inline(always)]
pub const fn compile_time_contracts_enabled() -> bool {
    cfg!(debug_assertions) || cfg!(feature = "always-contracts")
}

/// 実行時に契約検証を有効とみなすかを返します。
///
/// `RUST_CONTRACT_CHECKS=0|false|off` を設定すると、コンパイル時に有効でも停止できます。
#[must_use]
#[inline(always)]
pub fn contracts_enabled() -> bool {
    if !compile_time_contracts_enabled() {
        return false;
    }

    match std::env::var("RUST_CONTRACT_CHECKS") {
        Ok(value) => !is_disabled_value(value.trim()),
        Err(_) => true,
    }
}

fn is_disabled_value(value: &str) -> bool {
    value == "0" || value.eq_ignore_ascii_case("false") || value.eq_ignore_ascii_case("off")
}
