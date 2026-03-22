from __future__ import annotations

from typing import Protocol, TypeVar, Union

from typing_extensions import ParamSpec, TypeAlias

from .models import ViolationDetail

P = ParamSpec("P")
TReturn = TypeVar("TReturn", contravariant=True)
TSelf = TypeVar("TSelf", contravariant=True)
TException = TypeVar("TException", bound=BaseException, contravariant=True)

ValidationResult: TypeAlias = Union[bool, None, ViolationDetail]


class PrePredicate(Protocol[P]):
    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> ValidationResult: ...


class PostPredicate(Protocol[TReturn, P]):
    def __call__(
        self, result: TReturn, /, *args: P.args, **kwargs: P.kwargs
    ) -> ValidationResult: ...


class InvariantPredicate(Protocol[TSelf]):
    def __call__(self, value: TSelf, /) -> ValidationResult: ...


class ErrorPredicate(Protocol[TException, P]):
    def __call__(
        self,
        exc: TException,
        /,
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> ValidationResult: ...
