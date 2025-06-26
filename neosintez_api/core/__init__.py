"""
Основные компоненты для работы с API Неосинтез.
Этот пакет содержит core-функциональность для взаимодействия с API Неосинтез.
"""

from .client import NeosintezClient
from .exceptions import (
    NeosintezError,
    NeosintezAuthError,
    NeosintezAPIError,
    NeosintezConnectionError,
    NeosintezTimeoutError,
    NeosintezValidationError,
)

__all__ = [
    "NeosintezClient",
    "NeosintezError",
    "NeosintezAuthError",
    "NeosintezAPIError",
    "NeosintezConnectionError",
    "NeosintezTimeoutError",
    "NeosintezValidationError",
]
