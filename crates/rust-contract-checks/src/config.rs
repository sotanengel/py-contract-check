const PRIMARY_ENV_VAR: &str = "PYTHON_CONTRACTS_RS";
const LEGACY_ENV_VAR: &str = "RUST_CONTRACT_CHECKS";

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
/// `PYTHON_CONTRACTS_RS=0|false|off` を設定すると、コンパイル時に有効でも停止できます。
/// 旧環境変数 `RUST_CONTRACT_CHECKS` も後方互換のため受け付けます。
#[must_use]
#[inline(always)]
pub fn contracts_enabled() -> bool {
    if !compile_time_contracts_enabled() {
        return false;
    }

    let value = std::env::var(PRIMARY_ENV_VAR)
        .ok()
        .or_else(|| std::env::var(LEGACY_ENV_VAR).ok());

    env_value_enables_contracts(value.as_deref())
}

fn is_disabled_value(value: &str) -> bool {
    value == "0" || value.eq_ignore_ascii_case("false") || value.eq_ignore_ascii_case("off")
}

fn env_value_enables_contracts(value: Option<&str>) -> bool {
    match value {
        Some(value) => !is_disabled_value(value.trim()),
        None => true,
    }
}

#[cfg(test)]
mod tests {
    use super::env_value_enables_contracts;

    #[test]
    fn disabled_env_values_turn_contracts_off() {
        assert!(!env_value_enables_contracts(Some("0")));
        assert!(!env_value_enables_contracts(Some("false")));
        assert!(!env_value_enables_contracts(Some("off")));
        assert!(!env_value_enables_contracts(Some(" false ")));
    }

    #[test]
    fn other_values_keep_contracts_on() {
        assert!(env_value_enables_contracts(None));
        assert!(env_value_enables_contracts(Some("1")));
        assert!(env_value_enables_contracts(Some("true")));
        assert!(env_value_enables_contracts(Some("debug")));
    }
}
