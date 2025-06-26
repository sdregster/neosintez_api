"""
Основные компоненты для работы с API Неосинтез.
Этот пакет содержит core-функциональность для взаимодействия с API Неосинтез.
"""

from .client import NeosintezClient
from .exceptions import (
    NeosintezAPIError,
    NeosintezAuthError,
    NeosintezConnectionError,
    NeosintezError,
    NeosintezTimeoutError,
    NeosintezValidationError,
)


__all__ = [
    "NeosintezAPIError",
    "NeosintezAuthError",
    "NeosintezClient",
    "NeosintezConnectionError",
    "NeosintezError",
    "NeosintezTimeoutError",
    "NeosintezValidationError",
]
