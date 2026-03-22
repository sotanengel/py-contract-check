from __future__ import annotations

import contextlib
import contextvars
import functools
import inspect
import json
import os
import types
from dataclasses import dataclass, replace
from typing import (
    Any,
    Callable,
    Collection,
    Dict,
    Iterator,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
    get_args,
    get_origin,
    get_type_hints,
)

from . import _native
from .models import ViolationCause, ViolationDetail, violation_detail_to_dict

Predicate = Callable[..., Any]
ExceptionMatcher = Callable[..., Any]
ExceptionSpec = Union[Type[Exception], Tuple[Type[Exception], ...]]
ClassType = TypeVar("ClassType", bound=type[Any])
_VIOLATION_DETAIL_ATTRIBUTE = "__contract_violation_detail__"
_METHOD_ROLE_ATTRIBUTE = "__contract_method_role__"
_DEBUG_INVARIANTS_ENV_VAR = "PYTHON_CONTRACTS_RS_DEBUG_INVARIANTS"
_EXPENSIVE_INVARIANTS_ENV_VAR = "PYTHON_CONTRACTS_RS_EXPENSIVE_INVARIANTS"
_READ_ONLY_PREFIXES = ("get_", "list_", "peek_", "fetch_", "is_", "has_")
_ALLOWED_INVARIANT_POLICIES = frozenset(
    {"always", "mutating_only", "read_only_opt_out", "debug_only"}
)
_ALLOWED_INVARIANT_COSTS = frozenset({"cheap", "expensive"})
_VIOLATION_DETAILS_BY_ID: Dict[int, ViolationDetail] = {}


@dataclass(frozen=True)
class _ClauseSpec:
    kind: str
    condition: str
    checker: Optional[Callable[..., Any]]
    native: _native.ContractClause
    predicate_name: str | None = None
    predicate_module: str | None = None
    allow_none_success: bool = False
    policy: str = "always"
    cost: str = "cheap"


@dataclass(frozen=True)
class _PredicateOutcome:
    matched: bool
    detail: ViolationDetail | None = None


@dataclass(frozen=True)
class ContractRuntimeSettings:
    debug_invariants: bool = False
    expensive_invariants: bool = True


_RUNTIME_SETTINGS: contextvars.ContextVar[ContractRuntimeSettings | None] = contextvars.ContextVar(
    "python_contracts_rs_runtime_settings",
    default=None,
)


class ContractViolationError(AssertionError):
    _DETAIL_FIELDS = frozenset(
        {
            "code",
            "message",
            "field_path",
            "actual",
            "expected",
            "subject_id",
            "subject_type",
            "contract_phase",
            "predicate_name",
            "predicate_module",
            "severity",
            "hint",
            "causes",
        }
    )

    def __init__(
        self,
        violation: _native.ContractViolation,
        detail: ViolationDetail | None = None,
    ) -> None:
        self.violation = violation
        self._detail = _resolve_violation_detail(violation, detail)
        _attach_violation_detail(violation, self._detail)
        super().__init__(str(violation))

    @property
    def kind(self) -> str:
        return self.violation.kind

    @property
    def detail(self) -> ViolationDetail:
        return _resolve_violation_detail(self.violation, self._detail)

    def __getattr__(self, name: str) -> Any:
        if name in self._DETAIL_FIELDS:
            return getattr(self.detail, name)
        raise AttributeError(name)

    def to_dict(self) -> Dict[str, Any]:
        return violation_to_dict(self)

    def to_json(self) -> str:
        return violation_to_json(self)


def get_contract_runtime_settings() -> ContractRuntimeSettings:
    current = _RUNTIME_SETTINGS.get()
    if current is not None:
        return current

    return ContractRuntimeSettings(
        debug_invariants=_env_flag(_DEBUG_INVARIANTS_ENV_VAR, default=False),
        expensive_invariants=_env_flag(_EXPENSIVE_INVARIANTS_ENV_VAR, default=True),
    )


@contextlib.contextmanager
def contract_runtime(
    *,
    debug_invariants: bool | None = None,
    expensive_invariants: bool | None = None,
) -> Iterator[None]:
    current = get_contract_runtime_settings()
    token = _RUNTIME_SETTINGS.set(
        ContractRuntimeSettings(
            debug_invariants=current.debug_invariants
            if debug_invariants is None
            else debug_invariants,
            expensive_invariants=current.expensive_invariants
            if expensive_invariants is None
            else expensive_invariants,
        )
    )
    try:
        yield
    finally:
        _RUNTIME_SETTINGS.reset(token)


def mutating(function: Callable[..., Any]) -> Callable[..., Any]:
    setattr(function, _METHOD_ROLE_ATTRIBUTE, "mutating")
    return function


def read_only(function: Callable[..., Any]) -> Callable[..., Any]:
    setattr(function, _METHOD_ROLE_ATTRIBUTE, "read_only")
    return function


def pre(
    predicate: Predicate,
) -> _ClauseSpec:
    condition, checker, predicate_name, predicate_module, allow_none_success = (
        _normalize_boolean_clause(predicate)
    )
    return _clause(
        "precondition",
        condition,
        checker,
        predicate_name=predicate_name,
        predicate_module=predicate_module,
        allow_none_success=allow_none_success,
    )


def post(
    predicate: Predicate,
) -> _ClauseSpec:
    condition, checker, predicate_name, predicate_module, allow_none_success = (
        _normalize_boolean_clause(predicate)
    )
    return _clause(
        "postcondition",
        condition,
        checker,
        predicate_name=predicate_name,
        predicate_module=predicate_module,
        allow_none_success=allow_none_success,
    )


def invariant(
    predicate: Predicate,
    *,
    policy: str = "always",
    cost: str = "cheap",
) -> _ClauseSpec:
    normalized_policy = _normalize_invariant_policy(policy)
    normalized_cost = _normalize_invariant_cost(cost)
    condition, checker, predicate_name, predicate_module, allow_none_success = (
        _normalize_boolean_clause(predicate)
    )
    return _clause(
        "invariant",
        condition,
        checker,
        predicate_name=predicate_name,
        predicate_module=predicate_module,
        allow_none_success=allow_none_success,
        policy=normalized_policy,
        cost=normalized_cost,
    )


