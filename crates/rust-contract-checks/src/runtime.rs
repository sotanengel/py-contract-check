use crate::{
    metadata::ContractKind,
    report::{ContractLocation, ContractViolation, InputSnapshot},
};

/// 任意の参照から型名ベースの入力概要を構築します。
#[must_use]
pub fn input_snapshot<T>(name: &'static str, value: &T) -> InputSnapshot
where
    T: ?Sized,
{
    InputSnapshot::typed(name, std::any::type_name_of_val(value))
}

/// 契約違反オブジェクトを生成します。
#[must_use]
pub fn violation(
    kind: ContractKind,
    function: &'static str,
    condition: &'static str,
    message: Option<&'static str>,
    location: ContractLocation,
    inputs: Vec<InputSnapshot>,
) -> ContractViolation {
    ContractViolation::new(function, kind, condition, message, location, inputs)
}

/// 不変条件違反を明示的に構築します。
#[must_use]
pub fn invariant_violation(
    function: &'static str,
    condition: &'static str,
    message: Option<&'static str>,
    location: ContractLocation,
    inputs: Vec<InputSnapshot>,
) -> ContractViolation {
    violation(
        ContractKind::Invariant,
        function,
        condition,
        message,
        location,
        inputs,
    )
}

/// 契約違反をpanic payloadとして送出します。
pub fn handle_violation(violation: ContractViolation) -> ! {
    std::panic::panic_any(violation);
}
