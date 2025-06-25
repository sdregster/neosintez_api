"""
Пакет для удобного взаимодействия с API системы Неосинтез.
Предоставляет асинхронный API-клиент для выполнения запросов к системе.
"""

from .client import NeosintezClient
from .config import NeosintezSettings
from .exceptions import (
    NeosintezError,
    NeosintezAuthError,
    NeosintezAPIError,
    NeosintezConnectionError,
    NeosintezTimeoutError,
)
from .models import (
    SearchFilter,
    SearchCondition,
)

__all__ = [
    "NeosintezClient",
    "NeosintezSettings",
    "NeosintezError",
    "NeosintezAuthError",
    "NeosintezAPIError",
    "NeosintezConnectionError",
    "NeosintezTimeoutError",
    "SearchFilter",
    "SearchCondition",
]
