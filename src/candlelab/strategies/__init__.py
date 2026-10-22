"""Built-in strategies. Importing this package registers all of them."""

from candlelab.strategies import ma_cross  # noqa: F401  (registers strategies)
from candlelab.strategies.base import (
    Strategy,
    coerce_param,
    get_strategy,
    list_strategies,
    parameter_types,
    register,
    strategy_class,
)

__all__ = [
    "Strategy",
    "coerce_param",
    "get_strategy",
    "list_strategies",
    "parameter_types",
    "register",
    "strategy_class",
]
