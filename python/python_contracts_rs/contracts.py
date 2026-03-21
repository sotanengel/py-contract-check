from __future__ import annotations

import functools
import inspect
import json
from dataclasses import dataclass
from typing import (
    Any,
    Callable,
    Dict,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
)

from . import _native

Predicate = Callable[..., bool]
ExceptionMatcher = Callable[..., bool]
ExceptionSpec = Union[Type[Exception], Tuple[Type[Exception], ...]]
ClassType = TypeVar("ClassType", bound=type[Any])


@dataclass(frozen=True)
class _ClauseSpec:
    kind: str
    condition: str
    message: Optional[str]
    checker: Optional[Callable[..., bool]]
    native: _native.ContractClause


class ContractViolationError(AssertionError):
    def __init__(self, violation: _native.ContractViolation) -> None:
        self.violation = violation
        super().__init__(str(violation))

    @property
    def kind(self) -> str:
        return self.violation.kind

    def to_dict(self) -> Dict[str, Any]:
        return violation_to_dict(self.violation)

    def to_json(self) -> str:
        return violation_to_json(self.violation)


def pre(
    condition_or_predicate: Union[str, Predicate],
    predicate: Optional[Predicate] = None,
    message: Optional[str] = None,
) -> _ClauseSpec:
    condition, checker = _normalize_boolean_clause(condition_or_predicate, predicate)
    return _clause("precondition", condition, message, checker)


def post(
    condition_or_predicate: Union[str, Predicate],
    predicate: Optional[Predicate] = None,
    message: Optional[str] = None,
) -> _ClauseSpec:
    condition, checker = _normalize_boolean_clause(condition_or_predicate, predicate)
    return _clause("postcondition", condition, message, checker)


def invariant(
    condition_or_predicate: Union[str, Predicate],
    predicate: Optional[Predicate] = None,
    message: Optional[str] = None,
) -> _ClauseSpec:
    condition, checker = _normalize_boolean_clause(condition_or_predicate, predicate)
    return _clause("invariant", condition, message, checker)


def error(
    condition_or_matcher: Union[str, ExceptionMatcher, ExceptionSpec],
    matcher: Optional[Union[ExceptionMatcher, ExceptionSpec]] = None,
    message: Optional[str] = None,
) -> _ClauseSpec:
    if matcher is None and _is_exception_spec(condition_or_matcher):
        exceptions = _normalize_exceptions(cast(ExceptionSpec, condition_or_matcher))
        condition = " or ".join(exception.__name__ for exception in exceptions)
        return _clause("error", condition, message, _exception_matcher(exceptions))

    if matcher is not None and _is_exception_spec(matcher):
        exceptions = _normalize_exceptions(cast(ExceptionSpec, matcher))
        return _clause(
            "error",
            str(condition_or_matcher),
            message,
            _exception_matcher(exceptions),
        )

    callable_matcher = matcher if callable(matcher) and not _is_exception_spec(matcher) else None
    condition, checker = _normalize_boolean_clause(
        condition_or_matcher,
        cast(Optional[Callable[..., bool]], callable_matcher),
    )
    return _clause("error", condition, message, checker)


def raises(*exceptions: Type[Exception], message: Optional[str] = None) -> _ClauseSpec:
    if not exceptions:
        raise TypeError("raises() には少なくとも1つの例外型が必要です")

    normalized = _normalize_exceptions(exceptions)
    condition = " or ".join(exception.__name__ for exception in normalized)
    return _clause("error", condition, message, _exception_matcher(normalized))


def pure(message: Optional[str] = None) -> _ClauseSpec:
    return _clause("purity", "pure", message, None)


