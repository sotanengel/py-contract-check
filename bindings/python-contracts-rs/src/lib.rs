#![allow(missing_docs)]

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::PyModule;

const LEGACY_ENV_VAR: &str = "RUST_CONTRACT_CHECKS";
const PYTHON_ENV_VAR: &str = "PYTHON_CONTRACTS_RS";

fn normalize_kind(kind: &str) -> PyResult<String> {
    match kind {
        "precondition" | "postcondition" | "invariant" | "error" | "purity" | "panic" => {
            Ok(kind.to_owned())
        }
        _ => Err(PyValueError::new_err(format!(
            "unsupported contract kind: {kind}"
        ))),
    }
}

fn render_location(location: &Option<ContractLocation>) -> String {
    match location {
        Some(location) => location.to_string(),
        None => String::from("-"),
    }
}

fn render_inputs(inputs: &[InputSnapshot]) -> String {
    if inputs.is_empty() {
        return String::from("-");
    }

    inputs
        .iter()
        .map(InputSnapshot::render)
        .collect::<Vec<_>>()
        .join(", ")
}

#[pyclass(module = "python_contracts_rs._native", frozen)]
#[derive(Clone)]
pub struct ContractLocation {
    #[pyo3(get)]
    pub file: String,
    #[pyo3(get)]
    pub line: u32,
    #[pyo3(get)]
    pub column: u32,
}

impl std::fmt::Display for ContractLocation {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}:{}:{}", self.file, self.line, self.column)
    }
}

#[pymethods]
impl ContractLocation {
    #[new]
    fn new(file: String, line: u32, column: u32) -> Self {
        Self { file, line, column }
    }

    fn __str__(&self) -> String {
        self.to_string()
    }

    fn __repr__(&self) -> String {
        format!(
            "ContractLocation(file={:?}, line={}, column={})",
            self.file, self.line, self.column
        )
    }
}

#[pyclass(module = "python_contracts_rs._native", frozen)]
#[derive(Clone)]
pub struct InputSnapshot {
    #[pyo3(get)]
    pub name: String,
    #[pyo3(get)]
    pub type_name: String,
    #[pyo3(get)]
    pub summary: Option<String>,
}

impl InputSnapshot {
    fn render(&self) -> String {
        match &self.summary {
            Some(summary) => format!("{}: {} ({summary})", self.name, self.type_name),
            None => format!("{}: {}", self.name, self.type_name),
        }
    }
}

#[pymethods]
impl InputSnapshot {
    #[new]
    #[pyo3(signature = (name, type_name, summary=None))]
    fn new(name: String, type_name: String, summary: Option<String>) -> Self {
        Self {
            name,
            type_name,
            summary,
        }
    }

    fn __str__(&self) -> String {
        self.render()
    }

    fn __repr__(&self) -> String {
        format!(
            "InputSnapshot(name={:?}, type_name={:?}, summary={:?})",
            self.name, self.type_name, self.summary
        )
    }
}

#[pyclass(module = "python_contracts_rs._native", frozen)]
#[derive(Clone)]
pub struct ContractClause {
    kind: String,
    condition: String,
    message: Option<String>,
}

#[pymethods]
impl ContractClause {
    #[new]
    #[pyo3(signature = (kind, condition, message=None))]
    fn new(kind: String, condition: String, message: Option<String>) -> PyResult<Self> {
        Ok(Self {
            kind: normalize_kind(&kind)?,
            condition,
            message,
        })
    }

    #[getter]
    fn kind(&self) -> String {
        self.kind.clone()
    }

    #[getter]
    fn condition(&self) -> String {
        self.condition.clone()
    }

    #[getter]
    fn message(&self) -> Option<String> {
        self.message.clone()
    }

    fn __repr__(&self) -> String {
        format!(
            "ContractClause(kind={:?}, condition={:?}, message={:?})",
            self.kind, self.condition, self.message
        )
    }
}

#[pyclass(module = "python_contracts_rs._native", frozen)]
#[derive(Clone)]
pub struct ContractMetadata {
    function: String,
    clauses: Vec<ContractClause>,
}

#[pymethods]
impl ContractMetadata {
    #[new]
    fn new(py: Python<'_>, function: String, clauses: Vec<Py<ContractClause>>) -> PyResult<Self> {
        let clauses = clauses
            .into_iter()
            .map(|clause| clause.borrow(py).clone())
            .collect();

        Ok(Self { function, clauses })
    }

    #[getter]
    fn function(&self) -> String {
        self.function.clone()
    }

    #[getter]
    fn clauses(&self, py: Python<'_>) -> PyResult<Vec<Py<ContractClause>>> {
        self.clauses
            .iter()
            .cloned()
            .map(|clause| Py::new(py, clause))
            .collect()
    }

