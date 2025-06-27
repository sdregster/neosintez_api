"""
Сервисный слой для работы с объектами через Pydantic-модели.
Обеспечивает создание, чтение и обновление объектов через типизированные модели данных.
"""

import asyncio
import logging
from typing import TYPE_CHECKING, Any, Dict, Generic, Type, TypeVar, Union
from uuid import UUID

from pydantic import BaseModel

from ..exceptions import ApiError
from ..utils import generate_field_name
from .mappers.object_mapper import ObjectMapper


# Определяем тип для динамических моделей
T = TypeVar("T", bound=BaseModel)

# Настройка логгера
logger = logging.getLogger("neosintez_api.services.object_service")

if TYPE_CHECKING:
    from ..core.client import NeosintezClient


class ObjectService(Generic[T]):
    """
    Сервис для работы с объектами через Pydantic-модели.
    Обеспечивает создание, чтение и обновление объектов.
    """

    def __init__(self, client: "NeosintezClient"):
        """
        Инициализирует сервис с клиентом API.

        Args:
            client: Экземпляр клиента для взаимодействия с API
        """
        self.client = client
        self.mapper = ObjectMapper()

    async def create(
        self,
        model: T,
        class_id: str,
        class_name: str,
        attributes_meta: Dict[str, Any],
        parent_id: Union[str, UUID, None] = None,
    ) -> T:
        """
        Создает объект из единой Pydantic-модели.

        Args:
            model: Экземпляр Pydantic-модели с данными.
            class_id: ID класса создаваемого объекта.
            class_name: Имя класса создаваемого объекта.
            attributes_meta: Словарь с метаданными атрибутов из API.
            parent_id: Идентификатор родительского объекта.

        Returns:
            T: Экземпляр модели, дополненный ID созданного объекта.

        Raises:
            ApiError: Если произошла ошибка при создании объекта.
        """
        try:
            # 1. Получаем имя из модели
            object_name = model.name

            logger.info(f"Создание объекта '{object_name}' класса '{class_name}' (ID: {class_id})")

            # 2. Создаем объект в API без атрибутов
            object_data = {
                "Name": object_name,
                "Entity": {"Id": class_id, "Name": class_name},
            }
            response = await self.client.objects.create(object_data, parent_id=parent_id)
            object_id = response.get("Id")
            if not object_id:
                raise ApiError("Не удалось получить ID созданного объекта после создания")
            logger.debug(f"Объект '{object_name}' создан с ID: {object_id}")

            # 3. Преобразуем модель в атрибуты с помощью маппера
            attr_meta_by_name = {
                (a["Name"] if isinstance(a, dict) else a.Name): (a if isinstance(a, dict) else a.model_dump())
                for a in attributes_meta.values()
            }
            attributes_list = await self.mapper.model_to_attributes(model, attr_meta_by_name)

            # 4. Устанавливаем атрибуты
            if attributes_list:
                await self.client.objects.set_attributes(object_id, attributes_list)
                logger.info(f"Для объекта {object_id} установлено {len(attributes_list)} атрибутов.")

            # 5. Возвращаем обновленную модель с ID
            model.id = object_id
            model.class_id = class_id
            return model

        except Exception as e:
            logger.error(f"Ошибка API при создании объекта '{model.name}': {e}")
            raise

    async def read(self, object_id: Union[str, UUID], model_class: Type[T]) -> T:
        """
        Читает объект и преобразует его в плоскую модель Pydantic.
        """
        try:
            # 1. Параллельно получаем данные объекта и его путь
            object_data, path_data = await asyncio.gather(
                self.client.objects.get_by_id(object_id),
                self.client.objects.get_path(object_id),
            )
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"Получен объект {object_id} и его путь.")

            class_id = object_data.EntityId

            # 2. Получаем метаданные атрибутов класса
            class_attributes = await self.client.classes.get_attributes(class_id)
            attr_id_to_name = {
                str(attr.get("Id") if isinstance(attr, dict) else attr.Id): (
                    attr.get("Name") if isinstance(attr, dict) else attr.Name
                )
                for attr in class_attributes
            }

            # 3. Определяем родителя
            parent_id = None
            if path_data and path_data.AncestorsOrSelf and len(path_data.AncestorsOrSelf) > 1:
                # Родитель - это предпоследний элемент в пути
                parent_id = str(path_data.AncestorsOrSelf[-2].Id)

            # 4. Собираем данные для создания плоской модели
            model_payload = {
                "id": str(object_data.Id),
                "class_id": str(class_id),
                "parent_id": parent_id,
                "name": object_data.Name or "",
            }

            # 5. Извлекаем и преобразуем атрибуты
            if hasattr(object_data, "Attributes") and object_data.Attributes:
                for attr_id_str, attr_value_data in object_data.Attributes.items():
                    attr_name = attr_id_to_name.get(attr_id_str)
                    if not attr_name:
                        logger.warning(f"Атрибут с ID {attr_id_str} не найден в метаданных класса.")
                        continue

                    field_name = generate_field_name(attr_name)
                    attr_value = attr_value_data.get("Value") if isinstance(attr_value_data, dict) else attr_value_data
                    model_payload[field_name] = attr_value

            # 6. Создаем экземпляр модели
            model_instance = model_class(**model_payload)
            return model_instance

        except Exception as e:
            logger.error(f"Ошибка при чтении объекта {object_id}: {e}")
            raise

    async def update(
        self,
        model: T,
        attributes_meta: Dict[str, Any],
    ) -> bool:
        """
        Интеллектуально обновляет объект, сравнивая текущее состояние с моделью.
        Обновляет имя, родителя и атрибуты только при их изменении, делая это параллельно.
        """
        if not model.id:
            raise ValueError("Модель должна содержать 'id' для обновления.")
        object_id = model.id

        try:
            logger.info(f"Начало интеллектуального обновления объекта {object_id}")

            # 1. Получаем текущее состояние объекта
            current_obj = await self.read(object_id, model.__class__)

            # 2. Собираем задачи для параллельного выполнения
            update_tasks = []

            # Сравниваем и обновляем имя
            if model.name != current_obj.name:
                update_tasks.append(self.client.objects.rename(object_id, model.name))
                logger.info(f"Запланировано обновление имени на '{model.name}'")

            # Сравниваем и перемещаем объект
            if model.parent_id and model.parent_id != current_obj.parent_id:
                update_tasks.append(self.client.objects.move(object_id, model.parent_id))
                logger.info(f"Запланировано перемещение в родителя {model.parent_id}")

            # Обновляем атрибуты (пока без сравнения, просто перезаписываем)
            attr_meta_by_name = {
                (a["Name"] if isinstance(a, dict) else a.Name): (a if isinstance(a, dict) else a.model_dump())
                for a in attributes_meta.values()
            }
            attributes_list = await self.mapper.model_to_attributes(model, attr_meta_by_name)

            if attributes_list:
                update_tasks.append(self.client.objects.set_attributes(object_id, attributes_list))
                logger.info(f"Запланировано обновление {len(attributes_list)} атрибутов.")

            # 3. Выполняем все запланированные задачи параллельно
            if update_tasks:
                await asyncio.gather(*update_tasks)
                logger.info(f"Все задачи по обновлению объекта {object_id} успешно выполнены.")
            else:
                logger.info(f"Нет изменений для обновления объекта {object_id}.")

            return True
        except Exception as e:
            logger.error(f"Ошибка при обновлении объекта {model.id}: {e}")
            raise

    async def delete(self, object_id: Union[str, UUID]) -> bool:
        """
        Удаляет объект по ID.
        """
        await self.client.objects.delete(str(object_id))
        return True