def error(
    matcher_or_exceptions: Union[ExceptionMatcher, ExceptionSpec],
) -> _ClauseSpec:
    if _is_exception_spec(matcher_or_exceptions):
        exceptions = _normalize_exceptions(cast(ExceptionSpec, matcher_or_exceptions))
        condition = " or ".join(exception.__name__ for exception in exceptions)
        return _clause(
            "error",
            condition,
            _exception_matcher(exceptions),
            predicate_name=condition,
            predicate_module=None,
        )

    condition, checker, predicate_name, predicate_module, allow_none_success = (
        _normalize_boolean_clause(cast(ExceptionMatcher, matcher_or_exceptions))
    )
    return _clause(
        "error",
        condition,
        checker,
        predicate_name=predicate_name,
        predicate_module=predicate_module,
        allow_none_success=allow_none_success,
    )


def raises(*exceptions: Type[Exception]) -> _ClauseSpec:
    if not exceptions:
        raise TypeError("raises() には少なくとも1つの例外型が必要です")

    normalized = _normalize_exceptions(exceptions)
    condition = " or ".join(exception.__name__ for exception in normalized)
    return _clause(
        "error",
        condition,
        _exception_matcher(normalized),
        predicate_name=condition,
        predicate_module=None,
    )


def pure() -> _ClauseSpec:
    return _clause("purity", "pure", None, predicate_name="pure", predicate_module=None)


def panic_free() -> _ClauseSpec:
    return _clause("panic", "panic_free", None, predicate_name="panic_free", predicate_module=None)


def contract(*clauses: _ClauseSpec) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    normalized = tuple(_require_clause(clause) for clause in clauses)

    def decorator(function: Callable[..., Any]) -> Callable[..., Any]:
        signature = inspect.signature(function)
        function_path = _callable_path(function)
        location = _function_location(function)
        metadata = _native.ContractMetadata(
            function_path,
            [clause.native for clause in normalized],
        )
        preconditions = [clause for clause in normalized if clause.kind == "precondition"]
        postconditions = [clause for clause in normalized if clause.kind == "postcondition"]
        invariants = [clause for clause in normalized if clause.kind == "invariant"]
        error_contracts = [clause for clause in normalized if clause.kind == "error"]
        panic_contract = next(
            (clause for clause in normalized if clause.kind == "panic"),
            None,
        )

        if inspect.isasyncgenfunction(function):

            @functools.wraps(function)
            def async_generator_wrapper(*args: Any, **kwargs: Any) -> Any:
                if not _native.contracts_enabled():
                    return function(*args, **kwargs)

                active_invariants = _active_invariants(function, invariants)
                context, inputs = _prepare_call(signature, args, kwargs)
                _check_entry_contracts(
                    preconditions=preconditions,
                    invariants=active_invariants,
                    function_path=function_path,
                    location=location,
                    inputs=inputs,
                    context=context,
                )
                generator = function(*args, **kwargs)
                return _ContractAsyncGenerator(
                    generator=generator,
                    postconditions=postconditions,
                    invariants=active_invariants,
                    error_contracts=error_contracts,
                    panic_contract=panic_contract,
                    function_path=function_path,
                    location=location,
                    inputs=inputs,
                    context=context,
                )

            setattr(async_generator_wrapper, "__contract_metadata__", metadata)
            return async_generator_wrapper

        if inspect.iscoroutinefunction(function):

            @functools.wraps(function)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                if not _native.contracts_enabled():
                    return await function(*args, **kwargs)

                active_invariants = _active_invariants(function, invariants)
                context, inputs = _prepare_call(signature, args, kwargs)
                _check_entry_contracts(
                    preconditions=preconditions,
                    invariants=active_invariants,
                    function_path=function_path,
                    location=location,
                    inputs=inputs,
                    context=context,
                )

                try:
                    result = await function(*args, **kwargs)
                except ContractViolationError:
                    raise
                except Exception as exc:
                    _handle_invocation_exception(
                        error_contracts=error_contracts,
                        panic_contract=panic_contract,
                        function_path=function_path,
                        location=location,
                        inputs=inputs,
                        context=context,
                        invariants=active_invariants,
                        exc=exc,
                    )

                wrapped_manager = _maybe_wrap_async_context_manager(
                    result=result,
                    postconditions=postconditions,
                    invariants=active_invariants,
                    error_contracts=error_contracts,
                    panic_contract=panic_contract,
                    function_path=function_path,
                    location=location,
                    inputs=inputs,
                    context=context,
                )
                if wrapped_manager is not result:
                    return wrapped_manager

                _check_success_contracts(
                    postconditions=postconditions,
                    invariants=active_invariants,
                    function_path=function_path,
                    location=location,
                    inputs=inputs,
                    context=context,
                    result=result,
                )
                return result

            setattr(async_wrapper, "__contract_metadata__", metadata)
            return async_wrapper

        @functools.wraps(function)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if not _native.contracts_enabled():
                return function(*args, **kwargs)

            active_invariants = _active_invariants(function, invariants)
            context, inputs = _prepare_call(signature, args, kwargs)
            _check_entry_contracts(
                preconditions=preconditions,
                invariants=active_invariants,
                function_path=function_path,
                location=location,
                inputs=inputs,
                context=context,
            )

            try:
                result = function(*args, **kwargs)
            except ContractViolationError:
                raise
            except Exception as exc:
                _handle_invocation_exception(
                    error_contracts=error_contracts,
                    panic_contract=panic_contract,
                    function_path=function_path,
                    location=location,
                    inputs=inputs,
                    context=context,
                    invariants=active_invariants,
                    exc=exc,
                )

            wrapped_manager = _maybe_wrap_async_context_manager(
                result=result,
                postconditions=postconditions,
                invariants=active_invariants,
                error_contracts=error_contracts,
                panic_contract=panic_contract,
                function_path=function_path,
                location=location,
                inputs=inputs,
                context=context,
            )
            if wrapped_manager is not result:
                return wrapped_manager

            _check_success_contracts(
                postconditions=postconditions,
                invariants=active_invariants,
                function_path=function_path,
                location=location,
                inputs=inputs,
                context=context,
                result=result,
            )
            return result

        setattr(wrapper, "__contract_metadata__", metadata)
        return wrapper

    return decorator


