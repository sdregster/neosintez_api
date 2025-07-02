"""
Сервис для выполнения поисковых запросов к API Неосинтез.
"""

import logging
from typing import TYPE_CHECKING, Optional

from neosintez_api.core.exceptions import NeosintezAPIError
from neosintez_api.models import NeoObject, SearchFilter, SearchRequest


if TYPE_CHECKING:
    from neosintez_api.core.client import NeosintezClient


logger = logging.getLogger(__name__)


class ObjectSearchService:
    """
    Предоставляет методы для поиска объектов в Неосинтез.
    """

    def __init__(self, client: "NeosintezClient"):
        self.client = client

    async def find_object_by_name_and_class(self, name: str, class_id: str) -> Optional[NeoObject]:
        """
        Находит один объект по имени и ID класса.
        Сначала выполняется поиск по API, затем результаты фильтруются
        для нахождения точного совпадения по имени.

        Args:
            name: Имя объекта для поиска.
            class_id: ID класса, в котором производится поиск.

        Returns:
            Найденный объект или None, если ничего не найдено.

        Raises:
            NeosintezAPIError: Если найдено более одного объекта с точным именем.
        """
        logger.info(f"Поиск объекта '{name}' в классе '{class_id}'")
        try:
            request = SearchRequest(
                Filters=[
                    SearchFilter(Type=2, Value=name),  # Поиск по имени (содержит)
                    SearchFilter(Type=5, Value=class_id),  # Поиск по классу
                ]
            )
            # Сначала ищем по API. API может вернуть несколько результатов (поиск по подстроке)
            all_found_objects = await self.client.objects.search_all(request)

            # Теперь фильтруем по точному совпадению имени
            exact_match_objects = [obj for obj in all_found_objects if obj.Name.lower() == name.lower()]

            if len(exact_match_objects) > 1:
                # Даже после точной фильтрации нашли несколько - это дубликаты в системе
                object_ids = [str(o.Id) for o in exact_match_objects]
                logger.error(
                    f"Найдено несколько объектов ({len(exact_match_objects)}) с точным именем '{name}' в классе '{class_id}'. IDs: {object_ids}"
                )
                raise NeosintezAPIError(
                    status_code=409,  # Conflict
                    message=f"Найдено несколько объектов ({len(exact_match_objects)}) с точным именем '{name}' в классе '{class_id}'.",
                    response_data={"conflicting_ids": object_ids},
                )

            if not exact_match_objects:
                logger.warning(
                    f"Объект с точным именем '{name}' не найден в классе '{class_id}' среди {len(all_found_objects)} результатов."
                )
                return None

            found_object = exact_match_objects[0]
            logger.info(f"Найден объект '{found_object.Name}' с ID '{found_object.Id}'")
            return found_object

        except Exception:
            logger.error(
                f"Ошибка при поиске объекта '{name}' в классе '{class_id}'",
                exc_info=True,
            )
            raise

    async def find_objects_by_class(self, class_id: str, parent_id: Optional[str] = None) -> list[NeoObject]:
        """
        Находит объекты по ID класса и опционально по ID родителя.

        Args:
            class_id: ID класса для поиска.
            parent_id: ID родительского объекта для ограничения поиска (опционально).

        Returns:
            Список найденных объектов.
        """
        logger.info(f"Поиск объектов в классе '{class_id}'" + (f" у родителя '{parent_id}'" if parent_id else ""))

        # В SearchFilter Type: 5 = ByClass, 4 = ByParent
        search_filters = [
            SearchFilter(Type=5, Value=str(class_id)),
        ]
        if parent_id:
            search_filters.append(SearchFilter(Type=4, Value=str(parent_id)))

        request = SearchRequest(Filters=search_filters)

        try:
            found_objects = await self.client.objects.search_all(request)
            logger.info(f"Найдено {len(found_objects)} объектов.")
            return found_objects
        except Exception as e:
            logger.error(f"Ошибка при поиске объектов: {e}")
            raise
