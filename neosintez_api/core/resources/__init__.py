"""
Ресурсные классы для работы с различными разделами API Неосинтез.
"""

from .base import BaseResource
from .objects import ObjectsResource
from .attributes import AttributesResource
from .classes import ClassesResource


__all__ = [
    "BaseResource",
    "ObjectsResource",
    "AttributesResource",
    "ClassesResource",
]
