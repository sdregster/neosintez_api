"""
Сервисы-помощники для разрешения (resolving) различных сущностей.
Например, для преобразования строковых значений атрибутов в ID.
"""

from time import perf_counter
from typing import TYPE_CHECKING, Optional

from neosintez_api.services.cache import TTLCache


if TYPE_CHECKING:
    from neosintez_api.core.client import NeosintezClient
    from neosintez_api.models import Attribute

from neosintez_api.services.object_search_service import ObjectSearchService


class AttributeResolver:
    """
    Отвечает за "разрешение" значений атрибутов.
    Например, находит ID для строкового значения ссылочного атрибута.
    """

    _link_cache: TTLCache[object] = TTLCache(default_ttl=3600, max_size=10_000)
    _LINK_NOT_FOUND = object()

    def __init__(self, client: "NeosintezClient"):
        self.search_service = ObjectSearchService(client)

    def _make_key(self, cls_id: str, root_id: str | None, value: str) -> str:
        """Создает стандартизированный ключ для кэша ссылок."""
        return f"{cls_id}|{root_id or ''}|{value.lower()}"

    async def resolve_link_attribute_as_object(self, attr_meta: "Attribute", attr_value: str) -> dict:
        """
        Находит объект для ссылочного атрибута по его строковому значению.
        Результаты кэшируются для ускорения повторных вызовов.

        Args:
            attr_meta: Метаданные атрибута, из которых берутся ограничения.
            attr_value: Строковое значение, которое нужно найти (например, "Да").

        Returns:
            Словарь с Id и Name найденного объекта.

        Raises:
            ValueError: Если не удалось найти объект или метаданные некорректны.
        """

        def get_constraint_ids() -> (Optional[str], Optional[str]):
            """
            Извлекает ID класса и ID корневого объекта из ограничений.
            Возвращает (class_id, root_id)
            """
            linked_class_id, parent_id = None, None
            if not hasattr(attr_meta, "Constraints") or not isinstance(attr_meta.Constraints, list):
                return None, None

            for constraint in attr_meta.Constraints:
                if constraint.Type == 1 and constraint.EntityId:
                    linked_class_id = str(constraint.EntityId)
                elif constraint.Type == 3 and constraint.ObjectRootId:
                    parent_id = str(constraint.ObjectRootId)
            return linked_class_id, parent_id

        linked_class_id, parent_id = get_constraint_ids()

        if not linked_class_id:
            raise ValueError(
                f"Не удалось извлечь ID класса справочника (Constraint Type 1) для атрибута '{attr_meta.Name}'"
            )

        # Проверяем кэш перед выполнением дорогостоящего поиска
        key = self._make_key(linked_class_id, parent_id, attr_value)
        cached_result = self._link_cache.get(key)
        if cached_result is self._LINK_NOT_FOUND:
            raise ValueError(
                f"Не удалось найти связанный объект с именем '{attr_value}' для атрибута '{attr_meta.Name}'."
            )
        if cached_result is not None:
            return cached_result

        resolve_started_at = perf_counter()
        query = self.search_service.query().with_class_id(linked_class_id)
        if parent_id:
            query.with_parent_id(parent_id)

        possible_options = await query.find_all()
        resolve_duration = perf_counter() - resolve_started_at

        if resolve_duration >= 1.0:
            print(
                "[IMPORT PROFILING] slow link resolve: "
                f"attribute='{attr_meta.Name}', value='{attr_value}', class_id='{linked_class_id}', "
                f"root_id='{parent_id}', candidates={len(possible_options)}, duration={resolve_duration:.2f}s"
            )

        found_option = next(
            (option for option in possible_options if option.Name.lower() == attr_value.lower()),
            None,
        )

        if found_option:
            result = {"Id": str(found_option.Id), "Name": found_option.Name}
            # Сохраняем успешный результат в кэш
            self._link_cache.set(key, result)
            return result
        else:
            # Кэшируем отрицательный результат, чтобы не сканировать
            # один и тот же большой справочник повторно в рамках TTL.
            self._link_cache.set(key, self._LINK_NOT_FOUND)
            raise ValueError(
                f"Не удалось найти связанный объект с именем '{attr_value}' для атрибута '{attr_meta.Name}'."
            )
