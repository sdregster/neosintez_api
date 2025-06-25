"""
Ресурсные классы для работы с различными разделами API Неосинтез.
"""

from .base import BaseResource
from .classes import ClassesResource
from .attributes import AttributesResource
from .objects import ObjectsResource

__all__ = [
    "BaseResource",
    "ClassesResource",
    "AttributesResource",
    "ObjectsResource",
]
