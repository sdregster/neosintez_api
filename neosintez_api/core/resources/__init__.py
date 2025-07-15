"""
Ресурсные классы для работы с различными разделами API Неосинтез.
"""

from .attributes import AttributesResource
from .base import BaseResource
from .classes import ClassesResource
from .content import ContentResource
from .objects import ObjectsResource


__all__ = [
    "BaseResource",
    "ObjectsResource",
    "AttributesResource",
    "ClassesResource",
    "ContentResource",
]
