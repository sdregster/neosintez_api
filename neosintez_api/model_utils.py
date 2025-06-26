"""
Утилиты для работы с Pydantic моделями в контексте Neosintez API.
"""

from typing import Any, Dict, List, Optional, Type, TypeVar

from pydantic import BaseModel, Field, create_model


T = TypeVar("T", bound=BaseModel)


def neosintez_model(cls=None, *, class_name=None):
    """
    Декоратор для Pydantic моделей, который добавляет метаданные для работы с API Неосинтеза.

    Args:
        cls: Класс модели
        class_name: Имя класса в Неосинтезе

    Returns:
        Type[BaseModel]: Декорированный класс модели
    """

    def wrap(cls):
        # Устанавливаем имя класса
        if class_name is not None:
            cls.__class_name__ = class_name
        elif not hasattr(cls, "__class_name__"):
            cls.__class_name__ = cls.__name__

        # Добавляем методы для работы с API

        # Метод для получения данных модели с алиасами
        def get_attribute_data(self) -> Dict[str, Any]:
            """
            Получает данные модели в формате, готовом для отправки в API Неосинтеза.

            Returns:
                Dict[str, Any]: Данные модели с алиасами в качестве ключей
            """
            return self.model_dump(by_alias=True)

        # Метод для получения маппинга полей модели на атрибуты Неосинтеза
        def get_field_to_attribute_mapping(self) -> Dict[str, str]:
            """
            Получает маппинг полей модели на атрибуты Неосинтеза.

            Returns:
                Dict[str, str]: Словарь {имя_поля: алиас}
            """
            result = {}
            for field_name, field_info in self.model_fields.items():
                alias = field_info.alias or field_name
                result[field_name] = alias
            return result

        # Метод для получения имени объекта из модели
        def get_object_name(self) -> str:
            """
            Получает имя объекта из модели.

            Returns:
                str: Имя объекта

            Raises:
                ValueError: Если модель не содержит поля с алиасом 'Name'
            """
            # Сначала проверяем прямой доступ к полю Name
            if hasattr(self, "Name"):
                return self.Name

            # Затем проверяем поля с алиасом Name
            for field_name, field_info in self.model_fields.items():
                if hasattr(field_info, "alias") and field_info.alias == "Name":
                    return getattr(self, field_name)

            raise ValueError(
                "Модель должна иметь поле с именем 'Name' или с alias='Name'"
            )

        # Добавляем методы в класс
        cls.get_attribute_data = get_attribute_data
        cls.get_field_to_attribute_mapping = get_field_to_attribute_mapping
        cls.get_object_name = get_object_name

        return cls

    # Позволяет использовать декоратор как с аргументами, так и без
    if cls is None:
        return wrap
    return wrap(cls)


def create_model_from_class_attributes(
    class_name: str,
    class_attributes: List[Dict[str, Any]],
    base_class: Type[BaseModel] = BaseModel,
) -> Type[BaseModel]:
    """
    Создает Pydantic модель на основе атрибутов класса из Неосинтеза.

    Args:
        class_name: Имя класса в Неосинтезе
        class_attributes: Список атрибутов класса
        base_class: Базовый класс для новой модели

    Returns:
        Type[BaseModel]: Созданная модель
    """
    fields = {}

    # Добавляем поле Name
    fields["Name"] = (str, ...)

    # Добавляем поля для атрибутов
    for attr in class_attributes:
        if not isinstance(attr, dict) or "Name" not in attr:
            continue

        attr_name = attr["Name"]
        attr_type = attr.get("Type", 0)

        # Определяем тип поля на основе типа атрибута
        field_type = str  # По умолчанию строка
        if attr_type == 1:  # Целое число
            field_type = int
        elif attr_type == 2:  # Вещественное число
            field_type = float
        elif attr_type == 3:  # Дата
            field_type = (
                str  # Можно использовать datetime, но для простоты оставим строку
            )
        elif attr_type == 4:  # Булево
            field_type = bool

        # Добавляем поле с алиасом
        fields[attr_name.lower().replace(" ", "_")] = (
            Optional[field_type],
            Field(None, alias=attr_name),
        )

    # Создаем модель
    model = create_model(
        f"{class_name.replace(' ', '')}Model", __base__=base_class, **fields
    )

    # Добавляем имя класса
    model.__class_name__ = class_name

    # Декорируем модель
    return neosintez_model(model)
