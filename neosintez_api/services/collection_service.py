"""
Сервис для работы с коллекциями объектов через удобный API.
"""

import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union
from uuid import UUID

from neosintez_api.models import CollectionItem


# Настройка логгера
logger = logging.getLogger("neosintez_api.services.collection_service")

if TYPE_CHECKING:
    from neosintez_api.core.client import NeosintezClient


class CollectionService:
    """
    Сервис для работы с коллекциями объектов.
    Предоставляет удобные методы для работы с коллекциями через типизированные модели.
    """

    def __init__(self, client: "NeosintezClient"):
        """
        Инициализирует сервис с клиентом API.

        Args:
            client: Экземпляр клиента для взаимодействия с API
        """
        self.client = client

    async def get_collection_items(
        self,
        object_id: Union[str, UUID],
        attribute_id: Union[str, UUID],
        *,
        order_by: Optional[str] = None,
        order_direction: str = "asc",
        page: int = 1,
        page_size: int = 20,
        filter_text: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Получает элементы коллекции с удобной пагинацией.

        Args:
            object_id: ID объекта-владельца коллекции
            attribute_id: ID атрибута типа "Objects collection"
            order_by: Поле для сортировки (например, "542a224e-2305-f011-91d5-005056b6948b.name")
            order_direction: Направление сортировки ("asc" или "desc")
            page: Номер страницы (начинается с 1)
            page_size: Размер страницы
            filter_text: Текст для фильтрации

        Returns:
            CollectionQueryResult: Результат с элементами коллекции и общим количеством
        """
        # Преобразуем номер страницы в skip/take
        skip = (page - 1) * page_size
        take = page_size

        # Подготавливаем параметры сортировки
        order = None
        if order_by:
            order = {order_by: order_direction}

        logger.debug(
            f"Получение коллекции объекта {object_id}, атрибут {attribute_id}, страница {page}, размер {page_size}"
        )

        result = await self.client.collections.get_collection_items(
            object_id=object_id,
            attribute_id=attribute_id,
            order=order,
            skip=skip,
            take=take,
            filter_text=filter_text,
        )

        return result

    async def get_all_collection_items(
        self,
        object_id: Union[str, UUID],
        attribute_id: Union[str, UUID],
        *,
        order_by: Optional[str] = None,
        order_direction: str = "asc",
        filter_text: Optional[str] = None,
    ) -> List[CollectionItem]:
        """
        Получает все элементы коллекции без пагинации.

        Args:
            object_id: ID объекта-владельца коллекции
            attribute_id: ID атрибута типа "Objects collection"
            order_by: Поле для сортировки
            order_direction: Направление сортировки ("asc" или "desc")
            filter_text: Текст для фильтрации

        Returns:
            List[CollectionItem]: Список всех элементов коллекции
        """
        logger.debug(f"Получение всех элементов коллекции объекта {object_id}")

        result = await self.get_collection_items(
            object_id=object_id,
            attribute_id=attribute_id,
            order_by=order_by,
            order_direction=order_direction,
            page=1,
            page_size=1000,  # Большой размер страницы для получения всех элементов
            filter_text=filter_text,
        )

        all_items = result.Result or []

        # Если элементов больше чем на одной странице, получаем остальные
        if result.Total > 1000:
            pages_needed = (result.Total + 999) // 1000  # Округление вверх
            for page in range(2, pages_needed + 1):
                page_result = await self.get_collection_items(
                    object_id=object_id,
                    attribute_id=attribute_id,
                    order_by=order_by,
                    order_direction=order_direction,
                    page=page,
                    page_size=1000,
                    filter_text=filter_text,
                )
                if page_result.Result:
                    all_items.extend(page_result.Result)

        logger.debug(f"Получено {len(all_items)} элементов коллекции")
        return all_items

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
        """
        logger.debug(f"Создание элемента коллекции для объекта {object_id}")

        result = await self.client.collections.create_collection_item(
            object_id=object_id,
            attribute_id=attribute_id,
            item_data=item_data,
        )

        return result

    async def find_collection_item_by_name(
        self,
        object_id: Union[str, UUID],
        attribute_id: Union[str, UUID],
        name: str,
    ) -> Optional[CollectionItem]:
        """
        Находит элемент коллекции по имени.

        Args:
            object_id: ID объекта-владельца коллекции
            attribute_id: ID атрибута типа "Objects collection"
            name: Имя искомого элемента

        Returns:
            Optional[CollectionItem]: Найденный элемент или None
        """
        logger.debug(f"Поиск элемента коллекции '{name}' в объекте {object_id}")

        # Используем фильтрацию по тексту
        result = await self.get_collection_items(
            object_id=object_id,
            attribute_id=attribute_id,
            filter_text=name,
            page_size=100,  # Увеличиваем размер страницы для поиска
        )

        if result.Result:
            # Ищем точное совпадение по имени
            for item in result.Result:
                if item.Object.Name == name:
                    logger.debug(f"Найден элемент коллекции: {item.Id}")
                    return item

        logger.debug(f"Элемент коллекции '{name}' не найден")
        return None
