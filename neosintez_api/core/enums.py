"""
Перечисления для работы с API Неосинтез.
"""

from enum import Enum, auto


class WioAttributeType(int, Enum):
    """Типы атрибутов в API Неосинтез."""

    NUMBER = 1
    """Числовой тип."""

    STRING = 2
    """Строковый тип."""

    DATE = 3
    """Тип даты (без времени)."""

    TIME = 4
    """Тип времени (без даты)."""

    DATETIME = 5
    """Тип даты и времени."""

    TEXT = 6
    """Текстовый тип (поддерживает форматирование)."""

    FILE = 7
    """Файловый тип."""

    OBJECT_LINK = 8
    """Ссылочный тип на другой объект."""

    COLLECTION = 9
    """Коллекционный тип."""

    REFERENCE_COLLECTION = 10
    """Коллекция ссылок на объекты."""

    TEMPLATE = 15
    """Шаблонный тип."""

    @property
    def as_string(self) -> str:
        """Возвращает строковое представление типа атрибута."""
        return {
            WioAttributeType.NUMBER: "Number",
            WioAttributeType.STRING: "String",
            WioAttributeType.DATE: "Date",
            WioAttributeType.TIME: "Time",
            WioAttributeType.DATETIME: "DateTime",
            WioAttributeType.TEXT: "Text",
            WioAttributeType.FILE: "File",
            WioAttributeType.OBJECT_LINK: "ObjectLink",
            WioAttributeType.COLLECTION: "Collection",
            WioAttributeType.REFERENCE_COLLECTION: "ReferenceCollection",
            WioAttributeType.TEMPLATE: "Template",
        }.get(self, "Unknown")


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
