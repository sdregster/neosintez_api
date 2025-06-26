"""
Сервисный слой для работы с API Неосинтез.
"""

from .cache import TTLCache, cached
from .object_service import ObjectService

__all__ = [
    "TTLCache",
    "cached",
    "ObjectService",
]
