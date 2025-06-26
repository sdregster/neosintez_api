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
from .model_utils import neosintez_model, create_model_from_class_attributes
from .services.object_service import ObjectService

__all__ = [
    "NeosintezSettings",
    "NeosintezClient",
    "NeosintezError",
    "NeosintezAuthError",
    "NeosintezAPIError",
    "NeosintezConnectionError",
    "NeosintezTimeoutError",
    "NeosintezValidationError",
    "neosintez_model",
    "create_model_from_class_attributes",
    "ObjectService",
]

__version__ = "0.1.0"