def invariant_class(
    *clauses: _ClauseSpec,
    include_private: bool = False,
    include_dunder: bool = False,
    include: Collection[str] | None = None,
    exclude: Collection[str] | None = None,
) -> Callable[[ClassType], ClassType]:
    normalized = tuple(_require_invariant_clause(clause) for clause in clauses)
    included_names = None if include is None else frozenset(include)
    excluded_names = frozenset(exclude or ())

    def decorator(cls: ClassType) -> ClassType:
        for name, attribute in vars(cls).items():
            wrapped = _wrap_class_attribute(
                name=name,
                attribute=attribute,
                invariants=normalized,
                include_private=include_private,
                include_dunder=include_dunder,
                include=included_names,
                exclude=excluded_names,
            )
            if wrapped is not None:
                setattr(cls, name, wrapped)

        return cls

    return decorator


def get_contract_metadata(function: Callable[..., Any]) -> Optional[_native.ContractMetadata]:
    metadata = getattr(function, "__contract_metadata__", None)
    if metadata is not None:
        return cast(_native.ContractMetadata, metadata)

    bound_function = getattr(function, "__func__", None)
    if bound_function is None:
        return None

    return cast(
        Optional[_native.ContractMetadata], getattr(bound_function, "__contract_metadata__", None)
    )


def clause_to_dict(clause: _native.ContractClause) -> Dict[str, Any]:
    return {
        "kind": clause.kind,
        "condition": clause.condition,
    }


def metadata_to_dict(metadata: _native.ContractMetadata) -> Dict[str, Any]:
    return {
        "function": metadata.function,
        "clauses": [clause_to_dict(clause) for clause in metadata.clauses],
    }


def metadata_to_json(metadata: _native.ContractMetadata) -> str:
    return json.dumps(metadata_to_dict(metadata), ensure_ascii=False, sort_keys=True)


def input_snapshot_to_dict(snapshot: _native.InputSnapshot) -> Dict[str, Any]:
    return {
        "name": snapshot.name,
        "type_name": snapshot.type_name,
        "summary": snapshot.summary,
    }


def location_to_dict(location: Optional[_native.ContractLocation]) -> Optional[Dict[str, Any]]:
    if location is None:
        return None

    return {
        "file": location.file,
        "line": location.line,
        "column": location.column,
    }


def violation_to_dict(
    violation: Union[_native.ContractViolation, ContractViolationError],
) -> Dict[str, Any]:
    normalized = _normalize_violation(violation)
    detail = _resolve_violation_detail(
        normalized,
        violation.detail if isinstance(violation, ContractViolationError) else None,
    )
    payload = {
        "function": normalized.function,
        "kind": normalized.kind,
        "condition": normalized.condition,
        "details": normalized.details,
        "location": location_to_dict(normalized.location),
        "inputs": [input_snapshot_to_dict(snapshot) for snapshot in normalized.inputs],
    }
    payload.update(violation_detail_to_dict(detail))
    return payload


def violation_to_json(
    violation: Union[_native.ContractViolation, ContractViolationError],
) -> str:
    return json.dumps(violation_to_dict(violation), ensure_ascii=False, sort_keys=True)


def violation_to_sarif_result(
    violation: Union[_native.ContractViolation, ContractViolationError],
) -> Dict[str, Any]:
    normalized = _normalize_violation(violation)
    detail = _resolve_violation_detail(
        normalized,
        violation.detail if isinstance(violation, ContractViolationError) else None,
    )
    detail_payload = violation_detail_to_dict(detail)
    result: Dict[str, Any] = {
        "ruleId": _sarif_rule_id(normalized),
        "level": _sarif_level(detail.severity),
        "message": {
            "text": detail.message or normalized.details or normalized.condition,
        },
        "properties": {
            "contractKind": normalized.kind,
            "condition": normalized.condition,
            "details": normalized.details,
            "code": detail_payload["code"],
            "fieldPath": detail_payload["field_path"],
            "actual": detail_payload["actual"],
            "expected": detail_payload["expected"],
            "contractPhase": detail_payload["contract_phase"],
            "predicateName": detail_payload["predicate_name"],
            "predicateModule": detail_payload["predicate_module"],
            "subjectId": detail_payload["subject_id"],
            "subjectType": detail_payload["subject_type"],
            "severity": detail_payload["severity"],
            "hint": detail_payload["hint"],
            "causes": detail_payload["causes"],
        },
    }

    if normalized.location is not None:
        result["locations"] = [
            {
                "physicalLocation": {
                    "artifactLocation": {
                        "uri": normalized.location.file,
                    },
                    "region": {
                        "startLine": normalized.location.line,
                        "startColumn": normalized.location.column,
                    },
                }
            }
        ]

    return result


def violations_to_sarif(
    violations: Sequence[Union[_native.ContractViolation, ContractViolationError]],
) -> Dict[str, Any]:
    normalized = [_normalize_violation(violation) for violation in violations]
    rules = [
        {
            "id": _sarif_rule_id(violation),
            "name": violation.kind,
            "shortDescription": {"text": violation.kind},
            "fullDescription": {"text": violation.condition},
        }
        for violation in _unique_violations_by_rule(normalized)
    ]
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "contract-check",
                        "rules": rules,
                    }
                },
                "results": [violation_to_sarif_result(violation) for violation in normalized],
            }
        ],
    }


def violations_to_sarif_json(
    violations: Sequence[Union[_native.ContractViolation, ContractViolationError]],
) -> str:
    return json.dumps(violations_to_sarif(violations), ensure_ascii=False, sort_keys=True)


