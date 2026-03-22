from __future__ import annotations

import inspect
from typing import Any, Callable, List

from . import _native
from .contracts import (
    ContractViolationError,
    _ClauseSpec,
    _build_violation_error,
    _callable_path,
    _function_location,
    _invoke,
    _normalize_boolean_clause,
    _prepare_call,
    _resolve_clause_result,
)

__all__ = [
    "assert_valid",
    "collect_violations",
    "validate_payload",
]


def collect_violations(
    target: _ClauseSpec | Callable[..., Any],
    /,
    *args: Any,
    kind: str = "precondition",
    function_name: str | None = None,
    **kwargs: Any,
) -> List[ContractViolationError]:
    clause = _normalize_testing_target(target, kind)
    checker = clause.checker
    if checker is None:
        raise TypeError("testing API では評価可能な clause または predicate を渡してください")

    location = _function_location(checker)
    call_name = function_name or _callable_path(checker)
    available, inputs = _prepare_call(inspect.signature(checker), args, kwargs)

    try:
        outcome = _resolve_clause_result(clause, _invoke(checker, available))
    except ContractViolationError as exc:
        return [exc]
    except Exception as exc:
        return [
            _build_violation_error(
                function_path=call_name,
                kind=clause.kind,
                condition=clause.condition,
                location=location,
                inputs=inputs,
                details=f"predicate raised {type(exc).__name__}: {exc}",
                clause=clause,
            )
        ]

    if outcome.matched:
        return []

    return [
        _build_violation_error(
            function_path=call_name,
            kind=clause.kind,
            condition=clause.condition,
            location=location,
            inputs=inputs,
            clause=clause,
            detail=outcome.detail,
        )
    ]


def assert_valid(
    target: _ClauseSpec | Callable[..., Any],
    /,
    *args: Any,
    kind: str = "precondition",
    function_name: str | None = None,
    **kwargs: Any,
) -> None:
    violations = collect_violations(
        target,
        *args,
        kind=kind,
        function_name=function_name,
        **kwargs,
    )
    if violations:
        raise violations[0]


def validate_payload(
    predicate: _ClauseSpec | Callable[..., Any],
    payload: Any,
    /,
    *,
    argument_name: str = "payload",
    kind: str = "precondition",
    function_name: str | None = None,
) -> List[ContractViolationError]:
    return collect_violations(
        predicate,
        kind=kind,
        function_name=function_name,
        **{argument_name: payload},
    )


def _normalize_testing_target(
    target: _ClauseSpec | Callable[..., Any],
    kind: str,
) -> _ClauseSpec:
    if isinstance(target, _ClauseSpec):
        return target

    condition, checker, predicate_name, predicate_module, allow_none_success = (
        _normalize_boolean_clause(target)
    )
    return _ClauseSpec(
        kind=kind,
        condition=condition,
        checker=checker,
        native=_native.ContractClause(kind, condition),
        predicate_name=predicate_name,
        predicate_module=predicate_module,
        allow_none_success=allow_none_success,
    )
