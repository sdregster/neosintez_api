"""
Фабрика для создания Pydantic-моделей из существующих объектов в Неосинтезе.
"""

from typing import TYPE_CHECKING, Any, Dict

from neosintez_api.models import Attribute, NeoObject
from neosintez_api.services.class_service import ClassService
from neosintez_api.services.factories.model_factory import (
    DynamicModelFactory,
    ObjectBlueprint,
)


if TYPE_CHECKING:
    from neosintez_api.core.client import NeosintezClient


class ObjectToModelFactory:
    """
    Фабрика для создания Pydantic-моделей из существующих объектов в Неосинтезе.

    Поддерживает два основных сценария:
    - создание модели по ID объекта с дополнительным запросом в API;
    - создание модели из уже полученного NeoObject без повторного запроса.
    """

    def __init__(self, client: "NeosintezClient") -> None:
        """
        Инициализирует фабрику.

        Args:
            client: Клиент для работы с API Неосинтеза.
        """
        self.client = client
        self.class_service = ClassService(client)
        # Внутренняя фабрика для создания самих Pydantic моделей.
        # Алиасы не нужны, так как мы работаем с данными из API, а не от пользователя.
        self._model_factory = DynamicModelFactory(
            client=self.client,
            class_service=self.class_service,
            name_aliases=[],
            class_name_aliases=[],
        )

    async def create_from_object_id(self, object_id: str) -> ObjectBlueprint:
        """
        Создает Pydantic-модель из существующего объекта по его ID.

        Args:
            object_id: Идентификатор объекта в Неосинтезе.

        Returns:
            ObjectBlueprint: Структура с моделью и её экземпляром.

        Raises:
            NeosintezAPIError: Если объект не найден или произошла ошибка API.
            ValueError: Если класс объекта не найден.
        """
        # 1. Получаем сырые данные объекта
        object_data = await self._get_object_data(object_id)

        # 2. Извлекаем ID класса из данных объекта
        entity_info = object_data.get("Entity")
        if entity_info and isinstance(entity_info, dict):
            class_id = entity_info.get("Id")
        else:
            class_id = object_data.get("classId")  # Резервный вариант

        if not class_id:
            raise ValueError(f"Не удалось извлечь ID класса из данных объекта {object_id}")

        # 3. Используем ClassService для надежного получения метаданных
        class_info = await self.class_service.get_by_id(class_id)
        if not class_info:
            raise ValueError(f"Класс с ID {class_id} не найден.")

        class_attributes = await self.class_service.get_attributes(class_id)
        attributes_meta = {attr.Name: attr for attr in class_attributes}

        # 4. Создаем Pydantic-модель через внутреннюю фабрику (с кэшем)
        model_class = self._model_factory._get_or_create_pydantic_model(class_info.Name, attributes_meta)

        # 5. Заполняем модель данными объекта
        model_instance = self._populate_model_from_object(model_class, object_data, attributes_meta, class_id)

        # 6. Возвращаем blueprint
        return ObjectBlueprint(
            model_class=model_class,
            model_instance=model_instance,
            attributes_meta=attributes_meta,
            class_id=class_id,
            class_name=class_info.Name,
            user_data=object_data,  # В качестве user_data используем сырые данные
            display_representation=object_data.get("Attributes", {}),
        )

    async def create_from_neo_object(self, neo_object: NeoObject) -> ObjectBlueprint:
        """
        Создает Pydantic-модель из уже полученного объекта NeoObject.

        В этом сценарии повторный запрос к API для чтения объекта не выполняется,
        используются данные, пришедшие в результате поиска или другого вызова,
        а метаданные класса берутся из кеширующего ClassService.

        Args:
            neo_object: Экземпляр NeoObject, полученный из API.

        Returns:
            ObjectBlueprint: Структура с моделью и её экземпляром.

        Raises:
            ValueError: Если не удалось получить метаданные класса.
        """
        class_id = str(neo_object.EntityId)

        # 1. Получаем информацию о классе и его атрибуты (через кеширующий сервис).
        class_info = await self.class_service.get_by_id(class_id)
        if not class_info:
            raise ValueError(f"Класс с ID {class_id} не найден.")

        class_attributes = await self.class_service.get_attributes(class_id)
        attributes_meta = {attr.Name: attr for attr in class_attributes}

        # 2. Создаем или берем из кэша Pydantic-модель для этого класса.
        model_class = self._model_factory._get_or_create_pydantic_model(class_info.Name, attributes_meta)

        # 3. Собираем структуру object_data, совместимую с _populate_model_from_object.
        object_data: Dict[str, Any] = {
            "Id": str(neo_object.Id),
            "Name": neo_object.Name,
            "Entity": {"Id": class_id},
            # В результатах поиска атрибуты обычно возвращаются как словарь по ID атрибута.
            "Attributes": neo_object.Attributes or {},
        }

        # Информация о родителе в NeoObject отсутствует, поэтому оставляем Parent пустым.
        # Это не мешает заполнению модели, так как _populate_model_from_object
        # корректно обрабатывает отсутствие родителя.

        # 4. Создаем экземпляр модели и заполняем его данными.
        model_instance = self._populate_model_from_object(model_class, object_data, attributes_meta, class_id)

        # 5. Возвращаем blueprint.
        return ObjectBlueprint(
            model_class=model_class,
            model_instance=model_instance,
            attributes_meta=attributes_meta,
            class_id=class_id,
            class_name=class_info.Name,
            user_data=object_data,
            display_representation=object_data.get("Attributes", {}),
        )

    async def _get_object_data(self, object_id: str) -> Dict[str, Any]:
        """
        Получает сырые данные объекта по идентификатору.

        Args:
            object_id: Идентификатор объекта.

        Returns:
            Dict[str, Any]: Сырые данные объекта, возвращённые API.

        Raises:
            NeosintezAPIError: В случае ошибки при запросе к API.
        """
        endpoint = f"api/objects/{object_id}"
        raw_data = await self.client._request("GET", endpoint)
        return raw_data

    def _populate_model_from_object(
        self,
        model_class: type,
        object_data: Dict[str, Any],
        attributes_meta: Dict[str, Attribute],
        class_id: str,
    ) -> Any:
        """
        Заполняет модель данными из объекта.

        Args:
            model_class: Класс Pydantic-модели, в которую нужно загрузить данные.
            object_data: Сырые данные объекта, полученные из API.
            attributes_meta: Метаданные атрибутов класса (по имени атрибута).
            class_id: Идентификатор класса объекта.

        Returns:
            Any: Экземпляр модели с заполненными данными.
        """
        validation_data: Dict[str, Any] = {}

        object_id = object_data.get("Id")
        validation_data["name"] = object_data.get("Name")
        validation_data["class_id"] = class_id
        parent_id = object_data.get("Parent", {}).get("Id") if isinstance(object_data.get("Parent"), dict) else None

        object_attributes = object_data.get("Attributes", {})
        attr_id_to_meta = {str(attr.Id): attr for attr in attributes_meta.values()}

        for attr_id, attr_data in object_attributes.items():
            attr_meta = attr_id_to_meta.get(attr_id)
            if attr_meta:
                attr_value = attr_data.get("Value") if isinstance(attr_data, dict) else attr_data
                validation_data[attr_meta.Name] = attr_value

        # Создаем экземпляр модели
        instance = model_class.model_validate(validation_data)

        # Устанавливаем приватные атрибуты для NeosintezBaseModel
        from neosintez_api.models import NeosintezBaseModel

        if isinstance(instance, NeosintezBaseModel):
            instance._id = str(object_id) if object_id else None
            instance._class_id = class_id
            instance._parent_id = str(parent_id) if parent_id else None

        return instance
