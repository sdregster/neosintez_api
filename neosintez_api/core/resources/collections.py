"""
Ресурсный класс для работы с коллекциями объектов в API Неосинтез.
"""

import logging
from typing import Any, Dict, Optional, Union
from uuid import UUID

from ...models import CollectionQueryResult
from .base import BaseResource


# Настройка логгера
logger = logging.getLogger("neosintez_api.resources.collections")


class CollectionsResource(BaseResource):
    """
    Ресурсный класс для работы с коллекциями объектов в API Неосинтез.
    """

    async def get_collection_items(
        self,
        object_id: Union[str, UUID],
        attribute_id: Union[str, UUID],
        *,
        order: Optional[Dict[str, str]] = None,
        skip: Optional[int] = None,
        take: Optional[int] = None,
        filter_text: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Получает элементы коллекции объекта.

        Args:
            object_id: ID объекта-владельца коллекции
            attribute_id: ID атрибута типа "Objects collection"
            order: Словарь сортировки (ключ - поле, значение - направление)
            skip: Количество записей для пропуска (пагинация)
            take: Количество записей для выборки
            filter_text: Текст для фильтрации (опциональный)

        Returns:
            CollectionQueryResult: Результат с элементами коллекции и общим количеством

        Raises:
            NeosintezAPIError: Если произошла ошибка при запросе
        """
        endpoint = f"api/objects/{object_id}/collections"

        # Подготовка параметров запроса
        params = {"attributeId": str(attribute_id)}

        if order:
            # Добавляем параметры сортировки в формате order[field]=direction
            for field, direction in order.items():
                params[f"order[{field}]"] = direction

        if skip is not None:
            params["Skip"] = skip

        if take is not None:
            params["Take"] = take

        if filter_text:
            params["filter"] = filter_text

        logger.debug(f"Запрос коллекции для объекта {object_id}, атрибут {attribute_id}, параметры: {params}")

        try:
            result = await self._request("GET", endpoint, params=params, response_model=CollectionQueryResult)

            logger.debug(f"Получено {result.Total if hasattr(result, 'Total') else 'неизвестно'} элементов коллекции")
            return result

        except Exception as e:
            logger.error(f"Ошибка при получении коллекции для объекта {object_id}: {e}")
            raise

    async def create_collection_item(
        self,
        object_id: Union[str, UUID],
        attribute_id: Union[str, UUID],
        item_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Создает элемент коллекции.

        Args:
            object_id: ID объекта-владельца коллекции
            attribute_id: ID атрибута типа "Objects collection"
            item_data: Данные создаваемого элемента коллекции

        Returns:
            Dict[str, Any]: Созданный элемент коллекции

        Raises:
            NeosintezAPIError: Если произошла ошибка при создании
        """
        endpoint = f"api/objects/{object_id}/collections"

        params = {"attributeId": str(attribute_id)}

        logger.debug(f"Создание элемента коллекции для объекта {object_id}, атрибут {attribute_id}")

        try:
            result = await self._request("POST", endpoint, params=params, data=item_data)

            logger.debug(
                f"Элемент коллекции создан с ID: {result.get('Id') if isinstance(result, dict) else 'неизвестно'}"
            )
            return result

        except Exception as e:
            logger.error(f"Ошибка при создании элемента коллекции для объекта {object_id}: {e}")
            raise
