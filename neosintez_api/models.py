"""
Модели данных для работы с API Неосинтез.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr


class TokenResponse(BaseModel):
    """
    Ответ с токеном доступа от API.

    Attributes:
        access_token: Токен доступа
        token_type: Тип токена (обычно "bearer")
        expires_in: Срок истечения токена в секундах
    """

    access_token: str
    token_type: str
    expires_in: int


class SearchFilter(BaseModel):
    """
    Фильтр для поиска объектов.

    Attributes:
        Type: Тип фильтра:
            1 = ByText - полнотекстовый поиск
            2 = ByEntity - поиск по идентификатору сущности
            3 = ByEntity[] - поиск по массиву идентификаторов сущностей
            4 = ByParent - поиск по идентификатору родительской сущности
            5 = ByClass - поиск по идентификатору класса
            6 = ByAttribute - поиск по атрибуту
            7 = ByAttributeVersionId - поиск по версии
        Value: Значение для фильтрации
    """

    Type: int = Field(..., description="Тип фильтра")
    Value: Any = Field(..., description="Значение фильтра")


class SearchCondition(BaseModel):
    """
    Условие для поиска объектов.

    Attributes:
        AttributeId: ID атрибута для условия поиска
        Operation: Операция сравнения
        Value: Значение для сравнения
    """

    AttributeId: UUID
    Operation: str
    Value: Any


class SearchRequest(BaseModel):
    """
    Запрос на поиск объектов.

    Attributes:
        Filters: Список фильтров
        Conditions: Список условий
        Take: Количество записей для выборки
        Skip: Количество записей для пропуска (для пагинации)
    """

    Filters: List[SearchFilter] = Field(default_factory=list)
    Conditions: List[SearchCondition] = Field(default_factory=list)
    Take: Optional[int] = Field(None, description="Лимит выборки")
    Skip: Optional[int] = Field(None, description="Смещение выборки")


class EntityClass(BaseModel):
    """
    Класс объекта в системе Неосинтез.

    Attributes:
        Id: Идентификатор класса
        Name: Наименование класса
        Description: Описание класса
    """

    Id: UUID
    Name: str
    Description: Optional[str] = None


class AttributeType(BaseModel):
    """
    Тип атрибута объекта в системе Неосинтез.

    Attributes:
        Id: Идентификатор типа атрибута
        Name: Наименование типа атрибута
    """

    Id: int
    Name: str


class AttributeConstraint(BaseModel):
    """
    Ограничения для атрибута-ссылки.

    Описывает правила, по которым можно выбирать значение для ссылочного
    атрибута. Например, ограничивает выбор объектов определенным классом
    или деревом объектов.

    Attributes:
        Type: Тип ограничения (1 - по классу, 3 - по корневому объекту).
        EntityId: ID класса, которым ограничивается выбор.
        ObjectRootId: ID корневого объекта, в рамках которого ведется поиск.
    """

    Type: int
    EntityId: Optional[UUID] = None
    ObjectRootId: Optional[UUID] = None


class Attribute(BaseModel):
    """
    Атрибут объекта в системе Неосинтез.

    Attributes:
        Id: Идентификатор атрибута
        Name: Наименование атрибута
        Type: Тип данных атрибута (может быть числом или объектом AttributeType)
        Constraints: Ограничения атрибута
        Description: Описание атрибута (опционально)
        EntityId: Идентификатор сущности, к которой относится атрибут (опционально)
        IsCollection: Является ли атрибут коллекцией (опционально)
        DefaultValue: Значение по умолчанию (опционально)
        ValidationRule: Правило валидации (опционально)
        Items: Список возможных значений для атрибутов-ссылок (опционально)
    """

    Id: UUID
    Name: str
    Type: Optional[Union[AttributeType, int]] = None
    Constraints: Optional[List[AttributeConstraint]] = Field(default_factory=list)
    Description: Optional[str] = None
    EntityId: Optional[UUID] = None
    IsCollection: Optional[bool] = None
    DefaultValue: Optional[Any] = None
    ValidationRule: Optional[str] = None
    Items: Optional[List[Any]] = None


class AttributeListResponse(BaseModel):
    """
    Ответ на запрос списка атрибутов.

    Attributes:
        Result: Список атрибутов
    """

    Result: List[Attribute]


class AttributeValue(BaseModel):
    """
    Значение атрибута объекта.

    Attributes:
        Id: Идентификатор атрибута
        Value: Значение атрибута
        Type: Тип атрибута
    """

    Id: UUID
    Value: Any
    Type: Optional[str] = None


class NeoObject(BaseModel):
    """
    Объект в системе Неосинтез.

    Attributes:
        Id: Идентификатор объекта
        Name: Наименование объекта
        Description: Описание объекта
        EntityId: Идентификатор сущности (класса)
        Attributes: Атрибуты объекта
    """

    Id: UUID
    Name: str
    Description: Optional[str] = None
    EntityId: UUID
    Attributes: Optional[Dict[str, Any]] = None


class SearchResultObject(BaseModel):
    """
    Объект, возвращаемый в результатах поиска.
    Содержит сам объект и информацию о его родителе.
    """

    obj: NeoObject = Field(alias="Object")
    parent: Optional[NeoObject] = Field(default=None, alias="Parent")

    model_config = ConfigDict(populate_by_name=True)


class SearchResponse(BaseModel):
    """
    Ответ на поисковый запрос.

    Attributes:
        Result: Результаты поиска
        Total: Общее количество найденных объектов
    """

    Result: List[SearchResultObject]
    Total: int


class PathAncestor(BaseModel):
    """
    Информация о предке в пути объекта.

    Attributes:
        Id: Идентификатор объекта
        Name: Наименование объекта
    """

    Id: UUID
    Name: str


class PathResponse(BaseModel):
    """
    Ответ с информацией о пути объекта.

    Attributes:
        AncestorsOrSelf: Список предков объекта, включая сам объект
    """

    AncestorsOrSelf: List[PathAncestor]


class AttributeModel(BaseModel):
    """
    Модель атрибута для работы с API Неосинтеза.

    Attributes:
        id: Идентификатор атрибута
        name: Название атрибута
        value: Значение атрибута
        value_type: Тип значения атрибута
    """

    id: UUID = Field(alias="Id")
    name: str = Field(alias="Name")
    value: Any = Field(alias="Value")
    value_type: Optional[int] = Field(None, alias="Type")

    model_config = ConfigDict(
        populate_by_name=True,
    )


class EquipmentModel(BaseModel):
    """
    Пример модели оборудования с использованием алиасов для маппинга полей.

    Это пример модели, которая демонстрирует использование Field(alias=...)
    для маппинга между названиями полей в Python-коде и названиями атрибутов в API.

    Attributes:
        name: Название оборудования
        model: Модель оборудования
        serial_number: Серийный номер оборудования
        installation_date: Дата установки оборудования
        is_active: Флаг активности оборудования
    """

    __class_name__ = "Оборудование"
    """Имя класса объекта в Неосинтезе"""

    name: str = Field(alias="Name")
    model: str = Field(alias="Модель оборудования")
    serial_number: str = Field(alias="Серийный номер")
    installation_date: datetime = Field(alias="Дата установки")
    is_active: bool = Field(True, alias="Активен")

    model_config = ConfigDict(
        populate_by_name=True,
    )


class NeosintezBaseModel(BaseModel):
    """
    Базовая модель для всех объектов, работающих с API Неосинтеза.

    Она предоставляет механизм для связи с классом в Неосинтезе
    и хранения внутреннего состояния объекта (ID, метаданные и т.д.),
    оставляя пользовательский интерфейс модели чистым.
    """

    # Системные поля, которые будут у каждого объекта Неосинтеза.
    # Они будут заполняться автоматически сервисами.
    # Используем PrivateAttr, чтобы Pydantic не считал их частью схемы.
    _id: Optional[str] = PrivateAttr(default=None)
    _class_id: Optional[str] = PrivateAttr(default=None)
    _parent_id: Optional[str] = PrivateAttr(default=None)

    class Neosintez:
        """
        Внутренний класс для хранения мета-конфигурации,
        связывающей Pydantic-модель с классом Неосинтеза.
        """

        class_name: str

    model_config = ConfigDict(
        populate_by_name=True,
        # Разрешаем хранить дополнительные атрибуты, не объявленные в модели
        # (например, наши приватные _id, _class_id)
        extra="allow",
    )