def _clause(
    kind: str,
    condition: str,
    checker: Optional[Callable[..., Any]],
    *,
    predicate_name: str | None = None,
    predicate_module: str | None = None,
    allow_none_success: bool = False,
    policy: str = "always",
    cost: str = "cheap",
) -> _ClauseSpec:
    native = _native.ContractClause(kind, condition)
    return _ClauseSpec(
        kind=kind,
        condition=condition,
        checker=checker,
        native=native,
        predicate_name=predicate_name,
        predicate_module=predicate_module,
        allow_none_success=allow_none_success,
        policy=policy,
        cost=cost,
    )


def _require_clause(clause: _ClauseSpec) -> _ClauseSpec:
    if not isinstance(clause, _ClauseSpec):
        raise TypeError(
            "contract() には pre()/post()/invariant()/error()/pure()/panic_free() を渡してください"
        )
    return clause


def _require_invariant_clause(clause: _ClauseSpec) -> _ClauseSpec:
    clause = _require_clause(clause)
    if clause.kind != "invariant":
        raise TypeError("invariant_class() には invariant(...) だけを渡してください")
    return clause


def _normalize_boolean_clause(
    predicate: Callable[..., Any],
) -> Tuple[str, Callable[..., Any], str, str | None, bool]:
    if callable(predicate) and not _is_exception_spec(predicate):
        return (
            _callable_label(predicate),
            predicate,
            _callable_label(predicate),
            _callable_module(predicate),
            _predicate_allows_none_success(predicate),
        )

    raise TypeError("callable を渡してください")


def _callable_label(predicate: Callable[..., Any]) -> str:
    name = getattr(predicate, "__name__", predicate.__class__.__name__)
    if name == "<lambda>":
        return "<lambda>"
    return name


def _callable_module(predicate: Callable[..., Any]) -> str | None:
    module = getattr(predicate, "__module__", None)
    return module if isinstance(module, str) else None


def _normalize_invariant_policy(policy: str) -> str:
    if policy not in _ALLOWED_INVARIANT_POLICIES:
        raise ValueError(
            "invariant() の policy は always / mutating_only / read_only_opt_out / debug_only のいずれかです"
        )
    return policy


def _normalize_invariant_cost(cost: str) -> str:
    if cost not in _ALLOWED_INVARIANT_COSTS:
        raise ValueError("invariant() の cost は cheap / expensive のいずれかです")
    return cost


def _function_location(function: Callable[..., Any]) -> _native.ContractLocation:
    try:
        source_file = inspect.getsourcefile(function) or "<unknown>"
        _, line = inspect.getsourcelines(function)
        return _native.ContractLocation(source_file, line, 1)
    except (OSError, TypeError):
        return _native.ContractLocation("<unknown>", 0, 0)


def _callable_path(function: Callable[..., Any]) -> str:
    module = getattr(function, "__module__", "<unknown>")
    qualname = getattr(function, "__qualname__", getattr(function, "__name__", "<callable>"))
    return f"{module}.{qualname}"


class _ContractAsyncGenerator:
    def __init__(
        self,
        generator: Any,
        postconditions: Sequence[_ClauseSpec],
        invariants: Sequence[_ClauseSpec],
        error_contracts: Sequence[_ClauseSpec],
        panic_contract: Optional[_ClauseSpec],
        function_path: str,
        location: _native.ContractLocation,
        inputs: Sequence[_native.InputSnapshot],
        context: Mapping[str, Any],
    ) -> None:
        self._generator = generator
        self._postconditions = postconditions
        self._invariants = invariants
        self._error_contracts = error_contracts
        self._panic_contract = panic_contract
        self._function_path = function_path
        self._location = location
        self._inputs = inputs
        self._context = context
        self._closed = False

    def __aiter__(self) -> "_ContractAsyncGenerator":
        return self

    async def __anext__(self) -> Any:
        return await self._advance(self._generator.__anext__())

    async def asend(self, value: Any) -> Any:
        return await self._advance(self._generator.asend(value))

    async def athrow(self, typ: Any, val: Any = None, tb: Any = None) -> Any:
        if tb is not None:
            return await self._advance(self._generator.athrow(typ, val, tb))
        if val is not None:
            return await self._advance(self._generator.athrow(typ, val))
        return await self._advance(self._generator.athrow(typ))

    async def aclose(self) -> None:
        if self._closed:
            return

        try:
            await self._generator.aclose()
        finally:
            self._closed = True
            _check_boolean_clauses(
                clauses=self._invariants,
                function_path=self._function_path,
                location=self._location,
                inputs=self._inputs,
                available=self._context,
            )

    async def _advance(self, awaitable: Any) -> Any:
        try:
            result = await awaitable
        except StopAsyncIteration:
            self._closed = True
            _check_boolean_clauses(
                clauses=self._invariants,
                function_path=self._function_path,
                location=self._location,
                inputs=self._inputs,
                available=self._context,
            )
            raise
        except ContractViolationError:
            self._closed = True
            raise
        except Exception as exc:
            self._closed = True
            _handle_invocation_exception(
                error_contracts=self._error_contracts,
                panic_contract=self._panic_contract,
                function_path=self._function_path,
                location=self._location,
                inputs=self._inputs,
                context=self._context,
                invariants=self._invariants,
                exc=exc,
            )

        _check_success_contracts(
            postconditions=self._postconditions,
            invariants=self._invariants,
            function_path=self._function_path,
            location=self._location,
            inputs=self._inputs,
            context=self._context,
            result=result,
        )
        return result


