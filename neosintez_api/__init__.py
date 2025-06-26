"""
Пакет для работы с API Неосинтез через Python.
"""

from .config import NeosintezSettings
from .core import (
    NeosintezAPIError,
    NeosintezAuthError,
    NeosintezClient,
    NeosintezConnectionError,
    NeosintezError,
    NeosintezTimeoutError,
    NeosintezValidationError,
)
from .model_utils import create_model_from_class_attributes, neosintez_model
from .services.object_service import ObjectService


__all__ = [
    "NeosintezAPIError",
    "NeosintezAuthError",
    "NeosintezClient",
    "NeosintezConnectionError",
    "NeosintezError",
    "NeosintezSettings",
    "NeosintezTimeoutError",
    "NeosintezValidationError",
    "ObjectService",
    "create_model_from_class_attributes",
    "neosintez_model",
]

__version__ = "0.1.0"
