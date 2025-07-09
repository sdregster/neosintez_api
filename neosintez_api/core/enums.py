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


class SearchFilterType(int, Enum):
    """
    Типы фильтров для поиска объектов в API Неосинтез.

    - `BY_ATTRIBUTE`: Поиск по значению атрибута.
    - `BY_FULL_TEXT`: Полнотекстовый поиск.
    - `BY_NAME`: Поиск по имени объекта.
    - `BY_ID`: Поиск по ID объекта.
    - `BY_PARENT`: Поиск по ID родительского объекта.
    - `BY_CLASS`: Поиск по ID класса.
    - `BY_EXTERNAL_ID`: Поиск по ID в сторонней системе.
    - `BY_GEOMETRY`: Поиск по геометрии.
    """

    BY_ATTRIBUTE = 0
    BY_FULL_TEXT = 1
    BY_NAME = 2
    BY_ID = 3
    BY_PARENT = 4
    BY_CLASS = 5
    BY_EXTERNAL_ID = 6
    BY_GEOMETRY = 7


class SearchConditionType(int, Enum):
    """
    Типы условий для поиска объектов согласно API Неосинтез.

    Основан на SearchConditionType из swagger.json.
    """

    ATTRIBUTE = 1
    """Поиск по атрибуту."""

    NAME = 2
    """Поиск по имени."""

    LEVEL = 3
    """Поиск по уровню."""

    PARENT = 4
    """Поиск по родителю."""

    ENTITY = 5
    """Поиск по сущности."""

    CREATED_BY = 6
    """Поиск по создателю."""

    CREATION_DATE = 7
    """Поиск по дате создания."""

    DESCENDANTS = 8
    """Поиск по потомкам."""

    ANCESTORS = 9
    """Поиск по предкам."""

    MODIFICATION_DATE = 10
    """Поиск по дате модификации."""

    ELEMENT_LINK = 11
    """Поиск по связи элемента."""

    ID = 15
    """Поиск по ID."""

    VERSION = 16
    """Поиск по версии."""

    VERSION_TIMESTAMP = 17
    """Поиск по временной метке версии."""


class SearchOperatorType(int, Enum):
    """
    Типы операторов для поиска согласно API Неосинтез.

    Основан на SearchOperatorType из swagger.json.
    """

    EQUALS = 1
    """Равно."""

    NOT_EQUALS = 2
    """Не равно."""

    GREATER = 3
    """Больше."""

    LESS = 4
    """Меньше."""

    GREATER_OR_EQUAL = 5
    """Больше или равно."""

    LESS_OR_EQUAL = 6
    """Меньше или равно."""

    EXISTS = 7
    """Существует."""

    NOT_EXISTS = 8
    """Не существует."""

    STARTS_WITH = 9
    """Начинается с."""

    CONTAINS = 10
    """Содержит."""

    NOT_CONTAINS = 11
    """Не содержит."""

    CONTAINS_OBJECT = 12
    """Содержит объект."""

    NOT_CONTAINS_OBJECT = 13
    """Не содержит объект."""

    CONTAINS_WORD = 14
    """Содержит слово."""

    NOT_CONTAINS_WORD = 15
    """Не содержит слово."""


class SearchLogicType(int, Enum):
    """
    Типы логики для объединения условий поиска согласно API Неосинтез.

    Основан на SearchLogicType из swagger.json.
    """

    NONE = 0
    """Без логики."""

    OR = 1
    """ИЛИ."""

    AND = 2
    """И."""


class SearchQueryMode(int, Enum):
    """
    Режимы поискового запроса согласно API Неосинтез.

    Основан на SearchQueryMode из swagger.json.
    """

    ACTUAL_ONLY = 0
    """Только актуальные."""

    ACTUAL_AND_VERSIONED = 1
    """Актуальные и версионные."""

    VERSIONED_ONLY = 2
    """Только версионные."""


class SearchDirectionType(int, Enum):
    """
    Типы направления для поиска согласно API Неосинтез.

    Основан на SearchDirectionType из swagger.json.
    """

    NONE = 0
    """Без направления."""

    INSIDE = 1
    """Внутри."""

    OUTSIDE = 2
    """Снаружи."""


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