class _ContractAsyncContextManager:
    def __init__(
        self,
        manager: Any,
        postconditions: Sequence[_ClauseSpec],
        invariants: Sequence[_ClauseSpec],
        error_contracts: Sequence[_ClauseSpec],
        panic_contract: Optional[_ClauseSpec],
        function_path: str,
        location: _native.ContractLocation,
        inputs: Sequence[_native.InputSnapshot],
        context: Mapping[str, Any],
    ) -> None:
        self._manager = manager
        self._postconditions = postconditions
        self._invariants = invariants
        self._error_contracts = error_contracts
        self._panic_contract = panic_contract
        self._function_path = function_path
        self._location = location
        self._inputs = inputs
        self._context = context

    async def __aenter__(self) -> Any:
        try:
            result = await self._manager.__aenter__()
        except ContractViolationError:
            raise
        except Exception as exc:
            _handle_invocation_exception(
                error_contracts=self._error_contracts,
                panic_contract=self._panic_contract,
                function_path=self._function_path,
                location=self._location,
                inputs=self._inputs,
                context=self._context,
                invariants=self._invariants,
                exc=exc,
            )

        _check_success_contracts(
            postconditions=self._postconditions,
            invariants=self._invariants,
            function_path=self._function_path,
            location=self._location,
            inputs=self._inputs,
            context=self._context,
            result=result,
        )
        return result

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        tb: Any,
    ) -> Any:
        try:
            should_suppress = await self._manager.__aexit__(exc_type, exc, tb)
        except ContractViolationError:
            raise
        except Exception as inner_exc:
            _handle_invocation_exception(
                error_contracts=self._error_contracts,
                panic_contract=self._panic_contract,
                function_path=self._function_path,
                location=self._location,
                inputs=self._inputs,
                context=self._context,
                invariants=self._invariants,
                exc=inner_exc,
            )

        _check_boolean_clauses(
            clauses=self._invariants,
            function_path=self._function_path,
            location=self._location,
            inputs=self._inputs,
            available=self._context,
        )
        return should_suppress


def _prepare_call(
    signature: inspect.Signature,
    args: Sequence[Any],
    kwargs: Mapping[str, Any],
) -> Tuple[Dict[str, Any], Sequence[_native.InputSnapshot]]:
    bound = signature.bind(*args, **kwargs)
    bound.apply_defaults()
    context = dict(bound.arguments)
    return context, _capture_inputs(context)


def _check_entry_contracts(
    preconditions: Sequence[_ClauseSpec],
    invariants: Sequence[_ClauseSpec],
    function_path: str,
    location: _native.ContractLocation,
    inputs: Sequence[_native.InputSnapshot],
    context: Mapping[str, Any],
) -> None:
    _check_boolean_clauses(
        clauses=preconditions,
        function_path=function_path,
        location=location,
        inputs=inputs,
        available=context,
    )
    _check_boolean_clauses(
        clauses=invariants,
        function_path=function_path,
        location=location,
        inputs=inputs,
        available=context,
    )


def _handle_invocation_exception(
    error_contracts: Sequence[_ClauseSpec],
    panic_contract: Optional[_ClauseSpec],
    function_path: str,
    location: _native.ContractLocation,
    inputs: Sequence[_native.InputSnapshot],
    context: Mapping[str, Any],
    invariants: Sequence[_ClauseSpec],
    exc: Exception,
) -> None:
    _check_boolean_clauses(
        clauses=invariants,
        function_path=function_path,
        location=location,
        inputs=inputs,
        available=context,
    )

    matched, detail = _matches_error_contract(
        clauses=error_contracts,
        function_path=function_path,
        location=location,
        inputs=inputs,
        context=context,
        exc=exc,
    )
    if matched:
        raise exc

    if error_contracts:
        raise _build_violation_error(
            function_path=function_path,
            kind="error",
            condition=" or ".join(clause.condition for clause in error_contracts),
            location=location,
            inputs=inputs,
            details=_exception_details(exc),
            detail=detail
            or ViolationDetail(
                code="contract.error.unexpected_exception",
                message="宣言されていない例外が送出されました",
                actual={"type": type(exc).__name__, "message": str(exc)},
                expected=[clause.condition for clause in error_contracts],
                severity="error",
                hint="raises(...) または error(...) の宣言を見直してください",
            ),
        ) from exc

    if panic_contract is not None:
        raise _build_violation_error(
            function_path=function_path,
            kind="panic",
            condition=panic_contract.condition,
            location=location,
            inputs=inputs,
            details=_exception_details(exc),
            detail=ViolationDetail(
                code="contract.panic.unexpected_exception",
                message="想定外例外が panic 契約により契約違反へ変換されました",
                actual={"type": type(exc).__name__, "message": str(exc)},
                severity="error",
            ),
        ) from exc

    raise exc


def _check_success_contracts(
    postconditions: Sequence[_ClauseSpec],
    invariants: Sequence[_ClauseSpec],
    function_path: str,
    location: _native.ContractLocation,
    inputs: Sequence[_native.InputSnapshot],
    context: Mapping[str, Any],
    result: Any,
) -> None:
    _check_boolean_clauses(
        clauses=postconditions,
        function_path=function_path,
        location=location,
        inputs=inputs,
        available=_post_context(context, result),
    )
    _check_boolean_clauses(
        clauses=invariants,
        function_path=function_path,
        location=location,
        inputs=inputs,
        available=context,
    )


def _is_async_context_manager(value: Any) -> bool:
    return callable(getattr(value, "__aenter__", None)) and callable(
        getattr(value, "__aexit__", None)
    )


def _maybe_wrap_async_context_manager(
    result: Any,
    postconditions: Sequence[_ClauseSpec],
    invariants: Sequence[_ClauseSpec],
    error_contracts: Sequence[_ClauseSpec],
    panic_contract: Optional[_ClauseSpec],
    function_path: str,
    location: _native.ContractLocation,
    inputs: Sequence[_native.InputSnapshot],
    context: Mapping[str, Any],
) -> Any:
    if not _is_async_context_manager(result):
        return result

    return _ContractAsyncContextManager(
        manager=result,
        postconditions=postconditions,
        invariants=invariants,
        error_contracts=error_contracts,
        panic_contract=panic_contract,
        function_path=function_path,
        location=location,
        inputs=inputs,
        context=context,
    )


def _wrap_class_attribute(
    name: str,
    attribute: object,
    invariants: Sequence[_ClauseSpec],
    include_private: bool,
    include_dunder: bool,
    include: Collection[str] | None,
    exclude: Collection[str],
) -> Optional[Callable[..., Any]]:
    if isinstance(attribute, (staticmethod, classmethod, property)):
        return None

    if not inspect.isfunction(attribute):
        return None

    if not _should_wrap_method_name(
        name,
        include_private=include_private,
        include_dunder=include_dunder,
        include=include,
        exclude=exclude,
    ):
        return None

    if not _has_instance_receiver(attribute):
        return None

    return _wrap_method_with_invariants(attribute, invariants)