    fn __repr__(&self) -> String {
        format!(
            "ContractMetadata(function={:?}, clauses={})",
            self.function,
            self.clauses.len()
        )
    }
}

#[pyclass(module = "python_contracts_rs._native", frozen)]
#[derive(Clone)]
pub struct ContractViolation {
    function: String,
    kind: String,
    condition: String,
    message: Option<String>,
    details: Option<String>,
    location: Option<ContractLocation>,
    inputs: Vec<InputSnapshot>,
}

impl ContractViolation {
    fn log_line(&self) -> String {
        let message = self.message.as_deref().unwrap_or("-");
        let details = self.details.as_deref().unwrap_or("-");

        format!(
            "contract_violation|kind={}|function={}|condition={}|message={}|details={}|location={}|inputs={}",
            self.kind,
            self.function,
            self.condition,
            message,
            details,
            render_location(&self.location),
            render_inputs(&self.inputs)
        )
    }

    fn render(&self) -> String {
        let mut lines = vec![format!("契約違反 [{}] {}", self.kind, self.function)];
        lines.push(format!("条件: {}", self.condition));

        if let Some(message) = &self.message {
            lines.push(format!("説明: {message}"));
        }

        if let Some(details) = &self.details {
            lines.push(format!("詳細: {details}"));
        }

        if let Some(location) = &self.location {
            lines.push(format!("位置: {location}"));
        }

        if !self.inputs.is_empty() {
            lines.push(format!("入力: {}", render_inputs(&self.inputs)));
        }

        lines.push(format!("ログ: {}", self.log_line()));
        lines.join("\n")
    }
}

#[pymethods]
impl ContractViolation {
    #[new]
    #[pyo3(signature = (function, kind, condition, message=None, location=None, inputs=None, details=None))]
    #[allow(clippy::too_many_arguments)]
    fn new(
        py: Python<'_>,
        function: String,
        kind: String,
        condition: String,
        message: Option<String>,
        location: Option<Py<ContractLocation>>,
        inputs: Option<Vec<Py<InputSnapshot>>>,
        details: Option<String>,
    ) -> PyResult<Self> {
        let location = location.map(|location| location.borrow(py).clone());
        let inputs = inputs
            .unwrap_or_default()
            .into_iter()
            .map(|input| input.borrow(py).clone())
            .collect();

        Ok(Self {
            function,
            kind: normalize_kind(&kind)?,
            condition,
            message,
            details,
            location,
            inputs,
        })
    }

    #[getter]
    fn function(&self) -> String {
        self.function.clone()
    }

    #[getter]
    fn kind(&self) -> String {
        self.kind.clone()
    }

    #[getter]
    fn condition(&self) -> String {
        self.condition.clone()
    }

    #[getter]
    fn message(&self) -> Option<String> {
        self.message.clone()
    }

    #[getter]
    fn details(&self) -> Option<String> {
        self.details.clone()
    }

    #[getter]
    fn location(&self, py: Python<'_>) -> PyResult<Option<Py<ContractLocation>>> {
        self.location
            .clone()
            .map(|location| Py::new(py, location))
            .transpose()
    }

    #[getter]
    fn inputs(&self, py: Python<'_>) -> PyResult<Vec<Py<InputSnapshot>>> {
        self.inputs
            .iter()
            .cloned()
            .map(|input| Py::new(py, input))
            .collect()
    }

    fn to_log_line(&self) -> PyResult<String> {
        Ok(self.log_line())
    }

    fn __str__(&self) -> String {
        self.render()
    }

    fn __repr__(&self) -> String {
        format!(
            "ContractViolation(function={:?}, kind={:?}, condition={:?})",
            self.function, self.kind, self.condition
        )
    }
}

#[pyfunction]
fn contracts_enabled() -> bool {
    let value = std::env::var(PYTHON_ENV_VAR)
        .ok()
        .or_else(|| std::env::var(LEGACY_ENV_VAR).ok());

    env_value_enables_contracts(value)
}

#[pymodule]
fn _native(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_class::<ContractLocation>()?;
    module.add_class::<InputSnapshot>()?;
    module.add_class::<ContractClause>()?;
    module.add_class::<ContractMetadata>()?;
    module.add_class::<ContractViolation>()?;
    module.add_function(wrap_pyfunction!(contracts_enabled, module)?)?;
    module.add("CONTRACT_ENV_VAR", PYTHON_ENV_VAR)?;
    Ok(())
}
fn env_value_enables_contracts(value: Option<String>) -> bool {
    match value {
        Some(value) => {
            let normalized = value.trim();
            normalized != "0"
                && !normalized.eq_ignore_ascii_case("false")
                && !normalized.eq_ignore_ascii_case("off")
        }
        None => true,
    }
}
