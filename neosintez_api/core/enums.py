"""
Перечисления для работы с API Неосинтез.
"""

from enum import Enum, auto


class WioAttributeType(str, Enum):
    """Типы атрибутов в API Неосинтез."""

    STRING = "String"
    """Строковый тип."""

    INTEGER = "Integer"
    """Целочисленный тип."""

    DECIMAL = "Decimal"
    """Десятичный тип."""

    DATETIME = "DateTime"
    """Тип даты и времени."""

    REFERENCE = "Reference"
    """Ссылочный тип."""

    BOOLEAN = "Boolean"
    """Логический тип."""

    COLLECTION = "Collection"
    """Коллекционный тип."""

    FILE = "File"
    """Файловый тип."""


class HTTPMethod(str, Enum):
    """HTTP методы для запросов к API."""

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"


class CachePolicy(Enum):
    """Политика кэширования для API запросов."""

    NO_CACHE = auto()
    """Не использовать кэш."""

    USE_CACHE = auto()
    """Использовать кэш, если доступен."""

    REFRESH = auto()
    """Обновить кэш принудительно."""
