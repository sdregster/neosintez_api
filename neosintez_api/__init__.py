"""
Пакет для работы с API Неосинтез через Python.
"""

from . import models
from .cli import cli
from .config import NeosintezConfig
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
    "NeosintezConfig",
    "NeosintezTimeoutError",
    "NeosintezValidationError",
    "ObjectService",
    "create_model_from_class_attributes",
    "neosintez_model",
    "models",
    "cli",
]

__version__ = "0.1.0"
