"""
Автоматически сгенерированные модели данных из Swagger спецификации API Неосинтез.

НЕ РЕДАКТИРОВАТЬ ВРУЧНУЮ!
Этот файл генерируется автоматически из swagger.json.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import datetime
import uuid


class AttributeTypeModel(BaseModel):
    """Модель AttributeTypeModel"""

    Id: int
    Name: Optional[str] = Field(default=None)


class Group(BaseModel):
    """Модель Group"""

    Id: int
    Name: Optional[str] = Field(default=None)
    Description: Optional[str] = Field(default=None)


class ConstraintType(BaseModel):
    """Тип ограничения значения атрибута"""

    pass


class Constraint(BaseModel):
    """Ограничение значения атрибута

    <br>Если Type = Entity, то EntityId обязателен, ObjectRootId должен быть `null`<br>Если Type = ObjectRoot, то ObjectRootId обязателен, EntityId должен быть `null`"""

    Type: ConstraintType
    EntityId: Optional[uuid.UUID] = Field(
        default=None, description="Значение ограничения по классу"
    )
    ObjectRootId: Optional[uuid.UUID] = Field(
        default=None,
        description="Значение ограничения по корню поддерева возможных значений",
    )


class Unit(BaseModel):
    """Модель Unit"""

    Id: int
    Name: Optional[str] = Field(default=None)
    Description: Optional[str] = Field(default=None)


class Attribute(BaseModel):
    """Модель Attribute"""

    Id: uuid.UUID
    Name: Optional[str] = Field(default=None)
    Description: Optional[str] = Field(default=None)
    Type: Optional[AttributeTypeModel] = Field(default=None)
    Group: Optional[Group] = Field(default=None)
    Constraints: Optional[List[Constraint]] = Field(default=None)
    Unit: Optional[Unit] = Field(default=None)


class ElementAttributeType(BaseModel):
    """Тип сущности, используемой для сопоставления со значением маппинга."""

    pass


class ElementAttribute(BaseModel):
    """Модель ElementAttribute"""

    Type: ElementAttributeType
    Name: Optional[str] = Field(
        default=None,
        description="Получает и задаёт название свойства. Используется в случае когда ElementAttributeType == ElementAttributeType.Property",
    )
    Description: Optional[str] = Field(
        default=None,
        description="Получает и задаёт описание свойства. Используется в случае когда ElementAttributeType == ElementAttributeType.Property",
    )
    DisplayName: Optional[str] = Field(
        default=None, description="Калькулируемое свойство для отображения и сортировки"
    )


class AutoLinkingMappingCondition(BaseModel):
    """Модель AutoLinkingMappingCondition"""

    ElementAttribute: Optional[ElementAttribute] = Field(default=None)
    ClassAttributeId: uuid.UUID


class AutoLinkingMapping(BaseModel):
    """Модель AutoLinkingMapping"""

    Models: Optional[List[int]] = Field(default=None)
    Objects: Optional[List[uuid.UUID]] = Field(default=None)
    Classes: Optional[List[uuid.UUID]] = Field(default=None)
    Conditions: Optional[List[AutoLinkingMappingCondition]] = Field(default=None)


class BaseItem(BaseModel):
    """Базовый класс сущности"""

    Id: uuid.UUID = Field(description="Идентификатор объекта")
    Name: str = Field(min_length=1, max_length=450, description="Название объекта")
    Description: Optional[str] = Field(
        default=None, max_length=500, description="Описание объекта"
    )


class BaseItemNg_Of_Guid(BaseModel):
    """Модель BaseItemNg_Of_Guid"""

    Id: uuid.UUID = Field(description="Идентификатор объекта")
    Name: str = Field(min_length=1, max_length=450, description="Название объекта")
    Description: Optional[str] = Field(
        default=None, max_length=450, description="Описание объекта"
    )


class BaseItemNg_Of_Int32(BaseModel):
    """Модель BaseItemNg_Of_Int32"""

    Id: int = Field(description="Идентификатор объекта")
    Name: str = Field(min_length=1, max_length=450, description="Название объекта")
    Description: Optional[str] = Field(
        default=None, max_length=450, description="Описание объекта"
    )


class BaseItem_Of_Int32(BaseModel):
    """Базовый класс"""

    Id: int = Field(description="Идентификатор объекта")
    Name: str = Field(min_length=1, max_length=450, description="Название объекта")
    Description: Optional[str] = Field(
        default=None, max_length=500, description="Описание объекта"
    )


class BaseItem_Of_Int64(BaseModel):
    """Базовый класс"""

    Id: int = Field(description="Идентификатор объекта")
    Name: str = Field(min_length=1, max_length=450, description="Название объекта")
    Description: Optional[str] = Field(
        default=None, max_length=500, description="Описание объекта"
    )


class BrandingOptions(BaseModel):
    """Модель BrandingOptions"""

    Name: Optional[str] = Field(default=None)
    Logo: Optional[str] = Field(default=None)


class Cardinality(BaseModel):
    """Кардинальность (ограничения, вида, атрибутов в виде)"""

    pass


class ClientCredentials(BaseModel):
    """Модель ClientCredentials"""

    Secret: Optional[str] = Field(
        default=None,
        description="Если секрет не указан, клиент считается публичным, и для него возможен только Implicit Flow",
    )
    RedirectUris: Optional[List[str]] = Field(default=None)


class ClientsOptions(BaseModel):
    """Модель ClientsOptions"""

    Credentials: Optional[Dict[str, Any]] = Field(
        default=None, description="clientId/secret dictionary"
    )
    TokenLifetime: int = Field(
        description="Время жизни токена с момента его получения, в секундах"
    )


class LockType(BaseModel):
    """Тип блокировки сущности"""

    pass


class WioAttributeValidationType(BaseModel):
    """Модель WioAttributeValidationType"""

    pass


class WioAttributeValidationRule(BaseModel):
    """Модель WioAttributeValidationRule"""

    Id: uuid.UUID
    Type: WioAttributeValidationType
    Message: Optional[str] = Field(default=None)
    Params: Optional[Dict[str, Any]] = Field(default=None)


class WioAttributeType(BaseModel):
    """Тип атрибута"""

    pass


class WioEntityAttribute(BaseModel):
    """Модель WioEntityAttribute"""

    Id: uuid.UUID = Field(description="Идентификатор объекта")
    Name: str = Field(min_length=1, max_length=450, description="Название объекта")
    Description: Optional[str] = Field(
        default=None, max_length=500, description="Описание объекта"
    )
    Locked: Optional[LockType] = Field(default=None)
    Type: WioAttributeType
    Constraints: Optional[List[Constraint]] = Field(
        default=None, description="Список ограничений"
    )
    Unit: Optional[BaseItem_Of_Int64] = Field(default=None)
    Group: Optional[BaseItem_Of_Int64] = Field(default=None)
    Inherited: Optional[bool] = Field(default=None)
    Rules: Optional[Dict[str, Any]] = Field(
        default=None, description="Правила валидации для атрибута"
    )


class ViewerInstance_Of_Object(BaseModel):
    """Модель ViewerInstance_Of_Object"""

    Id: uuid.UUID
    Name: Optional[str] = Field(default=None)
    Caption: Optional[str] = Field(default=None)
    Icon: Optional[str] = Field(default=None)
    Attributes: Optional[List[uuid.UUID]] = Field(default=None)
    Settings: Optional[Any] = Field(default=None)


class WioEntity(BaseModel):
    """Сущность - класс в понятии Inter Operation"""

    Id: uuid.UUID = Field(description="Идентификатор объекта")
    Name: str = Field(min_length=1, max_length=450, description="Название объекта")
    Description: Optional[str] = Field(
        default=None, max_length=500, description="Описание объекта"
    )
    Locked: Optional[LockType] = Field(default=None)
    Parent: Optional[WioEntity] = Field(default=None)
    Level: Optional[int] = Field(
        default=None, description="Уровень узла в дереве классов"
    )
    Icon: Optional[str] = Field(default=None, description="Иконка сущности")
    Attributes: Optional[Dict[str, Any]] = Field(
        default=None, description="Список атрибутов класса"
    )
    Viewers: Optional[List[ViewerInstance_Of_Object]] = Field(
        default=None, description="Список просмотрщиков"
    )


class WioObjectAttribute(BaseModel):
    """Модель WioObjectAttribute"""

    Id: uuid.UUID = Field(description="Идентификатор объекта")
    Name: str = Field(min_length=1, max_length=450, description="Название объекта")
    Description: Optional[str] = Field(
        default=None, max_length=500, description="Описание объекта"
    )
    Locked: Optional[LockType] = Field(default=None)
    Type: WioAttributeType
    Constraints: Optional[List[Constraint]] = Field(
        default=None, description="Список ограничений"
    )
    Unit: Optional[BaseItem_Of_Int64] = Field(default=None)
    Group: Optional[BaseItem_Of_Int64] = Field(default=None)
    Value: Optional[Any] = Field(default=None, description="Значение атрибута")


class ModelContentType(BaseModel):
    """Модель ModelContentType"""

    Id: int
    Name: Optional[str] = Field(default=None)


class ElementLinkItem(BaseModel):
    """Модель ElementLinkItem"""

    Id: int = Field(description="Идентификатор объекта")
    Name: str = Field(min_length=1, max_length=450, description="Название объекта")
    Description: Optional[str] = Field(
        default=None, max_length=500, description="Описание объекта"
    )
    ContentType: Optional[ModelContentType] = Field(default=None)
    Ids: Optional[List[int]] = Field(default=None)


class ObjectPermission(BaseModel):
    """Полномочия на объект"""

    pass


class WioObject(BaseModel):
    """Объект класса"""

    Id: uuid.UUID = Field(description="Идентификатор объекта")
    Name: str = Field(min_length=1, max_length=450, description="Название объекта")
    Description: Optional[str] = Field(
        default=None, max_length=500, description="Описание объекта"
    )
    Entity: Optional[WioEntity] = Field(default=None)
    Attributes: Optional[Dict[str, Any]] = Field(
        default=None, description="Список атрибутов с их значениями"
    )
    ModelLinks: Optional[List[ElementLinkItem]] = Field(
        default=None, description="Список ссылок на 3D моделях"
    )
    CreationDate: Optional[datetime.datetime] = Field(
        default=None, description="Дата и время создания объекта"
    )
    ModificationDate: Optional[datetime.datetime] = Field(
        default=None, description="Дата и время модификации объекта"
    )
    Owner: Optional[BaseItem_Of_Int32] = Field(default=None)
    EffectivePermissions: Optional[ObjectPermission] = Field(default=None)
    IsTemplate: Optional[bool] = Field(
        default=None, description="Является ли объект шаблоном"
    )
    HostObjectId: Optional[uuid.UUID] = Field(
        default=None, description="Идентификатор родительского объекта (для коллекций)"
    )
    Icon: Optional[str] = Field(default=None)
    Version: int
    VersionTimestamp: datetime.datetime
    IsActualVersion: bool


class CollectionItem(BaseModel):
    """Элемент коллекции"""

    Id: uuid.UUID = Field(description="Идентификатор объекта")
    Name: str = Field(min_length=1, max_length=450, description="Название объекта")
    Description: Optional[str] = Field(
        default=None, max_length=500, description="Описание объекта"
    )
    Object: Optional[WioObject] = Field(default=None)


class Content(BaseModel):
    """Модель Content"""

    Id: uuid.UUID
    Name: Optional[str] = Field(default=None)
    MediaType: Optional[str] = Field(default=None)
    Extension: Optional[str] = Field(default=None)
    Hash: Optional[str] = Field(default=None)
    Version: int
    Size: int
    Timestamp: datetime.datetime


class ContentValue(BaseModel):
    """Бинарный контент"""

    Id: uuid.UUID = Field(description="Идентификатор объекта")
    Name: str = Field(min_length=1, max_length=450, description="Название объекта")
    Description: Optional[str] = Field(
        default=None, max_length=500, description="Описание объекта"
    )
    MediaType: Optional[str] = Field(default=None, description="Тип содержимого")
    Extension: Optional[str] = Field(default=None, description="Расширение файла")
    Hash: Optional[str] = Field(default=None, description="Хэш соджержимого")
    Version: Optional[int] = Field(default=None, description="Версия содержимого")
    Size: Optional[int] = Field(default=None, description="Размер содержимого")
    TempToken: Optional[uuid.UUID] = Field(
        default=None,
        description="Токен используется для загрузки контента через временные файлы",
    )


class Culture(BaseModel):
    """Represents culture model."""

    Name: Optional[str] = Field(default=None, description="Get culture name.")
    NativeName: Optional[str] = Field(
        default=None, description="Get culture native name."
    )


class DomainSortingOptions(BaseModel):
    """Модель DomainSortingOptions"""

    SortBy: uuid.UUID = Field(description="AttributeId")
    Desc: Optional[bool] = Field(default=None)


class DataOptions(BaseModel):
    """Модель DataOptions"""

    CommandTimeout: int
    DomainSorting: Optional[DomainSortingOptions] = Field(default=None)


class ElementLinksContainer(BaseModel):
    """Модель ElementLinksContainer"""

    Id: int = Field(description="Идентификатор объекта")
    Name: str = Field(min_length=1, max_length=450, description="Название объекта")
    Description: Optional[str] = Field(
        default=None, max_length=450, description="Описание объекта"
    )
    Links: Optional[List[BaseItemNg_Of_Guid]] = Field(default=None)


class ElementNode(BaseModel):
    """Представляет элемент дерева элементов p3db."""

    Id: int = Field(description="Получает и задаёт идентификатор элемента.")
    Name: Optional[str] = Field(
        default=None, description="Получает и задаёт название элемента."
    )
    HasChildren: bool = Field(description="Получает и задаёт признак наличия потомков.")
    Mapped: bool = Field(
        description="Получает и задаёт признак наличия маппинга классов."
    )
    Children: Optional[List[ElementNode]] = Field(default=None)


class FileStorageOptions(BaseModel):
    """Модель FileStorageOptions"""

    PanoPath: Optional[str] = Field(
        default=None,
        description="Папка для кеширования файлов распакованного пакета панорам.",
    )
    TempPath: Optional[str] = Field(
        default=None, description="Папка для временных файлов."
    )
    UploadPath: Optional[str] = Field(
        default=None,
        description="Папка для хранения файлов, которые пользователь загружает из браузера.",
    )


class Globalization(BaseModel):
    """Represents globalization model."""

    DefaultCulture: Optional[Culture] = Field(default=None)
    SupportedCultures: Optional[List[Culture]] = Field(
        default=None, description="Get supported cultures."
    )


class IGuidNode(BaseModel):
    """Модель IGuidNode"""

    Id: Optional[uuid.UUID] = Field(default=None)
    Name: Optional[str] = Field(default=None)
    Icon: Optional[str] = Field(default=None)


class Icon(BaseModel):
    """Represents Icon model."""

    Id: Optional[str] = Field(default=None)
    Name: Optional[str] = Field(default=None)


class LicensingOptions(BaseModel):
    """Модель LicensingOptions"""

    Server: Optional[str] = Field(default=None)
    Client: Optional[str] = Field(default=None)


class LongRunningTaskInfo(BaseModel):
    """Информация о созданной долгоиграющей задаче"""

    Id: uuid.UUID


class ModelFileNg(BaseModel):
    """Модель ModelFileNg"""

    Id: int = Field(description="Идентификатор объекта")
    Name: str = Field(min_length=1, max_length=450, description="Название объекта")
    Description: Optional[str] = Field(
        default=None, max_length=450, description="Описание объекта"
    )
    Inherited: bool
    ModelId: int
    Timestamp: datetime.datetime
    ContentId: uuid.UUID
    ContentSize: int
    ContentVersion: int


class ModelsAddRequest(BaseModel):
    """Модель ModelsAddRequest"""

    ModelIds: Optional[List[int]] = Field(default=None)
    ModelFileIds: Optional[List[int]] = Field(default=None)


class NodeType(BaseModel):
    """Модель NodeType"""

    pass


class NodeDto(BaseModel):
    """Модель NodeDto"""

    Id: uuid.UUID = Field(description="Идентификатор объекта")
    Name: str = Field(min_length=1, max_length=450, description="Название объекта")
    Description: Optional[str] = Field(
        default=None, max_length=500, description="Описание объекта"
    )
    Children: Optional[List[IGuidNode]] = Field(default=None)
    HasChildren: Optional[bool] = Field(default=None)
    Level: Optional[int] = Field(default=None)
    Icon: Optional[str] = Field(default=None)
    Type: Optional[NodeType] = Field(default=None)
    EffectivePermissions: Optional[ObjectPermission] = Field(default=None)


class NodeNg(BaseModel):
    """Модель NodeNg"""

    Id: int = Field(description="Идентификатор объекта")
    Name: str = Field(min_length=1, max_length=450, description="Название объекта")
    Description: Optional[str] = Field(
        default=None, max_length=450, description="Описание объекта"
    )
    Children: Optional[List[NodeNg]] = Field(default=None)
    HasChildren: Optional[bool] = Field(default=None)
    Level: Optional[int] = Field(default=None)
    Icon: Optional[str] = Field(default=None)
    Type: Optional[NodeType] = Field(default=None)


class ObjectPermissionState(BaseModel):
    """Модель ObjectPermissionState"""

    pass


class ObjectPermissionInfo(BaseModel):
    """Данные о полномочии"""

    Id: ObjectPermission
    Name: str = Field(min_length=1, max_length=450, description="Название объекта")
    Description: Optional[str] = Field(
        default=None, max_length=500, description="Описание объекта"
    )
    State: ObjectPermissionState
    InheritedState: Optional[ObjectPermissionState] = Field(default=None)
    IsInherited: bool = Field(description="Унаследовано ли это полномочме")


class PrincipalType(BaseModel):
    """Модель PrincipalType"""

    pass


class Principal(BaseModel):
    """Субъект доступа"""

    Id: int = Field(description="Идентификатор объекта")
    Name: str = Field(min_length=1, max_length=450, description="Название объекта")
    Description: Optional[str] = Field(
        default=None, max_length=500, description="Описание объекта"
    )
    Type: PrincipalType


class PrincipalPermissionInfo_Of_ObjectPermissionInfo(BaseModel):
    """Информация о полномочиях объекта"""

    Principal: Optional[Principal] = Field(default=None)
    Permissions: Optional[List[ObjectPermissionInfo]] = Field(
        default=None, description="Установленные полномочия"
    )
    IsInherited: bool = Field(description="Является ли данный principal унаследованным")


class ObjectSecurityInfo(BaseModel):
    """Модель ObjectSecurityInfo"""

    PrincipalObjectPermissions: Optional[
        List[PrincipalPermissionInfo_Of_ObjectPermissionInfo]
    ] = Field(default=None)
    EffectivePermissions: Optional[
        List[PrincipalPermissionInfo_Of_ObjectPermissionInfo]
    ] = Field(default=None)
    DefaultPermissions: Optional[List[ObjectPermissionInfo]] = Field(default=None)


class Permission(BaseModel):
    """Модель Permission"""

    Name: Optional[str] = Field(default=None)
    Description: Optional[str] = Field(default=None)


class PermissionOperation(BaseModel):
    """Модель PermissionOperation"""

    pass


class PermissionManagementOperation(BaseModel):
    """Модель PermissionManagementOperation"""

    Operation: PermissionOperation
    PrincipalPermissionInfo: Optional[
        PrincipalPermissionInfo_Of_ObjectPermissionInfo
    ] = Field(default=None)


class PreviewOptions(BaseModel):
    """Represents preview options."""

    DefaultAutoLimit: Optional[int] = Field(default=None)


class ProblemDetails(BaseModel):
    """Модель ProblemDetails"""

    type: Optional[str] = Field(default=None)
    title: Optional[str] = Field(default=None)
    status: Optional[int] = Field(default=None)
    detail: Optional[str] = Field(default=None)
    instance: Optional[str] = Field(default=None)


class QueryShapingResult_Of_CollectionItem(BaseModel):
    """Модель QueryShapingResult_Of_CollectionItem"""

    Result: Optional[List[CollectionItem]] = Field(default=None)
    Total: int


class QueryShapingResult_Of_Guid(BaseModel):
    """Модель QueryShapingResult_Of_Guid"""

    Result: Optional[List[uuid.UUID]] = Field(default=None)
    Total: int


class SearchResultObject(BaseModel):
    """Модель SearchResultObject"""

    Object: Optional[WioObject] = Field(default=None)
    Parent: Optional[WioObject] = Field(default=None)


class QueryShapingResult_Of_SearchResultObject(BaseModel):
    """Модель QueryShapingResult_Of_SearchResultObject"""

    Result: Optional[List[SearchResultObject]] = Field(default=None)
    Total: int


class QueryShapingResult_Of_WioObject(BaseModel):
    """Модель QueryShapingResult_Of_WioObject"""

    Result: Optional[List[WioObject]] = Field(default=None)
    Total: int


class ReportConstraintOptions(BaseModel):
    """Модель ReportConstraintOptions"""

    pass


class SearchLogicType(BaseModel):
    """Модель SearchLogicType"""

    pass


class SearchConditionType(BaseModel):
    """Тип условия"""

    pass


class SearchOperatorType(BaseModel):
    """Модель SearchOperatorType"""

    pass


class SearchDirectionType(BaseModel):
    """Модель SearchDirectionType"""

    pass


class SearchCondition(BaseModel):
    """Модель SearchCondition"""

    Type: SearchConditionType
    Value: Optional[str] = Field(default=None)
    Direction: Optional[SearchDirectionType] = Field(default=None)
    Attribute: Optional[uuid.UUID] = Field(default=None)
    Operator: Optional[SearchOperatorType] = Field(default=None)
    Logic: Optional[SearchLogicType] = Field(default=None)
    Group: Optional[str] = Field(default=None)
    Contextual: Optional[bool] = Field(default=None)
    Conditions: Optional[List[SearchCondition]] = Field(default=None)


class SearchFilter(BaseModel):
    """Модель SearchFilter"""

    Type: SearchConditionType
    Value: Optional[str] = Field(default=None)


class SearchRelationshipType(BaseModel):
    """Тип связи подчиненного набора данных"""

    pass


class SearchRelationship(BaseModel):
    """Модель SearchRelationship"""

    Type: SearchRelationshipType
    Direction: Optional[SearchDirectionType] = Field(default=None)
    Attribute: Optional[uuid.UUID] = Field(default=None)


class SearchQueryMode(BaseModel):
    """Тип связи подчиненного набора данных"""

    pass


class SearchQuery(BaseModel):
    """Модель SearchQuery"""

    Filters: Optional[List[SearchFilter]] = Field(default=None)
    Conditions: Optional[List[SearchCondition]] = Field(default=None)
    Relationship: Optional[SearchRelationship] = Field(default=None)
    Queries: Optional[List[SearchQuery]] = Field(default=None)
    Mode: Optional[SearchQueryMode] = Field(default=None)


class ShapingResult_Of_Attribute(BaseModel):
    """Модель ShapingResult_Of_Attribute"""

    Result: Optional[List[Attribute]] = Field(default=None)
    Total: int


class WioAttribute(BaseModel):
    """Модель WioAttribute"""

    Id: uuid.UUID = Field(description="Идентификатор объекта")
    Name: str = Field(min_length=1, max_length=450, description="Название объекта")
    Description: Optional[str] = Field(
        default=None, max_length=500, description="Описание объекта"
    )
    Locked: Optional[LockType] = Field(default=None)
    Type: WioAttributeType
    Constraints: Optional[List[Constraint]] = Field(
        default=None, description="Список ограничений"
    )
    Unit: Optional[BaseItem_Of_Int64] = Field(default=None)
    Group: Optional[BaseItem_Of_Int64] = Field(default=None)


class ShapingResult_Of_WioAttribute(BaseModel):
    """Модель ShapingResult_Of_WioAttribute"""

    Result: Optional[List[WioAttribute]] = Field(default=None)
    Total: int


class UIComponentsOptions(BaseModel):
    """Represents UI components options."""

    UseDxGrid: bool = Field(description="Get or set use DxGrid flag.")


class UpdateCultureCommand(BaseModel):
    """Represents set culture model."""

    Name: Optional[str] = Field(default=None, description="Get or set culture name.")


class UserChangePasswordCommand(BaseModel):
    """Represents user change password command."""

    CurrentPassword: Optional[str] = Field(
        default=None, description="Current password."
    )
    Password: Optional[str] = Field(default=None, description="New password.")
    ConfirmPassword: Optional[str] = Field(
        default=None, description="New password confirm."
    )


class WioAttributeTypeInfo(BaseModel):
    """Информация о типе атрибута"""

    Type: WioAttributeType
    Caption: Optional[str] = Field(default=None, description="Название типа атрибута")
    SupportsUnits: Optional[bool] = Field(
        default=None, description="Поддерживает ли атрибут единицы измерения"
    )
    IsScalar: Optional[bool] = Field(default=None)
    Constraints: Optional[Dict[str, Any]] = Field(
        default=None, description="Настройки кардинальности ограничений"
    )


class WioUserCredentials(BaseModel):
    """Модель WioUserCredentials"""

    CurrentPassword: str = Field(min_length=1)
    Password: str = Field(min_length=5, max_length=100)
    ConfirmPassword: Optional[str] = Field(default=None)
    Lockout: Optional[bool] = Field(default=None)


class WioFullUser(BaseModel):
    """Модель WioFullUser"""

    Id: int = Field(description="Идентификатор объекта")
    Name: str = Field(min_length=1, max_length=450, description="Название объекта")
    Description: Optional[str] = Field(
        default=None, max_length=500, description="Описание объекта"
    )
    LockoutDate: Optional[datetime.datetime] = Field(default=None)
    LastActivity: Optional[datetime.datetime] = Field(default=None)
    IsExternal: bool
    Attributes: Optional[Dict[str, Any]] = Field(default=None)
    Credentials: WioUserCredentials


class WioObjectNode(BaseModel):
    """Модель WioObjectNode"""

    Id: uuid.UUID = Field(description="Идентификатор объекта")
    Name: str = Field(min_length=1, max_length=450, description="Название объекта")
    Description: Optional[str] = Field(
        default=None, max_length=500, description="Описание объекта"
    )
    Children: Optional[List[WioObjectNode]] = Field(default=None)
    EffectivePermissions: Optional[ObjectPermission] = Field(default=None)
    HasChildren: Optional[bool] = Field(default=None)
    Level: Optional[int] = Field(default=None)
    Icon: Optional[str] = Field(default=None)
    Entity: WioEntity
    Version: int
    VersionTimestamp: datetime.datetime
    IsActualVersion: bool


class WioObjectPathInfo(BaseModel):
    """Модель WioObjectPathInfo"""

    CanShowInMainTree: bool
    AncestorsOrSelf: Optional[List[WioObjectNode]] = Field(default=None)


class WioRole(BaseModel):
    """Роль в Inter Operation for Web"""

    Id: int = Field(description="Идентификатор объекта")
    Description: Optional[str] = Field(
        default=None, max_length=500, description="Описание объекта"
    )
    Name: str = Field(min_length=3, max_length=100, pattern=r"^[а-яА-Я\\w\\-\\.]+$")


class WioUser(BaseModel):
    """Пользователь"""

    Id: int = Field(description="Идентификатор объекта")
    Name: str = Field(min_length=1, max_length=450, description="Название объекта")
    Description: Optional[str] = Field(
        default=None, max_length=500, description="Описание объекта"
    )
    LockoutDate: Optional[datetime.datetime] = Field(default=None)
    LastActivity: Optional[datetime.datetime] = Field(default=None)
    IsExternal: bool
    Attributes: Optional[Dict[str, Any]] = Field(default=None)


class WopiOptions(BaseModel):
    """Модель WopiOptions"""

    Server: Optional[str] = Field(default=None)
    InternalSite: Optional[str] = Field(default=None)
    ForceNativePdf: bool
