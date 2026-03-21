/// 契約種別です。
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ContractKind {
    /// 関数実行前に満たすべき条件です。
    Precondition,
    /// 関数実行後の戻り値に対する条件です。
    Postcondition,
    /// 状態保持コンポーネントの整合性条件です。
    Invariant,
    /// `Result::Err` 側に対する許可済み失敗条件です。
    ErrorContract,
    /// 純粋性の意図表明です。
    Purity,
    /// panic方針の意図表明です。
    PanicContract,
}

impl ContractKind {
    /// ログや表示に使う固定文字列を返します。
    #[must_use]
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Precondition => "precondition",
            Self::Postcondition => "postcondition",
            Self::Invariant => "invariant",
            Self::ErrorContract => "error",
            Self::Purity => "purity",
            Self::PanicContract => "panic",
        }
    }
}

/// 単一の契約条項です。
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ContractClause {
    /// 条項の種別です。
    pub kind: ContractKind,
    /// 条件文字列です。
    pub condition: &'static str,
    /// 任意の説明文です。
    pub message: Option<&'static str>,
}

impl ContractClause {
    /// 新しい契約条項を生成します。
    #[must_use]
    pub const fn new(
        kind: ContractKind,
        condition: &'static str,
        message: Option<&'static str>,
    ) -> Self {
        Self {
            kind,
            condition,
            message,
        }
    }
}

/// 外部解析やドキュメント生成が参照しやすい契約メタデータです。
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ContractMetadata {
    /// 契約対象の関数またはメソッド名です。
    pub function: &'static str,
    /// 宣言された条項一覧です。
    pub clauses: &'static [ContractClause],
}

impl ContractMetadata {
    /// 関数単位のメタデータを構築します。
    #[must_use]
    pub const fn new(function: &'static str, clauses: &'static [ContractClause]) -> Self {
        Self { function, clauses }
    }
}
