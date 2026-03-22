from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Sequence, Tuple


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value

    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}

    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
        return [_json_safe(item) for item in value]

    try:
        json.dumps(value, ensure_ascii=False, sort_keys=True)
    except TypeError:
        return repr(value)

    return value


@dataclass(frozen=True)
class ViolationCause:
    code: str | None = None
    message: str | None = None
    field_path: str | None = None
    actual: Any = None
    expected: Any = None
    subject_id: str | None = None
    subject_type: str | None = None
    severity: str | None = None
    hint: str | None = None

    def to_dict(self) -> Dict[str, Any]:
        return violation_cause_to_dict(self)


@dataclass(frozen=True)
class ViolationDetail:
    code: str | None = None
    message: str | None = None
    field_path: str | None = None
    actual: Any = None
    expected: Any = None
    subject_id: str | None = None
    subject_type: str | None = None
    contract_phase: str | None = None
    predicate_name: str | None = None
    predicate_module: str | None = None
    severity: str | None = None
    hint: str | None = None
    causes: Tuple[ViolationCause, ...] = field(default_factory=tuple)

    def to_dict(self) -> Dict[str, Any]:
        return violation_detail_to_dict(self)


def violation_cause_to_dict(cause: ViolationCause) -> Dict[str, Any]:
    return {
        "code": cause.code,
        "message": cause.message,
        "field_path": cause.field_path,
        "actual": _json_safe(cause.actual),
        "expected": _json_safe(cause.expected),
        "subject_id": cause.subject_id,
        "subject_type": cause.subject_type,
        "severity": cause.severity,
        "hint": cause.hint,
    }


def violation_detail_to_dict(detail: ViolationDetail) -> Dict[str, Any]:
    return {
        "code": detail.code,
        "message": detail.message,
        "field_path": detail.field_path,
        "actual": _json_safe(detail.actual),
        "expected": _json_safe(detail.expected),
        "subject_id": detail.subject_id,
        "subject_type": detail.subject_type,
        "contract_phase": detail.contract_phase,
        "predicate_name": detail.predicate_name,
        "predicate_module": detail.predicate_module,
        "severity": detail.severity,
        "hint": detail.hint,
        "causes": [violation_cause_to_dict(cause) for cause in detail.causes],
    }