def _should_wrap_method_name(
    name: str,
    include_private: bool,
    include_dunder: bool,
    include: Collection[str] | None,
    exclude: Collection[str],
) -> bool:
    if name in exclude:
        return False

    if name == "__init__":
        return True

    if include is not None and name not in include:
        return False

    if name.startswith("__") and name.endswith("__"):
        return include_dunder

    if name.startswith("_"):
        return include_private

    return True


def _has_instance_receiver(function: Callable[..., Any]) -> bool:
    parameters = tuple(inspect.signature(function).parameters.values())
    if not parameters:
        return False

    first = parameters[0]
    return first.kind in (
        inspect.Parameter.POSITIONAL_ONLY,
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
    )


def _wrap_method_with_invariants(
    function: Callable[..., Any],
    invariants: Sequence[_ClauseSpec],
) -> Callable[..., Any]:
    signature = inspect.signature(function)
    function_path = _callable_path(function)
    location = _function_location(function)
    skip_pre = function.__name__ == "__init__"
    metadata = _merge_metadata(function, invariants, function_path)

    if inspect.isasyncgenfunction(function):

        @functools.wraps(function)
        def async_generator_wrapper(*args: Any, **kwargs: Any) -> Any:
            if not _native.contracts_enabled():
                return function(*args, **kwargs)

            active_invariants = _active_invariants(function, invariants)
            context, inputs = _prepare_call(signature, args, kwargs)

            if not skip_pre:
                _check_boolean_clauses(
                    clauses=active_invariants,
                    function_path=function_path,
                    location=location,
                    inputs=inputs,
                    available=context,
                )

            generator = function(*args, **kwargs)
            return _ContractAsyncGenerator(
                generator=generator,
                postconditions=[],
                invariants=active_invariants,
                error_contracts=[],
                panic_contract=None,
                function_path=function_path,
                location=location,
                inputs=inputs,
                context=context,
            )

        setattr(async_generator_wrapper, "__contract_metadata__", metadata)
        return async_generator_wrapper

    if inspect.iscoroutinefunction(function):

        @functools.wraps(function)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            if not _native.contracts_enabled():
                return await function(*args, **kwargs)

            active_invariants = _active_invariants(function, invariants)
            context, inputs = _prepare_call(signature, args, kwargs)

            if not skip_pre:
                _check_boolean_clauses(
                    clauses=active_invariants,
                    function_path=function_path,
                    location=location,
                    inputs=inputs,
                    available=context,
                )

            try:
                result = await function(*args, **kwargs)
            except ContractViolationError:
                raise
            except Exception:
                if skip_pre:
                    raise

                _check_boolean_clauses(
                    clauses=active_invariants,
                    function_path=function_path,
                    location=location,
                    inputs=inputs,
                    available=context,
                )
                raise

            _check_boolean_clauses(
                clauses=active_invariants,
                function_path=function_path,
                location=location,
                inputs=inputs,
                available=context,
            )
            return _maybe_wrap_async_context_manager(
                result=result,
                postconditions=[],
                invariants=active_invariants,
                error_contracts=[],
                panic_contract=None,
                function_path=function_path,
                location=location,
                inputs=inputs,
                context=context,
            )

        setattr(async_wrapper, "__contract_metadata__", metadata)
        return async_wrapper

    @functools.wraps(function)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        if not _native.contracts_enabled():
            return function(*args, **kwargs)

        active_invariants = _active_invariants(function, invariants)
        context, inputs = _prepare_call(signature, args, kwargs)

        if not skip_pre:
            _check_boolean_clauses(
                clauses=active_invariants,
                function_path=function_path,
                location=location,
                inputs=inputs,
                available=context,
            )

        try:
            result = function(*args, **kwargs)
        except ContractViolationError:
            raise
        except Exception:
            if skip_pre:
                raise

            _check_boolean_clauses(
                clauses=active_invariants,
                function_path=function_path,
                location=location,
                inputs=inputs,
                available=context,
            )
            raise

        _check_boolean_clauses(
            clauses=active_invariants,
            function_path=function_path,
            location=location,
            inputs=inputs,
            available=context,
        )
        return _maybe_wrap_async_context_manager(
            result=result,
            postconditions=[],
            invariants=active_invariants,
            error_contracts=[],
            panic_contract=None,
            function_path=function_path,
            location=location,
            inputs=inputs,
            context=context,
        )

    setattr(wrapper, "__contract_metadata__", metadata)
    return wrapper


def _merge_metadata(
    function: Callable[..., Any],
    clauses: Sequence[_ClauseSpec],
    function_path: str,
) -> _native.ContractMetadata:
    existing = get_contract_metadata(function)
    merged_clauses = [] if existing is None else list(existing.clauses)
    merged_clauses.extend(clause.native for clause in clauses)
    return _native.ContractMetadata(function_path, merged_clauses)


def _capture_inputs(values: Mapping[str, Any]) -> Sequence[_native.InputSnapshot]:
    return [
        _native.InputSnapshot(name, type(value).__name__, _summarize_value(value))
        for name, value in values.items()
    ]


def _summarize_value(value: Any) -> str:
    rendered = repr(value)
    if len(rendered) > 120:
        return f"{rendered[:117]}..."
    return rendered


def _resolve_clause_result(clause: _ClauseSpec, result: Any) -> _PredicateOutcome:
    if isinstance(result, ViolationDetail):
        return _PredicateOutcome(matched=False, detail=result)

    if (
        isinstance(result, tuple)
        and result
        and all(isinstance(item, ViolationCause) for item in result)
    ):
        return _PredicateOutcome(
            matched=False,
            detail=ViolationDetail(causes=cast(Tuple[ViolationCause, ...], result)),
        )

    if (
        isinstance(result, list)
        and result
        and all(isinstance(item, ViolationCause) for item in result)
    ):
        return _PredicateOutcome(matched=False, detail=ViolationDetail(causes=tuple(result)))

    if result is None:
        return _PredicateOutcome(matched=clause.allow_none_success)

    return _PredicateOutcome(matched=bool(result))


