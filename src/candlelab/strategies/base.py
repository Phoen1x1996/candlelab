"""Strategy interface and registry."""

from __future__ import annotations

import dataclasses
import typing
from abc import ABC, abstractmethod
from typing import Any, ClassVar, TypeVar

import pandas as pd


class Strategy(ABC):
    """Base class for strategies.

    Concrete strategies are ``@dataclass`` subclasses whose fields are their tunable
    parameters. They turn candles into a *target position* series; the engine decides
    when and at what price that target is executed.
    """

    name: ClassVar[str]
    description: ClassVar[str] = ""

    @abstractmethod
    def target_position(self, candles: pd.DataFrame) -> pd.Series:
        """Return the desired exposure for each bar.

        ``0.0`` means flat and ``1.0`` means fully long. The value at bar ``t`` must only
        use information available at the **close** of bar ``t``.
        """

    def params(self) -> dict[str, Any]:
        """Current parameter values."""
        return dataclasses.asdict(self) if dataclasses.is_dataclass(self) else {}


S = TypeVar("S", bound=type[Strategy])

_REGISTRY: dict[str, type[Strategy]] = {}


def register(cls: S) -> S:
    """Class decorator that makes a strategy available by ``cls.name``."""
    name = getattr(cls, "name", None)
    if not name:
        raise TypeError(f"{cls.__name__} must define a non-empty 'name'")
    if name in _REGISTRY and _REGISTRY[name] is not cls:
        raise ValueError(f"strategy name {name!r} is already registered")
    _REGISTRY[name] = cls
    return cls


def list_strategies() -> list[type[Strategy]]:
    """All registered strategy classes, sorted by name."""
    return [_REGISTRY[name] for name in sorted(_REGISTRY)]


def strategy_class(name: str) -> type[Strategy]:
    try:
        return _REGISTRY[name]
    except KeyError:
        known = ", ".join(sorted(_REGISTRY)) or "(none)"
        raise ValueError(f"unknown strategy {name!r}; available: {known}") from None


def parameter_types(cls: type[Strategy]) -> dict[str, type]:
    """Map each parameter name of ``cls`` to its annotated type."""
    if not dataclasses.is_dataclass(cls):
        return {}
    hints = typing.get_type_hints(cls)
    return {f.name: hints[f.name] for f in dataclasses.fields(cls)}


_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}


def coerce_param(cls: type[Strategy], key: str, raw: str) -> Any:
    """Convert a string (e.g. from the command line) to the type of parameter ``key``."""
    types = parameter_types(cls)
    if key not in types:
        known = ", ".join(types) or "(none)"
        raise ValueError(f"strategy {cls.name!r} has no parameter {key!r}; known: {known}")
    target = types[key]
    try:
        if target is bool:
            lowered = raw.strip().lower()
            if lowered in _TRUE:
                return True
            if lowered in _FALSE:
                return False
            raise ValueError(raw)
        if target in (int, float, str):
            return target(raw)
    except ValueError:
        raise ValueError(f"parameter {key!r} expects {target.__name__}, got {raw!r}") from None
    raise TypeError(f"parameter {key!r} has unsupported type {target!r}")


def get_strategy(name: str, **params: Any) -> Strategy:
    """Instantiate a registered strategy with the given parameters."""
    cls = strategy_class(name)
    known = parameter_types(cls)
    unknown = sorted(set(params) - set(known))
    if unknown:
        raise ValueError(
            f"strategy {name!r} has no parameter(s) {', '.join(unknown)}; "
            f"known: {', '.join(known) or '(none)'}"
        )
    return cls(**params)
