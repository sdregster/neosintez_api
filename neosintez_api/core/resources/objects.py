"""
Ресурсный класс для работы с объектами в API Неосинтез.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from ...models import (
    NeoObject,
    PathAncestor,
    PathResponse,
    SearchFilter,
    SearchRequest,
    SearchResponse,
)
from ...utils import CustomJSONEncoder, chunk_list
from .base import BaseResource


# Настройка логгера
logger = logging.getLogger("neosintez_api.resources.objects")


class ObjectsResource(BaseResource):
    """
    Ресурсный класс для работы с объектами в API Неосинтез.
    """

    async def get_by_id(self, object_id: Union[str, UUID]) -> Dict[str, Any]:
        """
        Получает объект по его ID.

        Args:
            object_id: ID объекта

        Returns:
            Dict[str, Any]: Словарь с данными объекта

        Raises:
            NeosintezAPIError: Если объект не найден
        """
        endpoint = f"api/objects/{object_id}"

        result = await self._request("GET", endpoint)
        if isinstance(result, dict):
            # Преобразуем Entity в EntityId для совместимости с нашей моделью
            if "Entity" in result and isinstance(result["Entity"], dict) and "Id" in result["Entity"]:
                result["EntityId"] = result["Entity"]["Id"]

            return result

        from ...exceptions import NeosintezAPIError

        raise NeosintezAPIError(404, "Объект не найден", None)

    async def create(self, data: Dict[str, Any], parent_id: Optional[Union[str, UUID]] = None) -> Dict[str, Any]:
        """
        Создает новый объект.

        Args:
            data: Данные объекта для создания
            parent_id: ID родительского объекта (передается как query параметр)

        Returns:
            Dict[str, Any]: Созданный объект с его ID и другими данными
        """
        try:
            logger.debug(f"Отправка запроса на создание объекта: {data}")

            # Добавляем parent_id как query параметр, если он указан
            params = {}
            if parent_id:
                params["parent"] = str(parent_id)
                logger.debug(f"Создание объекта с родителем: {parent_id}")

            response = await self._request("POST", "api/objects", data=data, params=params)
            return response
        except Exception as e:
            logger.error(f"Ошибка при создании объекта: {e}")
            raise

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

    async def get_children(self, parent_id: Union[str, UUID]) -> List[NeoObject]:
        """
        Получает список дочерних объектов для заданного родительского объекта.

        Args:
            parent_id: ID родительского объекта

        Returns:
            List[NeoObject]: Список дочерних объектов
        """
        endpoint = f"api/objects/{parent_id}/children"

        result = await self._request("GET", endpoint)
        if isinstance(result, list):
            return [NeoObject.model_validate(item) for item in result]
        return []

    async def search(
        self,
        request: SearchRequest,
        take: Optional[int] = None,
        skip: Optional[int] = None,
    ) -> SearchResponse:
        """
        Выполняет поисковый запрос к API.

        Args:
            request: Тело запроса для поиска.
            take: Количество записей для возврата.
            skip: Количество записей для пропуска.

        Returns:
            Ответ API с результатами поиска.
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

        raw_result = await self._request("POST", endpoint, params=params, data=request, headers=headers)

        # Прокидываем вложенный Entity.Id в EntityId для каждого объекта в результате
        if "Result" in raw_result and isinstance(raw_result["Result"], list):
            for item in raw_result["Result"]:
                if (
                    isinstance(item, dict)
                    and "Object" in item
                    and isinstance(item["Object"], dict)
                    and "Entity" in item["Object"]
                    and isinstance(item["Object"]["Entity"], dict)
                    and "Id" in item["Object"]["Entity"]
                ):
                    item["Object"]["EntityId"] = item["Object"]["Entity"]["Id"]

        return SearchResponse.model_validate(raw_result)

    async def search_all(self, request: SearchRequest) -> List[NeoObject]:
        """
        Выполняет поиск всех объектов по заданным критериям с автоматической пагинацией.

        Args:
            request: Запрос на поиск

        Returns:
            List[NeoObject]: Все найденные объекты
        """
        limit = 500
        first_response = await self.search(request, take=limit, skip=0)

        total_items = first_response.Total
        # Извлекаем непосредственно объекты из результатов поиска
        items = [res.obj for res in first_response.Result]

        if total_items > limit:
            total_pages = (total_items + limit - 1) // limit
            tasks = []

            for page in range(1, total_pages):
                skip = page * limit
                tasks.append(self.search(request, take=limit, skip=skip))

            if tasks:
                responses = await asyncio.gather(*tasks)
                for response in responses:
                    items.extend([res.obj for res in response.Result])

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

            async def get_path_with_semaphore(item_id, sem):
                async with sem:
                    try:
                        path = await self.get_path(item_id)
                        return str(item_id), path.AncestorsOrSelf
                    except Exception:
                        return str(item_id), None

            tasks = [get_path_with_semaphore(item_id, semaphore) for item_id in chunk]
            chunk_results = await asyncio.gather(*tasks)

            # Сохраняем результаты этого блока
            for item_id_str, path_data in chunk_results:
                if path_data is not None:
                    result[item_id_str] = path_data

        return result

    async def rename(self, object_id: str, new_name: str) -> None:
        """Переименовывает объект."""
        endpoint = f"api/objects/{object_id}/name"
        await self._request("PUT", endpoint, params={"new": new_name})

    async def move(self, object_id: str, parent_id: str) -> None:
        """Перемещает объект к новому родителю."""
        endpoint = f"api/objects/{object_id}/parent"
        await self._request("PUT", endpoint, params={"parentId": parent_id})

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
    ) -> List[NeoObject]:
        """
        Получает объекты указанного класса с указанным родителем.

        Args:
            class_id: ID класса
            parent_id: ID родительского объекта

        Returns:
            List[NeoObject]: Список найденных объектов
        """
        filters = [
            SearchFilter(Type=4, Value=str(parent_id)),
            SearchFilter(Type=5, Value=str(class_id)),
        ]
        request = SearchRequest(Filters=filters)

        return await self.search_all(request)

    async def set_attributes(
        self,
        object_id: Union[str, UUID],
        attributes: Union[List[Dict[str, Any]], Dict[str, Any]],
    ) -> bool:
        """
        Устанавливает атрибуты объекта.

        Args:
            object_id: Идентификатор объекта
            attributes: Список атрибутов для установки или словарь {attr_id: value}

        Returns:
            bool: True, если атрибуты успешно установлены
        """
        # Приводим object_id к строке и обрабатываем случай, когда это словарь из API
        if isinstance(object_id, dict) and "Id" in object_id:
            object_id = object_id["Id"]
        else:
            object_id = str(object_id)

        # Проверка формата входных атрибутов и логирование
        logger.debug(f"Получены атрибуты для установки. Тип: {type(attributes)}, значение: {attributes}")

        # Преобразуем атрибуты в нужный формат для API
        attributes_array = []

        if isinstance(attributes, list):
            # Если атрибуты уже в формате списка объектов, проверяем наличие всех необходимых полей
            for attr in attributes:
                attr_obj = attr.copy()  # Создаем копию, чтобы не изменять оригинал

                # Проверяем наличие обязательных полей
                if "Id" not in attr_obj:
                    raise ValueError(f"Атрибут должен иметь поле 'Id': {attr_obj}")

                if "Value" not in attr_obj:
                    raise ValueError(f"Атрибут должен иметь поле 'Value': {attr_obj}")

                # Добавляем поле Name, если его нет
                if "Name" not in attr_obj:
                    attr_obj["Name"] = "forvalidation"

                # Добавляем поле Type, если его нет
                if "Type" not in attr_obj:
                    # Определяем тип по значению
                    if isinstance(attr_obj["Value"], int):
                        attr_obj["Type"] = 1  # INTEGER
                    elif isinstance(attr_obj["Value"], str):
                        attr_obj["Type"] = 2  # STRING
                    elif isinstance(attr_obj["Value"], float):
                        attr_obj["Type"] = 3  # FLOAT
                    elif isinstance(attr_obj["Value"], bool):
                        attr_obj["Type"] = 4  # BOOLEAN
                    else:
                        attr_obj["Type"] = 2  # По умолчанию STRING

                # Добавляем пустой список Constraints, если его нет
                if "Constraints" not in attr_obj:
                    attr_obj["Constraints"] = []

                attributes_array.append(attr_obj)
        elif isinstance(attributes, dict):
            # Если атрибуты в формате словаря {attr_id: value}, преобразуем в список объектов
            for attr_id, value in attributes.items():
                # Проверка, является ли значение словарем с полным описанием атрибута
                if isinstance(value, dict) and "Value" in value:
                    attr_obj = value.copy()
                    attr_obj["Id"] = attr_id

                    # Добавляем обязательные поля, если их нет
                    if "Name" not in attr_obj:
                        attr_obj["Name"] = "forvalidation"

                    if "Type" not in attr_obj:
                        # Определяем тип по значению
                        if isinstance(attr_obj["Value"], int):
                            attr_obj["Type"] = 1  # INTEGER
                        elif isinstance(attr_obj["Value"], str):
                            attr_obj["Type"] = 2  # STRING
                        elif isinstance(attr_obj["Value"], float):
                            attr_obj["Type"] = 3  # FLOAT
                        elif isinstance(attr_obj["Value"], bool):
                            attr_obj["Type"] = 4  # BOOLEAN
                        else:
                            attr_obj["Type"] = 2  # По умолчанию STRING

                    if "Constraints" not in attr_obj:
                        attr_obj["Constraints"] = []
                else:
                    # Создаем полный объект атрибута
                    attr_type = (
                        1
                        if isinstance(value, int)
                        else 2
                        if isinstance(value, str)
                        else 3
                        if isinstance(value, float)
                        else 4
                        if isinstance(value, bool)
                        else 2
                    )
                    attr_obj = {
                        "Id": attr_id,
                        "Name": "forvalidation",
                        "Type": attr_type,
                        "Value": value,
                        "Constraints": [],
                    }

                attributes_array.append(attr_obj)
        else:
            raise TypeError(f"Неподдерживаемый тип атрибутов: {type(attributes)}")

        # Формируем эндпоинт для установки атрибутов
        endpoint = f"api/objects/{object_id}/attributes"

        # Логирование запроса
        logger.debug(f"Отправка запроса на установку атрибутов: {attributes_array}")

        # Вывод атрибутов в формате JSON для отладки
        logger.debug(f"Атрибуты в JSON: {json.dumps(attributes_array, cls=CustomJSONEncoder)}")

        try:
            await self._request("PUT", endpoint, data=attributes_array)
            return True
        except Exception as e:
            logger.error(f"Не удалось установить атрибуты для объекта {object_id}: {e}")
            logger.error(f"Данные запроса: {attributes_array}")
            raise

    async def delete(self, object_id: str):
        """Удаляет объект."""
        endpoint = f"api/objects/{object_id}"
        await self._request("DELETE", endpoint)
