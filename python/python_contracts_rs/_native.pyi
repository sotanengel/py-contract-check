from typing import Optional, Sequence

CONTRACT_ENV_VAR: str

class ContractLocation:
    file: str
    line: int
    column: int
    def __init__(self, file: str, line: int, column: int) -> None: ...

class InputSnapshot:
    name: str
    type_name: str
    summary: Optional[str]
    def __init__(self, name: str, type_name: str, summary: Optional[str] = ...) -> None: ...

class ContractClause:
    kind: str
    condition: str
    def __init__(self, kind: str, condition: str) -> None: ...

class ContractMetadata:
    function: str
    clauses: list[ContractClause]
    def __init__(self, function: str, clauses: Sequence[ContractClause]) -> None: ...

class ContractViolation:
    function: str
    kind: str
    condition: str
    details: Optional[str]
    location: Optional[ContractLocation]
    inputs: list[InputSnapshot]
    def __init__(
        self,
        function: str,
        kind: str,
        condition: str,
        location: Optional[ContractLocation] = ...,
        inputs: Optional[Sequence[InputSnapshot]] = ...,
        details: Optional[str] = ...,
    ) -> None: ...
    def to_log_line(self) -> str: ...

def contracts_enabled() -> bool: ...
