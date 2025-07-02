"""
Фабрика для динамического создания Pydantic-моделей на основе пользовательских данных.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, create_model

from neosintez_api.services.object_search_service import ObjectSearchService
from neosintez_api.utils import generate_field_name, neosintez_type_to_python_type

from ..resolvers import AttributeResolver


if TYPE_CHECKING:
    from neosintez_api.core.client import NeosintezClient


@dataclass
class ObjectBlueprint:
    """
    Контейнер, описывающий Pydantic-модель объекта и его метаданные.

    Эта структура содержит все необходимое для работы с объектом:
    - Системное представление (готовая Pydantic-модель для API).
    - Пользовательское представление (человекочитаемые значения).
    - Метаданные, использованные для создания.
    - Исходные данные и ошибки.
    """

    model_class: type[BaseModel]
    model_instance: BaseModel
    attributes_meta: Dict[str, Any]
    class_id: str
    class_name: str
    user_data: Dict[str, Any]
    display_representation: Dict[str, Any]
    errors: List[str] = field(default_factory=list)


def _create_pydantic_model(class_name: str, attributes_meta: Dict[str, Any]) -> type[BaseModel]:
    """
    Создает Pydantic-модель на основе метаданных класса.
    Используется обеими фабриками.
    """
    # 4. Определяем поля для динамических атрибутов
    dynamic_fields = {}
    for attr_name, meta in attributes_meta.items():
        field_name = generate_field_name(attr_name)
        python_type = neosintez_type_to_python_type(meta.Type if hasattr(meta, "Type") else None)
        # Для чтения делаем все поля опциональными (None)
        dynamic_fields[field_name] = (
            Optional[python_type],
            Field(None, alias=attr_name),
        )

    # 5. Определяем статические поля, которые есть у любого объекта
    static_fields = {
        "id": (Optional[str], Field(None, description="ID объекта в Неосинтезе")),
        "class_id": (Optional[str], Field(None, description="ID класса объекта")),
        "parent_id": (Optional[str], Field(None, description="ID родительского объекта")),
        "name": (str, Field(..., description="Имя объекта")),
    }

    # 6. Создаем единую модель с "чистыми" именами полей и поддержкой алиасов
    sanitized_class_name = "".join(filter(str.isalnum, class_name))
    UnifiedObjectModel = create_model(
        f"{sanitized_class_name}ObjectModel",
        **static_fields,
        **dynamic_fields,
        __config__=ConfigDict(populate_by_name=True),
    )
    return UnifiedObjectModel


class DynamicModelFactory:
    """
    "Строитель", который разбирает пользовательские данные ОДНОГО объекта
    и создает единую, плоскую Pydantic модель для его представления.
    """

    def __init__(
        self,
        client: "NeosintezClient",
        name_aliases: List[str],
        class_name_aliases: List[str],
    ):
        self.client = client
        self.name_aliases = [alias.lower() for alias in name_aliases]
        self.class_name_aliases = [alias.lower() for alias in class_name_aliases]
        self.search_service = ObjectSearchService(self.client)
        self.resolver = AttributeResolver(self.client)

    def _find_and_extract(self, data: Dict[str, Any], aliases: List[str]) -> (str, Any):
        """Находит ключ по одному из алиасов, возвращает его и значение."""
        for key, value in data.items():
            if key.lower() in aliases:
                return key, value
        return None, None

    async def create_from_user_data(
        self,
        user_data: Dict[str, Any],
        class_name: str,
        class_id: str,
        attributes_meta: Dict[str, Any],
    ) -> ObjectBlueprint:
        """Основной метод фабрики."""
        # 1. Извлекаем стандартную информацию
        original_name_key, object_name = self._find_and_extract(user_data, self.name_aliases)
        if not object_name:
            raise ValueError(f"Не удалось найти имя объекта по алиасам: {self.name_aliases}")

        # 2. Отделяем данные для атрибутов и создаем чистовое представление
        attribute_data = {
            k: v
            for k, v in user_data.items()
            if k.lower() not in self.name_aliases and k.lower() not in self.class_name_aliases
        }
        display_representation = attribute_data.copy()
        if original_name_key:
            display_representation[original_name_key] = object_name

        # 3. Готовим справочник метаданных по имени атрибута
        attr_lookup = {attr_data.Name: attr_data for attr_data in attributes_meta.values()}

        # Обрабатываем ссылочные атрибуты
        for attr_name, attr_value in attribute_data.items():
            meta = attr_lookup.get(attr_name)
            if meta and meta.Type == 8 and isinstance(attr_value, str):  # 8 - Ссылка на объект
                try:
                    resolved_obj = await self.resolver.resolve_link_attribute_as_object(
                        attr_meta=meta, attr_value=attr_value
                    )
                    attribute_data[attr_name] = resolved_obj
                except ValueError as e:
                    # Можно здесь собирать ошибки, а не падать сразу
                    raise e

        # 4. Создаем Pydantic модель с помощью общей функции
        UnifiedObjectModel = _create_pydantic_model(class_name, attr_lookup)
        print(f"Создана единая Pydantic-модель: '{UnifiedObjectModel.__name__}'")

        # 7. Готовим данные для создания экземпляра модели.
        # Используем исходные данные атрибутов (с "грязными" именами), так как они являются алиасами.
        validation_data = attribute_data.copy()
        validation_data["name"] = object_name  # Добавляем имя объекта

        # 8. Создаем экземпляр через model_validate, который корректно работает с алиасами
        model_instance = UnifiedObjectModel.model_validate(validation_data)

        # 9. Возвращаем чертеж
        return ObjectBlueprint(
            model_class=UnifiedObjectModel,
            model_instance=model_instance,
            attributes_meta=attributes_meta,
            class_id=class_id,
            class_name=class_name,
            user_data=user_data,
            display_representation=display_representation,
            errors=[],  # Пока оставляем пустым
        )