def _check_boolean_clauses(
    clauses: Sequence[_ClauseSpec],
    function_path: str,
    location: _native.ContractLocation,
    inputs: Sequence[_native.InputSnapshot],
    available: Mapping[str, Any],
) -> None:
    for clause in clauses:
        assert clause.checker is not None
        try:
            outcome = _resolve_clause_result(clause, _invoke(clause.checker, available))
        except ContractViolationError:
            raise
        except Exception as exc:
            raise _build_violation_error(
                function_path=function_path,
                kind=clause.kind,
                condition=clause.condition,
                location=location,
                inputs=inputs,
                details=f"predicate raised {type(exc).__name__}: {exc}",
                clause=clause,
            ) from exc

        if not outcome.matched:
            raise _build_violation_error(
                function_path=function_path,
                kind=clause.kind,
                condition=clause.condition,
                location=location,
                inputs=inputs,
                clause=clause,
                detail=outcome.detail,
            )


def _matches_error_contract(
    clauses: Sequence[_ClauseSpec],
    function_path: str,
    location: _native.ContractLocation,
    inputs: Sequence[_native.InputSnapshot],
    context: Mapping[str, Any],
    exc: Exception,
) -> Tuple[bool, ViolationDetail | None]:
    if not clauses:
        return False, None

    available = dict(context)
    available["exc"] = exc
    available["error"] = exc
    first_detail: ViolationDetail | None = None

    for clause in clauses:
        assert clause.checker is not None
        try:
            outcome = _resolve_clause_result(clause, _invoke(clause.checker, available))
            if outcome.matched:
                return True, None
            if first_detail is None and outcome.detail is not None:
                first_detail = outcome.detail
        except Exception as inner_exc:
            raise _build_violation_error(
                function_path=function_path,
                kind="error",
                condition=clause.condition,
                location=location,
                inputs=inputs,
                details=f"predicate raised {type(inner_exc).__name__}: {inner_exc}",
                clause=clause,
            ) from inner_exc

    return False, first_detail


def _post_context(context: Mapping[str, Any], result: Any) -> Dict[str, Any]:
    available = dict(context)
    available["ret"] = result
    if "result" not in available:
        available["result"] = result
    return available


def _invoke(function: Callable[..., Any], available: Mapping[str, Any]) -> Any:
    signature = inspect.signature(function)
    positional = []
    keyword = {}
    accepts_kwargs = False

    for parameter in signature.parameters.values():
        if parameter.kind is inspect.Parameter.VAR_POSITIONAL:
            raise TypeError("契約predicateで *args は未サポートです")

        if parameter.kind is inspect.Parameter.VAR_KEYWORD:
            accepts_kwargs = True
            continue

        if parameter.name not in available:
            if parameter.default is inspect.Signature.empty:
                raise TypeError(f"predicate parameter '{parameter.name}' を解決できません")
            continue

        if parameter.kind is inspect.Parameter.POSITIONAL_ONLY:
            positional.append(available[parameter.name])
        else:
            keyword[parameter.name] = available[parameter.name]

    if accepts_kwargs:
        for name, value in available.items():
            if name not in keyword:
                keyword[name] = value

    return function(*positional, **keyword)


def _build_violation_error(
    function_path: str,
    kind: str,
    condition: str,
    location: _native.ContractLocation,
    inputs: Sequence[_native.InputSnapshot],
    details: Optional[str] = None,
    clause: _ClauseSpec | None = None,
    detail: ViolationDetail | None = None,
) -> ContractViolationError:
    normalized_detail = _compose_violation_detail(
        kind=kind,
        condition=condition,
        clause=clause,
        detail=detail,
        details=details,
    )
    violation = _native.ContractViolation(
        function_path,
        kind,
        condition,
        location,
        list(inputs),
        details or normalized_detail.message,
    )
    return ContractViolationError(violation, detail=normalized_detail)


def _normalize_violation(
    violation: Union[_native.ContractViolation, ContractViolationError],
) -> _native.ContractViolation:
    if isinstance(violation, ContractViolationError):
        return violation.violation
    return violation


def _sarif_rule_id(violation: _native.ContractViolation) -> str:
    return f"contract/{violation.kind}"


def _sarif_level(severity: str | None) -> str:
    if severity == "warning":
        return "warning"
    if severity == "info":
        return "note"
    return "error"


def _unique_violations_by_rule(
    violations: Sequence[_native.ContractViolation],
) -> Sequence[_native.ContractViolation]:
    unique: Dict[str, _native.ContractViolation] = {}
    for violation in violations:
        unique.setdefault(_sarif_rule_id(violation), violation)
    return list(unique.values())


def _exception_details(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}"


def _compose_violation_detail(
    *,
    kind: str,
    condition: str,
    clause: _ClauseSpec | None,
    detail: ViolationDetail | None,
    details: str | None,
) -> ViolationDetail:
    base = detail or ViolationDetail()
    phase = base.contract_phase or _contract_phase(kind)
    message = base.message or details or _default_violation_message(phase, condition, clause)
    return replace(
        base,
        code=base.code or _default_violation_code(phase),
        message=message,
        contract_phase=phase,
        predicate_name=base.predicate_name
        or (clause.predicate_name if clause is not None else None),
        predicate_module=base.predicate_module
        or (clause.predicate_module if clause is not None else None),
        severity=base.severity or "error",
    )


def _contract_phase(kind: str) -> str:
    mapping = {
        "precondition": "pre",
        "postcondition": "post",
        "invariant": "invariant",
        "error": "error",
        "panic": "panic",
    }
    return mapping.get(kind, kind)


def _default_violation_code(phase: str) -> str:
    return f"contract.{phase}.failed"


def _default_violation_message(
    phase: str,
    condition: str,
    clause: _ClauseSpec | None,
) -> str:
    phase_label = {
        "pre": "前提条件",
        "post": "事後条件",
        "invariant": "不変条件",
        "error": "例外契約",
        "panic": "panic 契約",
    }.get(phase, "契約")
    predicate_name = clause.predicate_name if clause is not None else condition
    return f"{phase_label} '{predicate_name}' が失敗しました"


