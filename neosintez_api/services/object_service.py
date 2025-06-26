"""
Сервисный слой для работы с объектами через Pydantic-модели.
Обеспечивает создание, чтение и обновление объектов через типизированные модели данных.
"""

import logging
import uuid
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union
from uuid import UUID

from pydantic import BaseModel

from ..client import NeosintezClient
from ..core.enums import WioAttributeType
from ..exceptions import ApiError, ModelValidationError
from ..utils import format_attribute_value, build_attribute_body
from .mappers.object_mapper import ObjectMapper

# Определяем тип для динамических моделей
T = TypeVar("T", bound=BaseModel)

# Настройка логгера
logger = logging.getLogger("neosintez_api.services.object_service")


class ObjectService(Generic[T]):
    """
    Сервис для работы с объектами через Pydantic-модели.
    """

    def __init__(self, client: NeosintezClient):
        """
        Инициализирует сервис.
        
        Args:
            client: Клиент API
        """
        self.client = client
        self.mapper = ObjectMapper()

    async def create(self, model: T, parent_id: Union[str, UUID]) -> str:
        """
        Создает объект из модели Pydantic.

        Args:
            model: Модель объекта
            parent_id: Идентификатор родительского объекта

        Returns:
            str: Идентификатор созданного объекта

        Raises:
            ApiError: Если произошла ошибка при создании объекта
            ModelValidationError: Если модель не соответствует требованиям
        """
        try:
            # 1) Получаем имя класса из модели
            class_name = getattr(model.__class__, "__class_name__", None)
            if not class_name:
                raise ModelValidationError("Модель должна иметь атрибут __class_name__")

            # 2) Получаем имя объекта из модели
            try:
                object_name = model.Name
            except AttributeError:
                try:
                    object_name = model.name
                except AttributeError:
                    raise ModelValidationError("Модель должна иметь атрибут name или Name")

            # 3) Находим класс по имени
            class_id = await self.client.classes.find_by_name(class_name)
            logger.info(f"Найден класс '{class_name}' с ID {class_id}")

            # 4) Получаем атрибуты класса
            class_attributes = await self.client.classes.get_attributes(class_id)
            logger.info(f"Получено {len(class_attributes)} атрибутов класса")

            # 5) Создаем объект
            object_data = {
                "Name": object_name,
                "Entity": {
                    "Id": class_id,
                    "Name": class_name
                }
            }

            if parent_id:
                object_data["Parent"] = {"Id": str(parent_id)}

            logger.info(f"Создание объекта '{object_name}' класса '{class_name}' в родителе {parent_id}")
            response = await self.client.objects.create(object_data)
            
            # Получаем ID созданного объекта
            object_id = response.get("Id")
            if not object_id:
                raise ApiError("Не удалось получить ID созданного объекта")
            
            # 6) Подготавливаем атрибуты для установки
            attr_meta_by_name = {}
            for attr in class_attributes:
                if isinstance(attr, dict):
                    attr_name = attr.get("Name")
                    if attr_name:
                        attr_meta_by_name[attr_name] = attr
                else:
                    attr_name = getattr(attr, "Name", None)
                    if attr_name:
                        attr_meta_by_name[attr_name] = attr

            # 7) Преобразуем модель в атрибуты
            attributes_list = await self.mapper.model_to_attributes(model, attr_meta_by_name)
            
            # 8) Устанавливаем атрибуты
            if attributes_list:
                await self.client.objects.set_attributes(object_id, attributes_list)
            
            return object_id
        except Exception as e:
            logger.error(f"Ошибка API при создании объекта: {e}")
            raise

    async def read(self, object_id: Union[str, UUID], model_class: Type[T]) -> T:
        """
        Читает объект в модель Pydantic.

        Args:
            object_id: Идентификатор объекта
            model_class: Класс модели

        Returns:
            T: Экземпляр модели

        Raises:
            ApiError: Если произошла ошибка при чтении объекта
            ModelValidationError: Если модель не соответствует требованиям
        """
        try:
            # 1) Получаем данные объекта вместе с атрибутами
            object_data = await self.client.objects.get_by_id(object_id)
            logger.info(f"Получены данные объекта {object_id}")

            # 2) Создаем словарь для данных модели
            model_data = {"Name": object_data.Name}

            # 3) Получаем атрибуты из объекта
            object_attributes = []
            if hasattr(object_data, "Attributes") and object_data.Attributes:
                # Преобразуем словарь атрибутов в список для единообразной обработки
                for attr_id, attr_data in object_data.Attributes.items():
                    if isinstance(attr_data, dict):
                        attr_dict = {"Id": attr_id}
                        attr_dict.update(attr_data)
                        object_attributes.append(attr_dict)
                    else:
                        # Если атрибут не словарь, создаем минимальную структуру
                        object_attributes.append({"Id": attr_id, "Value": attr_data})

            logger.info(f"Получено {len(object_attributes)} атрибутов объекта")

            # 4) Получаем маппинг полей на атрибуты
            try:
                # Пытаемся использовать метод get_field_to_attribute_mapping если он есть
                field_mapping = {}
                for field_name, field_info in model_class.model_fields.items():
                    field_mapping[field_name] = field_info.alias or field_name
            except Exception as e:
                logger.warning(f"Ошибка при получении маппинга полей: {str(e)}")
                field_mapping = {}

            # 5) Заполняем данные модели из атрибутов объекта
            for attr in object_attributes:
                if "Name" in attr and "Value" in attr:
                    attr_name = attr["Name"]
                    attr_value = attr["Value"]

                    # Пропускаем атрибуты без значений
                    if attr_value is None:
                        continue

                    # Сопоставляем с полями модели по маппингу
                    for field_name, field_alias in field_mapping.items():
                        if field_name == attr_name or field_alias == attr_name:
                            model_data[field_name] = attr_value
                            logger.info(f"Установлено поле {field_name}={attr_value}")
                            break
                    else:
                        # Если не нашли соответствие, пробуем прямое сопоставление
                        for field_name, field_info in model_class.model_fields.items():
                            field_alias = field_info.alias or field_name
                            if field_name == attr_name or field_alias == attr_name:
                                model_data[field_name] = attr_value
                                logger.info(
                                    f"Установлено поле {field_name}={attr_value}"
                                )
                                break

            # 6) Создаем экземпляр модели
            try:
                model = model_class(**model_data)
                logger.info(f"Создана модель {model_class.__name__}")
                return model
            except Exception as e:
                logger.error(f"Ошибка при создании модели: {str(e)}")
                raise ModelValidationError(f"Ошибка при создании модели: {str(e)}")

        except ApiError as e:
            logger.error(f"Ошибка API при чтении объекта: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Ошибка при чтении объекта: {str(e)}")
            raise ApiError(f"Ошибка при чтении объекта: {str(e)}")

    async def update_attrs(self, object_id: Union[str, UUID], model: T) -> bool:
        """
        Обновляет атрибуты объекта из модели Pydantic.
        Отправляет только изменившиеся атрибуты.
        
        Args:
            object_id: ID объекта
            model: Новые данные объекта
            
        Returns:
            bool: True если обновление успешно
        """
        try:
            # 1) Получить текущие данные объекта
            current_obj = await self.client.objects.get_by_id(object_id)
            logger.info(f"Получен объект {object_id}")
            
            # 2) Получить атрибуты класса объекта
            class_id = current_obj.EntityId
            class_attributes = await self.client.classes.get_attributes(class_id)
            logger.debug(f"Получено {len(class_attributes)} атрибутов класса")
            
            # 3) Создать словарь атрибутов по имени
            attr_by_name = {
                (a["Name"] if isinstance(a, dict) else a.Name):
                (a if isinstance(a, dict) else a.model_dump())
                for a in class_attributes
            }
            
            # 4) Получить текущие значения атрибутов
            current_attrs = {}
            if hasattr(current_obj, "Attributes") and current_obj.Attributes:
                for attr_id, attr_data in current_obj.Attributes.items():
                    if isinstance(attr_data, dict) and "Name" in attr_data:
                        current_attrs[attr_data["Name"]] = attr_data["Value"]
            
            # 5) Сравнить с новыми значениями и собрать изменившиеся
            model_data = model.model_dump(by_alias=True)
            changed_attrs = []
            
            for attr_name, value in model_data.items():
                if attr_name == "Name" or value is None:
                    continue
                    
                if attr_name not in current_attrs or current_attrs[attr_name] != value:
                    if attr_name in attr_by_name:
                        attr_meta = attr_by_name[attr_name]
                        attr_id = str(attr_meta["Id"] if isinstance(attr_meta, dict) else attr_meta.Id)
                        formatted_value = self._format_attribute_value(attr_meta, value)
                        changed_attrs.append({
                            "Id": attr_id,
                            "Value": formatted_value
                        })
                        
                        if logger.isEnabledFor(logging.DEBUG):
                            logger.debug(f"Изменен атрибут {attr_name}: {current_attrs.get(attr_name)} -> {value}")
            
            # 6) Обновить изменившиеся атрибуты
            if changed_attrs:
                logger.info(f"Обновление {len(changed_attrs)} атрибутов объекта {object_id}")
                return await self.client.objects.set_attributes(object_id, changed_attrs)
            
            logger.info("Нет изменившихся атрибутов для обновления")
            return True
            
        except ApiError as e:
            logger.error(f"Ошибка API при обновлении атрибутов: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Ошибка при обновлении атрибутов: {str(e)}")
            raise ApiError(f"Ошибка при обновлении атрибутов: {str(e)}")
            
    def _format_attribute_value(self, attr_meta: Dict[str, Any], value: Any) -> Any:
        """
        Форматирует значение атрибута для API.
        
        Args:
            attr_meta: Метаданные атрибута
            value: Значение атрибута
            
        Returns:
            Any: Отформатированное значение
        """
        return format_attribute_value(attr_meta, value)

    async def _set_attributes(
        self, object_id: str, attributes: List[Dict[str, Any]]
    ) -> bool:
        """
        Устанавливает атрибуты объекта.

        Args:
            object_id: Идентификатор объекта
            attributes: Список атрибутов для установки в формате [{\"Id\": \"...\", \"Value\": \"...\", \"Type\": 1}]

        Returns:
            bool: True, если атрибуты успешно установлены

        Raises:
            ApiError: Если произошла ошибка при установке атрибутов
        """
        try:
            logger.debug(
                f"Устанавливаем {len(attributes)} атрибутов для объекта {object_id}"
            )

            # Вывод атрибутов для отладки
            for i, attr in enumerate(attributes):
                logger.debug(f"Атрибут {i+1}: {attr}")

            # Проверяем, что все атрибуты имеют необходимые поля
            for attr in attributes:
                if "Id" not in attr:
                    raise ValueError(f"Атрибут не содержит поле Id: {attr}")
                if "Value" not in attr:
                    raise ValueError(f"Атрибут не содержит поле Value: {attr}")
                if "Type" not in attr:
                    # Если тип не указан, пытаемся определить его
                    # ВАЖНО: В API Неосинтез тип 1 - это число, тип 2 - это строка
                    # Это отличается от нашего перечисления WioAttributeType
                    if isinstance(attr["Value"], int):
                        attr["Type"] = 1  # Число
                    elif isinstance(attr["Value"], str):
                        attr["Type"] = 2  # Строка
                    else:
                        attr["Type"] = 2  # По умолчанию строка
                if "Name" not in attr:
                    attr["Name"] = ""
                if "Constraints" not in attr:
                    attr["Constraints"] = []

            return await self.client.objects.set_attributes(object_id, attributes)
        except Exception as e:
            logger.error(f"Ошибка при установке атрибутов: {e}")
            raise ApiError(f"Ошибка API при установке атрибутов: {e}") from e
