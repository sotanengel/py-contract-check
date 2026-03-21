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

/// `panic_free` 契約つき関数内で捕捉したpanicを契約違反へ変換します。
pub fn handle_panic(
    function: &'static str,
    message: Option<&'static str>,
    location: ContractLocation,
    inputs: Vec<InputSnapshot>,
    payload: Box<dyn std::any::Any + Send>,
) -> ! {
    match payload.downcast::<ContractViolation>() {
        Ok(violation) => handle_violation(*violation),
        Err(payload) => {
            let violation = ContractViolation::new(
                function,
                ContractKind::PanicContract,
                "panic_free",
                message,
                location,
                inputs,
            )
            .with_details(render_panic_payload(payload.as_ref()));
            handle_violation(violation);
        }
    }
}

fn render_panic_payload(payload: &(dyn std::any::Any + Send)) -> String {
    if let Some(message) = payload.downcast_ref::<String>() {
        return message.clone();
    }

    if let Some(message) = payload.downcast_ref::<&'static str>() {
        return (*message).to_owned();
    }

    String::from("非文字列panic payload")
}

/// 契約違反をpanic payloadとして送出します。
pub fn handle_violation(violation: ContractViolation) -> ! {
    std::panic::panic_any(violation);
}
