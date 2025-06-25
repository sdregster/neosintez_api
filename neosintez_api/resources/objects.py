"""
Ресурсный класс для работы с объектами в API Неосинтез.
"""

import asyncio
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from ..models import (
    Object,
    PathAncestor,
    PathResponse,
    SearchFilter,
    SearchRequest,
    SearchResponse,
)
from ..utils import chunk_list
from .base import BaseResource


class ObjectsResource(BaseResource):
    """
    Ресурсный класс для работы с объектами в API Неосинтез.
    """

    async def get_by_id(self, object_id: Union[str, UUID]) -> Object:
        """
        Получает объект по его ID.

        Args:
            object_id: ID объекта

        Returns:
            Object: Объект

        Raises:
            NeosintezAPIError: Если объект не найден
        """
        endpoint = f"api/objects/{object_id}"

        result = await self._request("GET", endpoint)
        if isinstance(result, dict):
            # Преобразуем Entity в EntityId для совместимости с нашей моделью
            if (
                "Entity" in result
                and isinstance(result["Entity"], dict)
                and "Id" in result["Entity"]
            ):
                result["EntityId"] = result["Entity"]["Id"]

            return Object.model_validate(result)

        from ..exceptions import NeosintezAPIError

        raise NeosintezAPIError(404, "Объект не найден", None)

    async def create(self, parent_id: Union[str, UUID], data: Dict[str, Any]) -> str:
        """
        Создает новый объект в API.

        Args:
            parent_id: ID родительского объекта
            data: Данные для создания объекта

        Returns:
            str: ID созданного объекта
        """
        endpoint = "api/objects"
        params = {"parent": str(parent_id)}

        result = await self._request("POST", endpoint, params=params, data=data)
        if isinstance(result, dict) and "Id" in result:
            return result["Id"]

        # Если результат не содержит Id, возвращаем пустую строку
        from ..exceptions import NeosintezAPIError

        if isinstance(result, dict):
            # Если результат - словарь, но без Id, возможно это ошибка
            error_message = result.get(
                "Message", "Неизвестная ошибка при создании объекта"
            )
            raise NeosintezAPIError(400, error_message, str(result))
        else:
            # Если результат не словарь, возвращаем пустую строку
            return ""

    async def update(self, object_id: Union[str, UUID], data: Dict[str, Any]) -> bool:
        """
        Обновляет объект.

        Args:
            object_id: ID объекта
            data: Данные для обновления объекта

        Returns:
            bool: True, если обновление успешно
        """
        endpoint = f"api/objects/{object_id}"

        await self._request("PUT", endpoint, data=data)
        return True

    async def delete(self, object_id: Union[str, UUID]) -> bool:
        """
        Удаляет объект.

        Args:
            object_id: ID объекта

        Returns:
            bool: True, если удаление успешно
        """
        endpoint = f"api/objects/{object_id}"

        await self._request("DELETE", endpoint)
        return True

    async def get_children(self, parent_id: Union[str, UUID]) -> List[Object]:
        """
        Получает список дочерних объектов для заданного родительского объекта.

        Args:
            parent_id: ID родительского объекта

        Returns:
            List[Object]: Список дочерних объектов
        """
        endpoint = f"api/objects/{parent_id}/children"

        result = await self._request("GET", endpoint)
        if isinstance(result, list):
            return [Object.model_validate(item) for item in result]
        return []

    async def search(
        self,
        request: SearchRequest,
        take: Optional[int] = None,
        skip: Optional[int] = None,
    ) -> SearchResponse:
        """
        Выполняет поиск объектов по заданным критериям.

        Args:
            request: Запрос на поиск
            take: Количество записей для выборки (переопределяет значение в request)
            skip: Смещение для пагинации (переопределяет значение в request)

        Returns:
            SearchResponse: Результаты поиска
        """
        if take is not None:
            request.Take = take
        if skip is not None:
            request.Skip = skip

        endpoint = "api/objects/search"
        params = {}
        if request.Take is not None:
            params["take"] = request.Take
        if request.Skip is not None:
            params["skip"] = request.Skip

        headers = {"X-HTTP-Method-Override": "GET"}

        result = await self._request(
            "POST", endpoint, params=params, data=request, headers=headers
        )
        return SearchResponse.model_validate(result)

    async def search_all(self, request: SearchRequest) -> List[Object]:
        """
        Выполняет поиск всех объектов по заданным критериям с автоматической пагинацией.

        Args:
            request: Запрос на поиск

        Returns:
            List[Object]: Все найденные объекты
        """
        limit = 500
        first_response = await self.search(request, take=limit, skip=0)

        total_items = first_response.Total
        items = first_response.Result

        if total_items > limit:
            total_pages = (total_items + limit - 1) // limit
            tasks = []

            for page in range(1, total_pages):
                skip = page * limit
                tasks.append(self.search(request, take=limit, skip=skip))

            if tasks:
                responses = await asyncio.gather(*tasks)
                for response in responses:
                    items.extend(response.Result)

        return items

    async def get_path(self, object_id: Union[str, UUID]) -> PathResponse:
        """
        Получает путь к объекту от корня иерархии.

        Args:
            object_id: ID объекта

        Returns:
            PathResponse: Путь к объекту
        """
        endpoint = f"api/objects/{object_id}/path"

        result = await self._request("GET", endpoint)
        if isinstance(result, dict):
            return PathResponse.model_validate(result)

        # Создаем пустой объект в случае ошибки
        return PathResponse(AncestorsOrSelf=[])

    async def get_paths_batch(
        self,
        object_ids: List[Union[str, UUID]],
        chunk_size: int = 20,
    ) -> Dict[str, List[PathAncestor]]:
        """
        Получает пути для нескольких объектов с ограничением одновременных запросов.

        Args:
            object_ids: Список ID объектов
            chunk_size: Размер блока для одновременной обработки

        Returns:
            Dict[str, List[PathAncestor]]: Словарь путей с ключами ID объектов
        """
        # Разбиваем список id на блоки
        id_chunks = chunk_list(object_ids, chunk_size)

        result: Dict[str, List[PathAncestor]] = {}

        # Обрабатываем блоки последовательно, внутри блока - параллельно
        for chunk in id_chunks:
            semaphore = asyncio.Semaphore(chunk_size)

            async def get_path_with_semaphore(item_id):
                async with semaphore:
                    try:
                        path = await self.get_path(item_id)
                        return str(item_id), path.AncestorsOrSelf
                    except Exception:
                        return str(item_id), None

            tasks = [get_path_with_semaphore(item_id) for item_id in chunk]
            chunk_results = await asyncio.gather(*tasks)

            # Сохраняем результаты этого блока
            for item_id, ancestors in chunk_results:
                if ancestors is not None:
                    result[str(item_id)] = ancestors

        return result

    async def rename(self, object_id: Union[str, UUID], new_name: str) -> bool:
        """
        Переименовывает объект.

        Args:
            object_id: ID объекта
            new_name: Новое имя объекта

        Returns:
            bool: True, если переименование успешно
        """
        endpoint = f"api/objects/{object_id}/name"
        params = {"new": new_name}

        await self._request("PUT", endpoint, params=params)
        return True

    async def move(
        self, object_id: Union[str, UUID], parent_id: Union[str, UUID]
    ) -> bool:
        """
        Перемещает объект под нового родителя.

        Args:
            object_id: ID объекта для перемещения
            parent_id: ID нового родительского объекта

        Returns:
            bool: True, если перемещение успешно
        """
        endpoint = f"api/objects/{object_id}/parent"
        params = {"parentId": str(parent_id)}

        await self._request("PUT", endpoint, params=params)
        return True

    async def move_batch(
        self,
        object_ids: List[Union[str, UUID]],
        parent_id: Union[str, UUID],
    ) -> bool:
        """
        Перемещает несколько объектов под нового родителя.

        Args:
            object_ids: Список ID объектов для перемещения
            parent_id: ID нового родительского объекта

        Returns:
            bool: True, если все объекты успешно перемещены
        """
        tasks = []
        for object_id in object_ids:
            tasks.append(self.move(object_id, parent_id))

        await asyncio.gather(*tasks)
        return True

    async def get_by_class_and_parent(
        self,
        class_id: Union[str, UUID],
        parent_id: Union[str, UUID],
    ) -> List[Object]:
        """
        Получает объекты указанного класса с указанным родителем.

        Args:
            class_id: ID класса
            parent_id: ID родительского объекта

        Returns:
            List[Object]: Список найденных объектов
        """
        filters = [
            SearchFilter(Type=4, Value=str(parent_id)),
            SearchFilter(Type=5, Value=str(class_id)),
        ]
        request = SearchRequest(Filters=filters)

        return await self.search_all(request)
