"""
Ресурсные классы для работы с различными разделами API Неосинтез.
"""

from .attributes import AttributesResource
from .base import BaseResource
from .classes import ClassesResource
from .objects import ObjectsResource


__all__ = [
    "AttributesResource",
    "BaseResource",
    "ClassesResource",
    "ObjectsResource",
]
