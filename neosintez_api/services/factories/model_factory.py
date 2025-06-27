"""
Фабрика для динамического создания Pydantic-моделей на основе пользовательских данных.
"""

from typing import TYPE_CHECKING, Any, Dict, List, NamedTuple, Optional

from pydantic import BaseModel, ConfigDict, Field, create_model

from neosintez_api.utils import generate_field_name, neosintez_type_to_python_type


if TYPE_CHECKING:
    from neosintez_api.core.client import NeosintezClient


class ObjectBlueprint(NamedTuple):
    """
    Контейнер, описывающий Pydantic-модель объекта и его первоначальное состояние.
    Эта структура отражает плоское представление объекта, удобное для работы в Python.
    """

    model_class: type[BaseModel]
    model_instance: BaseModel
    attributes_meta: Dict[str, Any]
    class_id: str
    class_name: str


class DynamicModelFactory:
    """
    "Строитель", который разбирает пользовательские данные ОДНОГО объекта
    и создает единую, плоскую Pydantic модель для его представления.
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

    async def create_from_user_data(self, user_data: Dict[str, Any], client: "NeosintezClient") -> ObjectBlueprint:
        """Основной метод фабрики."""
        # 1. Извлекаем стандартную информацию
        original_class_key, class_name = self._find_and_extract(user_data, self.class_name_aliases)
        if not class_name:
            raise ValueError(f"Не удалось найти имя класса по алиасам: {self.class_name_aliases}")

        original_name_key, object_name = self._find_and_extract(user_data, self.name_aliases)
        if not object_name:
            raise ValueError(f"Не удалось найти имя объекта по алиасам: {self.name_aliases}")

        print(f"Найден класс: '{class_name}', Имя объекта: '{object_name}'")

        # 2. Отделяем данные для атрибутов
        attribute_data = {k: v for k, v in user_data.items() if k not in (original_class_key, original_name_key)}
        print(f"Найдены пользовательские атрибуты: {list(attribute_data.keys())}")

        # 3. Получаем метаданные из API
        print("Запрашиваем все классы с атрибутами...")
        all_classes_meta = await client.classes.get(exclude_attributes=False)

        target_class_meta = next(
            (c for c in all_classes_meta if c.get("Name", "").lower() == class_name.lower()),
            None,
        )
        if not target_class_meta:
            raise ValueError(f"Класс '{class_name}' не найден в API.")

        class_id = target_class_meta.get("Id")
        if not class_id:
            raise ValueError(f"Не удалось получить ID для класса '{class_name}'")

        api_attributes = target_class_meta.get("Attributes", {})
        if not api_attributes:
            print(f"Предупреждение: для класса '{class_name}' не найдено атрибутов в API.")

        attr_lookup = {
            attr_data.get("Name"): attr_data for _, attr_data in api_attributes.items() if isinstance(attr_data, dict)
        }

        # 4. Определяем поля для динамических атрибутов
        dynamic_fields = {}
        for attr_name in attribute_data:
            meta = attr_lookup.get(attr_name)
            if not meta:
                print(f"Предупреждение: Атрибут '{attr_name}' не найден в метаданных класса '{class_name}'")
                continue

            field_name = generate_field_name(attr_name)
            python_type = neosintez_type_to_python_type(meta.get("Type"))
            dynamic_fields[field_name] = (python_type, Field(..., alias=attr_name))

        # 5. Определяем статические поля, которые есть у любого объекта
        static_fields = {
            "id": (Optional[str], Field(None, description="ID объекта в Неосинтезе")),
            "class_id": (
                Optional[str],
                Field(None, description="ID класса объекта"),
            ),
            "parent_id": (
                Optional[str],
                Field(None, description="ID родительского объекта"),
            ),
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
            attributes_meta=api_attributes,
            class_id=class_id,
            class_name=class_name,
        )
