"""
Фабрика для динамического создания Pydantic-моделей на основе пользовательских данных.
"""

from typing import Any, Dict, List, NamedTuple

from pydantic import BaseModel, ConfigDict, Field, create_model

from neosintez_api.client import NeosintezClient
from neosintez_api.utils import generate_field_name, neosintez_type_to_python_type


class ObjectBlueprint(NamedTuple):
    """Контейнер для разобранных данных, готовых к созданию объекта."""

    class_name: str
    object_name: str
    attributes_model: BaseModel


class DynamicModelFactory:
    """
    "Строитель", который разбирает пользовательские данные ОДНОГО объекта
    и создает динамическую Pydantic модель для его атрибутов.
    """

    def __init__(self, name_aliases: List[str], class_name_aliases: List[str]):
        self.name_aliases = [alias.lower() for alias in name_aliases]
        self.class_name_aliases = [alias.lower() for alias in class_name_aliases]

    def _find_and_extract(self, data: Dict[str, Any], aliases: List[str]) -> (str, Any):
        """Находит ключ по одному из алиасов, возвращает его и значение."""
        for key, value in data.items():
            if key.lower() in aliases:
                return key, value
        return None, None

    async def create_from_user_data(self, user_data: Dict[str, Any], client: NeosintezClient) -> ObjectBlueprint:
        """Основной метод фабрики."""
        original_class_key, class_name = self._find_and_extract(user_data, self.class_name_aliases)
        if not class_name:
            raise ValueError(f"Не удалось найти имя класса по алиасам: {self.class_name_aliases}")

        original_name_key, object_name = self._find_and_extract(user_data, self.name_aliases)
        if not object_name:
            raise ValueError(f"Не удалось найти имя объекта по алиасам: {self.name_aliases}")

        print(f"Найден класс: '{class_name}', Имя объекта: '{object_name}'")

        attribute_data = {k: v for k, v in user_data.items() if k != original_class_key and k != original_name_key}
        print(f"Найдены пользовательские атрибуты: {list(attribute_data.keys())}")

        print("Запрашиваем все классы с атрибутами...")
        all_classes_meta = await client.classes.get(exclude_attributes=False)

        target_class_meta = next(
            (c for c in all_classes_meta if c.get("Name", "").lower() == class_name.lower()),
            None,
        )
        if not target_class_meta:
            raise ValueError(f"Класс '{class_name}' не найден в API.")

        api_attributes = target_class_meta.get("Attributes", {})
        attr_lookup = {
            attr_data.get("Name"): attr_data for _, attr_data in api_attributes.items() if isinstance(attr_data, dict)
        }

        model_fields_meta = {}
        for attr_name in attribute_data:
            meta = attr_lookup.get(attr_name)
            if not meta:
                print(f"Предупреждение: Атрибут '{attr_name}' не найден в метаданных класса '{class_name}'")
                continue

            field_name = generate_field_name(attr_name)
            python_type = neosintez_type_to_python_type(meta.get("Type"))
            model_fields_meta[attr_name] = (field_name, python_type)

        sanitized_class_name = "".join(filter(str.isalnum, class_name))
        model_name = f"{sanitized_class_name}AttributesModel"

        if not model_fields_meta:
            AttributesModel = create_model(model_name)
            attributes_model_instance = AttributesModel()
        else:
            fields = {meta[0]: (meta[1], Field(..., alias=alias)) for alias, meta in model_fields_meta.items()}
            AttributesModel = create_model(model_name, **fields, __config__=ConfigDict(validate_by_alias=True))
            attributes_model_instance = AttributesModel.model_validate(attribute_data)

        print(f"Создана динамическая модель для атрибутов: '{AttributesModel.__name__}'")

        return ObjectBlueprint(
            class_name=class_name,
            object_name=object_name,
            attributes_model=attributes_model_instance,
        )