def panic_free(message: Optional[str] = None) -> _ClauseSpec:
    return _clause("panic", "panic_free", message, None)


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

                context, inputs = _prepare_call(signature, args, kwargs)
                _check_entry_contracts(
                    preconditions=preconditions,
                    invariants=invariants,
                    function_path=function_path,
                    location=location,
                    inputs=inputs,
                    context=context,
                )
                generator = function(*args, **kwargs)
                return _ContractAsyncGenerator(
                    generator=generator,
                    postconditions=postconditions,
                    invariants=invariants,
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

                context, inputs = _prepare_call(signature, args, kwargs)
                _check_entry_contracts(
                    preconditions=preconditions,
                    invariants=invariants,
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
                        invariants=invariants,
                        exc=exc,
                    )

                wrapped_manager = _maybe_wrap_async_context_manager(
                    result=result,
                    postconditions=postconditions,
                    invariants=invariants,
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
                    invariants=invariants,
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

            context, inputs = _prepare_call(signature, args, kwargs)
            _check_entry_contracts(
                preconditions=preconditions,
                invariants=invariants,
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
                    invariants=invariants,
                    exc=exc,
                )

            wrapped_manager = _maybe_wrap_async_context_manager(
                result=result,
                postconditions=postconditions,
                invariants=invariants,
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
                invariants=invariants,
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
) -> Callable[[ClassType], ClassType]:
    normalized = tuple(_require_invariant_clause(clause) for clause in clauses)

    def decorator(cls: ClassType) -> ClassType:
        for name, attribute in vars(cls).items():
            wrapped = _wrap_class_attribute(
                name=name,
                attribute=attribute,
                invariants=normalized,
                include_private=include_private,
                include_dunder=include_dunder,
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
        "message": clause.message,
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


def violation_to_dict(violation: _native.ContractViolation) -> Dict[str, Any]:
    return {
        "function": violation.function,
        "kind": violation.kind,
        "condition": violation.condition,
        "message": violation.message,
        "details": violation.details,
        "location": location_to_dict(violation.location),
        "inputs": [input_snapshot_to_dict(snapshot) for snapshot in violation.inputs],
    }


def violation_to_json(violation: _native.ContractViolation) -> str:
    return json.dumps(violation_to_dict(violation), ensure_ascii=False, sort_keys=True)


def violation_to_sarif_result(
    violation: Union[_native.ContractViolation, ContractViolationError],
) -> Dict[str, Any]:
    normalized = _normalize_violation(violation)
    result: Dict[str, Any] = {
        "ruleId": _sarif_rule_id(normalized),
        "level": "error",
        "message": {
            "text": normalized.message or normalized.condition,
        },
        "properties": {
            "contractKind": normalized.kind,
            "condition": normalized.condition,
            "details": normalized.details,
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
            "fullDescription": {"text": violation.message or violation.condition},
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
    message: Optional[str],
    checker: Optional[Callable[..., bool]],
) -> _ClauseSpec:
    native = _native.ContractClause(kind, condition, message)
    return _ClauseSpec(
        kind=kind, condition=condition, message=message, checker=checker, native=native
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
    condition_or_predicate: Union[str, Predicate, ExceptionMatcher, ExceptionSpec],
    predicate: Optional[Callable[..., bool]],
) -> Tuple[str, Callable[..., bool]]:
    if (
        predicate is None
        and callable(condition_or_predicate)
        and not _is_exception_spec(condition_or_predicate)
    ):
        checker = cast(Callable[..., bool], condition_or_predicate)
        return _callable_label(checker), checker

    if isinstance(condition_or_predicate, str) and predicate is not None:
        return condition_or_predicate, predicate

    raise TypeError("条件文字列とcallableの組、またはcallable単体を渡してください")


def _callable_label(predicate: Callable[..., bool]) -> str:
    name = getattr(predicate, "__name__", predicate.__class__.__name__)
    if name == "<lambda>":
        return "<lambda>"
    return name


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

    if _matches_error_contract(
        clauses=error_contracts,
        function_path=function_path,
        location=location,
        inputs=inputs,
        context=context,
        exc=exc,
    ):
        raise exc

    if error_contracts:
        raise _build_violation_error(
            function_path=function_path,
            kind="error",
            condition=" or ".join(clause.condition for clause in error_contracts),
            message=_join_messages(error_contracts),
            location=location,
            inputs=inputs,
            details=_exception_details(exc),
        ) from exc

    if panic_contract is not None:
        raise _build_violation_error(
            function_path=function_path,
            kind="panic",
            condition=panic_contract.condition,
            message=panic_contract.message,
            location=location,
            inputs=inputs,
            details=_exception_details(exc),
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
) -> Optional[Callable[..., Any]]:
    if isinstance(attribute, (staticmethod, classmethod, property)):
        return None

    if not inspect.isfunction(attribute):
        return None

    if not _should_wrap_method_name(
        name, include_private=include_private, include_dunder=include_dunder
    ):
        return None

    if not _has_instance_receiver(attribute):
        return None

    return _wrap_method_with_invariants(attribute, invariants)


def _should_wrap_method_name(name: str, include_private: bool, include_dunder: bool) -> bool:
    if name == "__init__":
        return True

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

            context, inputs = _prepare_call(signature, args, kwargs)

            if not skip_pre:
                _check_boolean_clauses(
                    clauses=invariants,
                    function_path=function_path,
                    location=location,
                    inputs=inputs,
                    available=context,
                )

            generator = function(*args, **kwargs)
            return _ContractAsyncGenerator(
                generator=generator,
                postconditions=[],
                invariants=invariants,
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

            context, inputs = _prepare_call(signature, args, kwargs)

            if not skip_pre:
                _check_boolean_clauses(
                    clauses=invariants,
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
                    clauses=invariants,
                    function_path=function_path,
                    location=location,
                    inputs=inputs,
                    available=context,
                )
                raise

            _check_boolean_clauses(
                clauses=invariants,
                function_path=function_path,
                location=location,
                inputs=inputs,
                available=context,
            )
            return _maybe_wrap_async_context_manager(
                result=result,
                postconditions=[],
                invariants=invariants,
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

        context, inputs = _prepare_call(signature, args, kwargs)

        if not skip_pre:
            _check_boolean_clauses(
                clauses=invariants,
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
                clauses=invariants,
                function_path=function_path,
                location=location,
                inputs=inputs,
                available=context,
            )
            raise

        _check_boolean_clauses(
            clauses=invariants,
            function_path=function_path,
            location=location,
            inputs=inputs,
            available=context,
        )
        return _maybe_wrap_async_context_manager(
            result=result,
            postconditions=[],
            invariants=invariants,
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
            matched = bool(_invoke(clause.checker, available))
        except ContractViolationError:
            raise
        except Exception as exc:
            raise _build_violation_error(
                function_path=function_path,
                kind=clause.kind,
                condition=clause.condition,
                message=clause.message,
                location=location,
                inputs=inputs,
                details=f"predicate raised {type(exc).__name__}: {exc}",
            ) from exc

        if not matched:
            raise _build_violation_error(
                function_path=function_path,
                kind=clause.kind,
                condition=clause.condition,
                message=clause.message,
                location=location,
                inputs=inputs,
            )


def _matches_error_contract(
    clauses: Sequence[_ClauseSpec],
    function_path: str,
    location: _native.ContractLocation,
    inputs: Sequence[_native.InputSnapshot],
    context: Mapping[str, Any],
    exc: Exception,
) -> bool:
    if not clauses:
        return False

    available = dict(context)
    available["exc"] = exc
    available["error"] = exc

    for clause in clauses:
        assert clause.checker is not None
        try:
            if bool(_invoke(clause.checker, available)):
                return True
        except Exception as inner_exc:
            raise _build_violation_error(
                function_path=function_path,
                kind="error",
                condition=clause.condition,
                message=clause.message,
                location=location,
                inputs=inputs,
                details=f"predicate raised {type(inner_exc).__name__}: {inner_exc}",
            ) from inner_exc

    return False


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
    message: Optional[str],
    location: _native.ContractLocation,
    inputs: Sequence[_native.InputSnapshot],
    details: Optional[str] = None,
) -> ContractViolationError:
    violation = _native.ContractViolation(
        function_path,
        kind,
        condition,
        message,
        location,
        list(inputs),
        details,
    )
    return ContractViolationError(violation)


def _normalize_violation(
    violation: Union[_native.ContractViolation, ContractViolationError],
) -> _native.ContractViolation:
    if isinstance(violation, ContractViolationError):
        return violation.violation
    return violation


def _sarif_rule_id(violation: _native.ContractViolation) -> str:
    return f"contract/{violation.kind}"


def _unique_violations_by_rule(
    violations: Sequence[_native.ContractViolation],
) -> Sequence[_native.ContractViolation]:
    unique: Dict[str, _native.ContractViolation] = {}
    for violation in violations:
        unique.setdefault(_sarif_rule_id(violation), violation)
    return list(unique.values())


def _exception_details(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}"


def _join_messages(clauses: Sequence[_ClauseSpec]) -> Optional[str]:
    messages = [clause.message for clause in clauses if clause.message]
    if not messages:
        return None
    return " / ".join(messages)


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
