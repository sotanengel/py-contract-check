use std::fmt::{Display, Formatter};

use crate::metadata::ContractKind;

/// 契約違反の発生位置です。
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ContractLocation {
    /// ファイル名です。
    pub file: &'static str,
    /// 行番号です。
    pub line: u32,
    /// 列番号です。
    pub column: u32,
}

impl ContractLocation {
    /// 位置情報を生成します。
    #[must_use]
    pub const fn new(file: &'static str, line: u32, column: u32) -> Self {
        Self { file, line, column }
    }
}

impl Display for ContractLocation {
    fn fmt(&self, f: &mut Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}:{}:{}", self.file, self.line, self.column)
    }
}

/// 入力値の概要です。
///
/// デフォルトでは型名のみを保持し、必要なら `summary` に手動説明を追加できます。
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct InputSnapshot {
    /// 引数名です。
    pub name: &'static str,
    /// Rust型名です。
    pub type_name: &'static str,
    /// 任意の補足説明です。
    pub summary: Option<String>,
}

impl InputSnapshot {
    /// 型情報のみを持つ入力概要を生成します。
    #[must_use]
    pub fn typed(name: &'static str, type_name: &'static str) -> Self {
        Self {
            name,
            type_name,
            summary: None,
        }
    }

    /// 補足説明付きの入力概要を生成します。
    #[must_use]
    pub fn described(
        name: &'static str,
        type_name: &'static str,
        summary: impl Into<String>,
    ) -> Self {
        Self {
            name,
            type_name,
            summary: Some(summary.into()),
        }
    }
}

impl Display for InputSnapshot {
    fn fmt(&self, f: &mut Formatter<'_>) -> std::fmt::Result {
        match &self.summary {
            Some(summary) => write!(f, "{}: {} ({summary})", self.name, self.type_name),
            None => write!(f, "{}: {}", self.name, self.type_name),
        }
    }
}

/// 機械処理しやすい契約違反情報です。
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ContractViolation {
    /// 違反した関数またはメソッド名です。
    pub function: &'static str,
    /// 違反種別です。
    pub kind: ContractKind,
    /// 違反した条件文字列です。
    pub condition: &'static str,
    /// 任意の補足メッセージです。
    pub message: Option<&'static str>,
    /// 実行時にしか得られない補足情報です。
    pub details: Option<String>,
    /// 発生位置です。
    pub location: ContractLocation,
    /// 入力値の要約です。
    pub inputs: Vec<InputSnapshot>,
}

impl ContractViolation {
    /// 契約違反オブジェクトを生成します。
    #[must_use]
    pub fn new(
        function: &'static str,
        kind: ContractKind,
        condition: &'static str,
        message: Option<&'static str>,
        location: ContractLocation,
        inputs: Vec<InputSnapshot>,
    ) -> Self {
        Self {
            function,
            kind,
            condition,
            message,
            details: None,
            location,
            inputs,
        }
    }

    /// 実行時の詳細情報を追加します。
    #[must_use]
    pub fn with_details(mut self, details: impl Into<String>) -> Self {
        self.details = Some(details.into());
        self
    }

    /// 監査やCIログに流しやすい単一行フォーマットを返します。
    #[must_use]
    pub fn to_log_line(&self) -> String {
        let message = self.message.unwrap_or("-");
        let details = self.details.as_deref().unwrap_or("-");
        let inputs = if self.inputs.is_empty() {
            String::from("-")
        } else {
            self.inputs
                .iter()
                .map(ToString::to_string)
                .collect::<Vec<_>>()
                .join(", ")
        };

        format!(
            "contract_violation|kind={}|function={}|condition={}|message={}|details={}|location={}|inputs={}",
            self.kind.as_str(),
            self.function,
            self.condition,
            message,
            details,
            self.location,
            inputs
        )
    }
}

impl Display for ContractViolation {
    fn fmt(&self, f: &mut Formatter<'_>) -> std::fmt::Result {
        writeln!(f, "契約違反 [{}] {}", self.kind.as_str(), self.function)?;
        writeln!(f, "条件: {}", self.condition)?;

        if let Some(message) = self.message {
            writeln!(f, "説明: {message}")?;
        }

        if let Some(details) = &self.details {
            writeln!(f, "詳細: {details}")?;
        }

        writeln!(f, "位置: {}", self.location)?;

        if !self.inputs.is_empty() {
            let rendered = self
                .inputs
                .iter()
                .map(ToString::to_string)
                .collect::<Vec<_>>()
                .join(", ");
            writeln!(f, "入力: {rendered}")?;
        }

        write!(f, "ログ: {}", self.to_log_line())
    }
}

impl std::error::Error for ContractViolation {}
