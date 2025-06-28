"""
Фабрика для создания Pydantic-моделей из существующих объектов в Неосинтезе.
"""

from typing import TYPE_CHECKING, Any, Dict

from neosintez_api.exceptions import ApiError
from neosintez_api.models import Attribute
from neosintez_api.services.class_service import ClassService
from neosintez_api.services.factories.model_factory import (
    ObjectBlueprint,
    _create_pydantic_model,
)


if TYPE_CHECKING:
    from neosintez_api.core.client import NeosintezClient


class ObjectToModelFactory:
    """
    Фабрика для создания Pydantic-моделей из существующих объектов в Неосинтезе.

    Принимает ID объекта, получает его данные и метаданные класса,
    создает соответствующую Pydantic модель и заполняет её данными объекта.
    """

    def __init__(self, client: "NeosintezClient"):
        """
        Инициализация фабрики.

        Args:
            client: Клиент для работы с API Неосинтеза
        """
        self.client = client
        self.class_service = ClassService(client)

    async def create_from_object_id(self, object_id: str) -> ObjectBlueprint:
        """
        Создает Pydantic модель из существующего объекта по его ID.

        Args:
            object_id: ID объекта в Неосинтезе

        Returns:
            ObjectBlueprint: Структура с моделью и её экземпляром

        Raises:
            ApiError: Если объект не найден или произошла ошибка API
            ValueError: Если класс объекта не найден
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

        # 4. Создаем Pydantic модель
        model_class = _create_pydantic_model(class_info.Name, attributes_meta)

        # 5. Заполняем модель данными объекта
        model_instance = self._populate_model_from_object(model_class, object_data, attributes_meta, class_id)

        # 6. Возвращаем blueprint
        return ObjectBlueprint(
            model_class=model_class,
            model_instance=model_instance,
            attributes_meta=attributes_meta,
            class_id=class_id,
            class_name=class_info.Name,
        )

    async def _get_object_data(self, object_id: str) -> Dict[str, Any]:
        """
        Получает сырые данные объекта по ID.
        """
        try:
            endpoint = f"api/objects/{object_id}"
            raw_data = await self.client._request("GET", endpoint)
            return raw_data
        except Exception as e:
            raise ApiError(f"Ошибка получения объекта {object_id}: {e}")

    def _populate_model_from_object(
        self,
        model_class: type,
        object_data: Dict[str, Any],
        attributes_meta: Dict[str, Attribute],
        class_id: str,
    ) -> any:
        """
        Заполняет модель данными из объекта.
        """
        validation_data = {}

        validation_data["id"] = object_data.get("Id")
        validation_data["name"] = object_data.get("Name")
        validation_data["class_id"] = class_id
        validation_data["parent_id"] = (
            object_data.get("Parent", {}).get("Id") if isinstance(object_data.get("Parent"), dict) else None
        )

        object_attributes = object_data.get("Attributes", {})
        attr_id_to_meta = {str(attr.Id): attr for attr in attributes_meta.values()}

        for attr_id, attr_data in object_attributes.items():
            attr_meta = attr_id_to_meta.get(attr_id)
            if attr_meta:
                attr_value = attr_data.get("Value") if isinstance(attr_data, dict) else attr_data
                validation_data[attr_meta.Name] = attr_value

        return model_class.model_validate(validation_data)
