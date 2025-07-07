"""
Фабрика для динамического создания Pydantic-моделей на основе пользовательских данных.
"""

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar, Dict, List, Optional, Type

from pydantic import BaseModel, Field, create_model

from neosintez_api.models import NeosintezBaseModel
from neosintez_api.services.object_search_service import ObjectSearchService
from neosintez_api.utils import generate_field_name, neosintez_type_to_python_type

from ..class_service import ClassService
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


class DynamicModelFactory:
    """
    "Строитель", который разбирает пользовательские данные ОДНОГО объекта
    и создает единую, плоскую Pydantic модель для его представления.
    """

    def __init__(
        self,
        client: "NeosintezClient",
        class_service: "ClassService",
        name_aliases: List[str],
        class_name_aliases: List[str],
    ):
        self.client = client
        self.class_service = class_service
        self.name_aliases = [alias.lower() for alias in name_aliases]
        self.class_name_aliases = [alias.lower() for alias in class_name_aliases]
        self.search_service = ObjectSearchService(self.client)
        self.resolver = AttributeResolver(self.client)
        self.logger = logging.getLogger(__name__)
        # Кэш для хранения уже сгенерированных Pydantic моделей
        self._model_cache: Dict[str, Type[NeosintezBaseModel]] = {}

    def _get_or_create_pydantic_model(
        self, class_name: str, attributes_meta: Dict[str, Any]
    ) -> type["NeosintezBaseModel"]:
        """
        Получает Pydantic-модель из кэша или создает новую, если ее там нет.
        """
        sanitized_class_name = "".join(filter(str.isalnum, class_name))
        model_name = f"{sanitized_class_name}DynamicModel"

        if model_name in self._model_cache:
            return self._model_cache[model_name]

        self.logger.debug(f"Кэш моделей не содержит '{model_name}'. Создание новой Pydantic-модели.")

        # 1. Определяем поля для динамических атрибутов
        dynamic_fields = {}
        for attr_name, meta in attributes_meta.items():
            field_name = generate_field_name(attr_name)

            # Если тип атрибута - ссылка (8), то он может быть строкой или уже разрешенным словарем.
            if hasattr(meta, "Type") and meta.Type == 8:  # 8 = Ссылка на объект
                python_type = Any
            else:
                python_type = neosintez_type_to_python_type(meta.Type if hasattr(meta, "Type") else None)

            dynamic_fields[field_name] = (
                Optional[python_type],
                Field(None, alias=attr_name),
            )

        # 2. Создаем временный базовый класс с нужной мета-информацией.
        class _Neosintez:
            pass

        _Neosintez.class_name = class_name

        class TempBase(NeosintezBaseModel):
            Neosintez: ClassVar = _Neosintez

        # 3. Собираем все поля вместе. 'name' обязателен для ObjectService.
        fields_to_add = {
            "name": (str, Field(..., description="Имя объекта")),
            **dynamic_fields,
        }

        # 4. Динамически создаем финальную модель
        UnifiedObjectModel = create_model(
            model_name,
            **fields_to_add,
            __base__=TempBase,
        )

        # 5. Сохраняем в кэш и возвращаем
        self._model_cache[model_name] = UnifiedObjectModel
        return UnifiedObjectModel

    def _find_and_extract(self, data: Dict[str, Any], aliases: List[str]) -> (str, Any):
        """Находит ключ по одному из алиасов, возвращает его и значение."""
        for key, value in data.items():
            if key.lower() in aliases:
                return key, value
        return None, None

    async def create(self, user_data: Dict[str, Any]) -> ObjectBlueprint:
        """
        Создает чертеж объекта из словаря, автоматически находя
        имя класса и получая необходимые метаданные.
        """
        # 1. Извлекаем имя класса из данных
        _, class_name_to_find = self._find_and_extract(user_data, self.class_name_aliases)
        if not class_name_to_find:
            raise ValueError(f"В данных не найдено имя класса. Ожидался один из ключей: {self.class_name_aliases}")

        # 2. Получаем метаданные для класса из кэширующего сервиса
        class_info_list = await self.class_service.find_by_name(class_name_to_find)
        if not class_info_list:
            raise ValueError(f"Класс '{class_name_to_find}' не найден в Неосинтезе.")

        class_info = next(
            (c for c in class_info_list if c.Name.lower() == class_name_to_find.lower()),
            None,
        )
        if not class_info:
            raise ValueError(
                f"Найдено несколько классов, похожих на '{class_name_to_find}', но точное совпадение отсутствует."
            )

        class_id = str(class_info.Id)
        class_attributes = await self.class_service.get_attributes(class_id)
        attributes_meta_map = {attr.Name: attr for attr in class_attributes}

        # 3. Вызываем внутренний метод-строитель с полной мета-информацией
        return await self._create_with_metadata(
            user_data=user_data,
            class_name=class_name_to_find,
            class_id=class_id,
            attributes_meta=attributes_meta_map,
        )

    async def _create_with_metadata(
        self,
        user_data: Dict[str, Any],
        class_name: str,
        class_id: str,
        attributes_meta: Dict[str, Any],
    ) -> ObjectBlueprint:
        """Внутренний метод, создающий модель при наличии всех метаданных."""
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

        # 4. Создаем или получаем Pydantic модель из кэша
        UnifiedObjectModel = self._get_or_create_pydantic_model(class_name, attr_lookup)

        # 5. Разрешаем ссылочные атрибуты, если они переданы как строки
        resolved_attribute_data = attribute_data.copy()
        for attr_name, attr_value in attribute_data.items():
            meta = attr_lookup.get(attr_name)
            if meta and meta.Type == 8 and isinstance(attr_value, str):
                try:
                    resolved_value = await self.resolver.resolve_link_attribute_as_object(
                        attr_meta=meta, attr_value=attr_value
                    )
                    resolved_attribute_data[attr_name] = resolved_value
                except ValueError as e:
                    self.logger.warning(
                        f"Не удалось разрешить значение '{attr_value}' для ссылочного "
                        f"атрибута '{meta.Name}'. Атрибут будет пропущен. Ошибка: {e}"
                    )
                    resolved_attribute_data[attr_name] = None

        # 7. Готовим данные для создания экземпляра модели.
        validation_data = resolved_attribute_data
        name_key, name_value = self._find_and_extract(user_data, self.name_aliases)
        if not name_value:
            raise ValueError(f"Не удалось найти имя объекта по алиасам: {self.name_aliases}")
        validation_data["name"] = name_value

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
            errors=[],
        )