def _attach_violation_detail(
    violation: _native.ContractViolation,
    detail: ViolationDetail,
) -> None:
    _VIOLATION_DETAILS_BY_ID[id(violation)] = detail
    try:
        setattr(violation, _VIOLATION_DETAIL_ATTRIBUTE, violation_detail_to_dict(detail))
    except AttributeError:
        return


def _resolve_violation_detail(
    violation: _native.ContractViolation,
    detail: ViolationDetail | None = None,
) -> ViolationDetail:
    if detail is not None:
        return detail

    cached = _VIOLATION_DETAILS_BY_ID.get(id(violation))
    if cached is not None:
        return cached

    payload = getattr(violation, _VIOLATION_DETAIL_ATTRIBUTE, None)
    if isinstance(payload, Mapping):
        return _detail_from_payload(payload)

    return _compose_violation_detail(
        kind=violation.kind,
        condition=violation.condition,
        clause=None,
        detail=ViolationDetail(message=violation.details),
        details=violation.details,
    )


def _detail_from_payload(payload: Mapping[str, Any]) -> ViolationDetail:
    causes_payload = payload.get("causes")
    causes: Tuple[ViolationCause, ...] = ()
    if isinstance(causes_payload, Sequence) and not isinstance(
        causes_payload, (str, bytes, bytearray)
    ):
        normalized_causes = []
        for item in causes_payload:
            if isinstance(item, Mapping):
                normalized_causes.append(
                    ViolationCause(
                        code=_optional_str(item.get("code")),
                        message=_optional_str(item.get("message")),
                        field_path=_optional_str(item.get("field_path")),
                        actual=item.get("actual"),
                        expected=item.get("expected"),
                        subject_id=_optional_str(item.get("subject_id")),
                        subject_type=_optional_str(item.get("subject_type")),
                        severity=_optional_str(item.get("severity")),
                        hint=_optional_str(item.get("hint")),
                    )
                )
        causes = tuple(normalized_causes)

    return ViolationDetail(
        code=_optional_str(payload.get("code")),
        message=_optional_str(payload.get("message")),
        field_path=_optional_str(payload.get("field_path")),
        actual=payload.get("actual"),
        expected=payload.get("expected"),
        subject_id=_optional_str(payload.get("subject_id")),
        subject_type=_optional_str(payload.get("subject_type")),
        contract_phase=_optional_str(payload.get("contract_phase")),
        predicate_name=_optional_str(payload.get("predicate_name")),
        predicate_module=_optional_str(payload.get("predicate_module")),
        severity=_optional_str(payload.get("severity")),
        hint=_optional_str(payload.get("hint")),
        causes=causes,
    )


def _optional_str(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _predicate_allows_none_success(predicate: Callable[..., Any]) -> bool:
    raw_annotation = inspect.signature(predicate).return_annotation
    try:
        return_annotation = get_type_hints(predicate).get("return")
    except Exception:
        return _annotation_allows_none(raw_annotation)

    if return_annotation is None:
        return True

    return _annotation_allows_none(return_annotation)


def _annotation_allows_none(annotation: Any) -> bool:
    if annotation is inspect.Signature.empty:
        return False

    if isinstance(annotation, str):
        normalized = annotation.replace(" ", "")
        return (
            normalized in {"None", "NoneType"}
            or "|None" in normalized
            or "None|" in normalized
            or normalized.startswith("Optional[")
            or normalized.endswith(",None]")
        )

    if annotation is type(None):
        return True

    origin = get_origin(annotation)
    union_type = getattr(types, "UnionType", None)
    if origin is Union or (union_type is not None and origin is union_type):
        return any(_annotation_allows_none(argument) for argument in get_args(annotation))

    return False


def _env_flag(name: str, *, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default

    normalized = value.strip()
    lowered = normalized.lower()
    return normalized != "0" and lowered != "false" and lowered != "off"


def _active_invariants(
    function: Callable[..., Any],
    invariants: Sequence[_ClauseSpec],
) -> Sequence[_ClauseSpec]:
    settings = get_contract_runtime_settings()
    role = _method_role(function)
    return [
        clause
        for clause in invariants
        if _invariant_should_run(clause, role=role, settings=settings)
    ]


def _method_role(function: Callable[..., Any]) -> str:
    explicit = getattr(function, _METHOD_ROLE_ATTRIBUTE, None)
    if explicit in {"mutating", "read_only"}:
        return cast(str, explicit)

    name = getattr(function, "__name__", "")
    if name == "__init__":
        return "mutating"

    if name.startswith(_READ_ONLY_PREFIXES):
        return "read_only"

    if name.startswith(
        (
            "set_",
            "add_",
            "update_",
            "remove_",
            "delete_",
            "create_",
            "write_",
            "save_",
            "debit",
            "credit",
            "spend",
        )
    ):
        return "mutating"

    return "unspecified"


def _invariant_should_run(
    clause: _ClauseSpec,
    *,
    role: str,
    settings: ContractRuntimeSettings,
) -> bool:
    if clause.cost == "expensive" and not settings.expensive_invariants:
        return False

    if clause.policy == "always":
        return True

    if clause.policy == "mutating_only":
        return role == "mutating"

    if clause.policy == "read_only_opt_out":
        return role != "read_only"

    if clause.policy == "debug_only":
        return settings.debug_invariants

    return True


def _is_exception_spec(value: object) -> bool:
    if inspect.isclass(value) and issubclass(value, Exception):
        return True

    if isinstance(value, tuple) and value:
        return all(inspect.isclass(item) and issubclass(item, Exception) for item in value)

    return False


def _normalize_exceptions(
    value: Union[ExceptionSpec, Tuple[Type[Exception], ...]],
) -> Tuple[Type[Exception], ...]:
    if inspect.isclass(value) and issubclass(value, Exception):
        return (value,)

    if (
        isinstance(value, tuple)
        and value
        and all(inspect.isclass(item) and issubclass(item, Exception) for item in value)
    ):
        return value

    raise TypeError("例外型または例外型のtupleを渡してください")


def _exception_matcher(exceptions: Tuple[Type[Exception], ...]) -> ExceptionMatcher:
    return lambda exc, **_: isinstance(exc, exceptions)
