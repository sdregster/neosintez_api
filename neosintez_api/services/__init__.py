"""
Сервисы для работы с API Неосинтез.
"""

from .cache import TTLCache, cached

__all__ = [
    "TTLCache",
    "cached",
]
