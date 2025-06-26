"""
Сервисный слой для работы с объектами через Pydantic-модели.
Обеспечивает создание, чтение и обновление объектов через типизированные модели данных.
"""

import logging
from typing import Any, Dict, Generic, List, Type, TypeVar, Union
from uuid import UUID

from pydantic import BaseModel

from ..client import NeosintezClient
from ..exceptions import ApiError, ModelValidationError
from ..utils import build_attribute_body

# Определяем тип для динамических моделей
T = TypeVar("T", bound=BaseModel)

# Настройка логгера
logger = logging.getLogger("neosintez_api.services.object_service")


class ObjectService(Generic[T]):
    """
    Сервис для работы с объектами через модели Pydantic.
    """

    def __init__(self, client: NeosintezClient):
        """
        Инициализирует сервис объектов.

        Args:
            client: Клиент API Неосинтеза
        """
        self.client = client

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
                object_name = model.get_object_name()
            except (AttributeError, ValueError):
                # Пробуем найти поле Name или поле с алиасом Name
                object_name = None
                if hasattr(model, "Name"):
                    object_name = model.Name
                else:
                    for field_name, field_info in model.model_fields.items():
                        if hasattr(field_info, "alias") and field_info.alias == "Name":
                            object_name = getattr(model, field_name)
                            break

                if not object_name:
                    raise ModelValidationError(
                        "Модель должна иметь поле с именем 'Name' или с alias='Name'"
                    )

            # 3) Получаем ID класса по его имени
            classes = await self.client.classes.get_classes_by_name(class_name)
            if not classes:
                raise ApiError(f"Класс '{class_name}' не найден")

            class_id = classes[0]["id"]
            class_name_from_api = classes[0]["name"]
            logger.info(f"Найден класс '{class_name_from_api}' с ID {class_id}")

            # 4) Получаем атрибуты класса
            class_attributes = await self.client.classes.get_attributes(class_id)
            logger.info(f"Получено {len(class_attributes)} атрибутов класса")

            # 5) Создаем словарь атрибутов по имени
            attr_by_name = {}
            for attr in class_attributes:
                if isinstance(attr, dict) and "Name" in attr:
                    attr_by_name[attr["Name"]] = attr
                else:
                    logger.warning(f"Пропущен атрибут с неверным форматом: {attr}")

            # 6) Подготавливаем базовые данные объекта
            object_data = {
                "Name": object_name,
                "Entity": {"Id": class_id, "Name": class_name},
                "IsActualVersion": True,
                "Version": 1,
                "VersionTimestamp": "2023-01-01T00:00:00Z",
                "Attributes": {},  # Добавляем атрибуты прямо в запрос на создание
            }

            # 7) Получаем словарь с ключами-алиасами
            try:
                model_data = model.get_attribute_data()
            except AttributeError:
                model_data = model.model_dump(by_alias=True)

            # 8) Получаем маппинг полей на атрибуты
            try:
                field_mapping = model.get_field_to_attribute_mapping()
            except AttributeError:
                field_mapping = {}
                for field_name, field_info in model.model_fields.items():
                    field_mapping[field_name] = field_info.alias or field_name

            # 9) Итерируем по всем полям модели, кроме Name
            for field_name, field_value in model_data.items():
                # Пропускаем Name и None значения
                if field_name == "Name" or field_value is None:
                    continue

                # Ищем соответствующий атрибут в классе по алиасу
                if field_name in attr_by_name:
                    attr_meta = attr_by_name[field_name]
                    attr_id = attr_meta["Id"]

                    # Создаем тело атрибута
                    try:
                        # Добавляем атрибут в словарь атрибутов объекта
                        object_data["Attributes"][attr_id] = {
                            "Name": field_name,
                            "Type": attr_meta["Type"],
                            "Value": field_value,
                        }
                        logger.info(f"Добавлен атрибут {field_name}={field_value}")
                    except Exception as e:
                        logger.warning(
                            f"Ошибка при создании атрибута {field_name}: {str(e)}"
                        )

            # 10) Создаем объект с атрибутами
            logger.info(
                f"Создание объекта '{object_name}' класса '{class_name}' в родителе {parent_id}"
            )
            object_id = await self.client.objects.create(parent_id, object_data)
            logger.info(f"Создан объект с ID {object_id}")

            return object_id

        except ApiError as e:
            logger.error(f"Ошибка API при создании объекта: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Ошибка при создании объекта: {str(e)}")
            raise ApiError(f"Ошибка при создании объекта: {str(e)}")

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
        Обновляются только те атрибуты, которые изменились.

        Args:
            object_id: Идентификатор объекта
            model: Модель объекта

        Returns:
            bool: True, если атрибуты успешно обновлены

        Raises:
            ApiError: Если произошла ошибка при обновлении атрибутов
            ModelValidationError: Если модель не соответствует требованиям
        """
        try:
            # 1) Получаем текущие данные объекта вместе с атрибутами
            object_data = await self.client.objects.get_by_id(object_id)
            logger.info(f"Получены данные объекта {object_id}")

            # 2) Создаем словарь атрибутов по имени
            attr_by_name = {}
            attr_values = {}

            # Обрабатываем атрибуты из объекта
            if hasattr(object_data, "Attributes") and object_data.Attributes:
                for attr_id, attr_data in object_data.Attributes.items():
                    if isinstance(attr_data, dict) and "Name" in attr_data:
                        attr_name = attr_data["Name"]
                        attr_by_name[attr_name] = {"Id": attr_id, **attr_data}
                        if "Value" in attr_data:
                            attr_values[attr_name] = attr_data["Value"]
                    else:
                        # Если атрибут не словарь или не содержит имя, пропускаем его
                        logger.warning(
                            f"Пропущен атрибут с неверным форматом: {attr_id}={attr_data}"
                        )

            # 3) Получаем класс объекта
            class_id = object_data.EntityId
            if not class_id:
                raise ApiError(f"Не удалось определить класс объекта {object_id}")

            # 4) Получаем атрибуты класса (для тех, которых нет у объекта)
            class_attributes = await self.client.classes.get_attributes(class_id)
            logger.info(f"Получено {len(class_attributes)} атрибутов класса")

            # 5) Дополняем словарь атрибутов атрибутами класса
            for attr in class_attributes:
                if (
                    hasattr(attr, "Name")
                    and attr.Name
                    and attr.Name not in attr_by_name
                ):
                    attr_dict = attr.model_dump()
                    attr_by_name[attr.Name] = attr_dict

            # 6) Подготавливаем набор атрибутов для обновления
            attributes_to_update = []

            # Получаем словарь с ключами-алиасами
            try:
                model_data = model.get_attribute_data()
            except AttributeError:
                model_data = model.model_dump(by_alias=True)

            # Получаем маппинг полей на атрибуты
            try:
                field_mapping = model.get_field_to_attribute_mapping()
            except AttributeError:
                field_mapping = {}
                for field_name, field_info in model.model_fields.items():
                    field_mapping[field_name] = field_info.alias or field_name

            # Проверяем поля модели, кроме Name
            for field_name, field_value in model_data.items():
                # Пропускаем Name и None значения
                if field_name == "Name" or field_value is None:
                    continue

                # Ищем атрибут по алиасу
                if field_name in attr_by_name:
                    attr_meta = attr_by_name[field_name]

                    # Проверяем, изменилось ли значение
                    if (
                        field_name not in attr_values
                        or attr_values[field_name] != field_value
                    ):
                        # Создаем тело атрибута
                        try:
                            attr_body = self._build_attribute_body(
                                attr_meta, field_value
                            )
                            attributes_to_update.append(attr_body)
                            logger.info(
                                f"Атрибут {field_name} будет обновлен: {field_value}"
                            )
                        except Exception as e:
                            logger.warning(
                                f"Ошибка при создании тела атрибута {field_name}: {str(e)}"
                            )

            # 7) Устанавливаем атрибуты
            if attributes_to_update:
                await self._set_attributes(object_id, attributes_to_update)
                logger.info(f"Обновлены атрибуты для объекта {object_id}")
                return True
            else:
                logger.info("Нет атрибутов для обновления")
                return False

        except ApiError as e:
            logger.error(f"Ошибка API при обновлении атрибутов: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Ошибка при обновлении атрибутов: {str(e)}")
            raise ApiError(f"Ошибка при обновлении атрибутов: {str(e)}")

    async def _set_attributes(
        self, object_id: str, attributes: List[Dict[str, Any]]
    ) -> bool:
        """
        Устанавливает атрибуты объекта.

        Args:
            object_id: Идентификатор объекта
            attributes: Список атрибутов для установки

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
                logger.debug(f"Атрибут {i + 1}: {attr}")

            # Устанавливаем атрибуты
            result = await self.client.objects.set_attributes(object_id, attributes)

            if not result:
                logger.warning(
                    f"Не удалось установить атрибуты для объекта {object_id}"
                )
                return False

            logger.info(f"Успешно установлены атрибуты для объекта {object_id}")
            return True
        except Exception as e:
            logger.error(f"Ошибка при установке атрибутов: {str(e)}")
            raise ApiError(f"Ошибка при установке атрибутов: {str(e)}")

    def _build_attribute_body(
        self, attr_meta: Dict[str, Any], value: Any
    ) -> Dict[str, Any]:
        """
        Формирует тело запроса для атрибута на основе его метаданных и значения.

        Args:
            attr_meta: Метаданные атрибута
            value: Значение атрибута

        Returns:
            Dict[str, Any]: Тело запроса для атрибута
        """
        try:
            # Получаем базовые данные атрибута
            attr_id = attr_meta["Id"]
            attr_name = attr_meta["Name"]
            attr_type = attr_meta.get("Type", 0)

            # Формируем тело запроса в зависимости от типа атрибута
            body = {
                "Id": attr_id,
                "Name": attr_name,  # Добавляем имя атрибута
                "Type": attr_type,
            }

            # Добавляем значение в правильном формате в зависимости от типа атрибута
            if attr_type == 0:  # Строка
                body["Value"] = str(value)
            elif attr_type == 1:  # Целое число
                body["Value"] = int(value)
            elif attr_type == 2:  # Вещественное число
                body["Value"] = float(value)
            elif attr_type == 3:  # Дата
                body["Value"] = str(
                    value
                )  # Предполагается, что дата передается в строковом формате
            elif attr_type == 4:  # Булево
                body["Value"] = bool(value)
            else:
                body["Value"] = str(value)  # По умолчанию преобразуем в строку

            return body
        except Exception as e:
            logger.warning(
                f"Ошибка при создании тела атрибута: {str(e)}. Используем упрощенную версию."
            )
            return build_attribute_body(attr_meta, value)
