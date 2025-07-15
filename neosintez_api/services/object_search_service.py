"""
Сервис для выполнения поисковых запросов к API Неосинтез.
"""

import logging
from typing import TYPE_CHECKING, Any, Optional, Self
from uuid import UUID

from neosintez_api.core.enums import (
    SearchConditionType,
    SearchDirectionType,
    SearchFilterType,
    SearchLogicType,
    SearchOperatorType,
    SearchQueryMode,
)
from neosintez_api.core.exceptions import NeosintezAPIError
from neosintez_api.models import NeoObject, SearchCondition, SearchFilter, SearchRequest


if TYPE_CHECKING:
    from neosintez_api.core.client import NeosintezClient
    from neosintez_api.services.class_service import ClassService


logger = logging.getLogger(__name__)


class SearchQueryBuilder:
    """
    Построитель для создания и выполнения поисковых запросов к API Неосинтез.

    Позволяет в текучем стиле (fluent) собирать запрос и выполнять его.
    """

    def __init__(self, client: "NeosintezClient", class_service: "ClassService"):
        self._client = client
        self._class_service = class_service
        self._filters: list[SearchFilter] = []
        self._conditions: list[SearchCondition] = []
        self._class_name: Optional[str] = None

    def with_name(self, name: str) -> Self:
        """
        Добавляет условие поиска по имени объекта (регистронезависимый).

        Args:
            name: Имя объекта для поиска.
        Returns:
            Self: Для цепочки вызовов.
        """
        condition = SearchCondition(
            Type=SearchConditionType.NAME,
            Value=name,
            Operator=SearchOperatorType.EQUALS,
            Logic=SearchLogicType.NONE,
            Direction=SearchDirectionType.NONE,
        )
        self._conditions.append(condition)
        return self

    def with_class_id(self, class_id: str) -> Self:
        """Добавляет фильтр по ID класса."""
        self._filters.append(SearchFilter(Type=SearchFilterType.BY_CLASS, Value=class_id))
        return self

    def with_class_name(self, name: str) -> Self:
        """
        Задает имя класса для поиска.
        Имя будет разрешено в ID непосредственно перед выполнением запроса.

        Args:
            name: Точное имя класса для поиска.
        """
        self._class_name = name
        return self

    def with_parent_id(self, parent_id: str) -> Self:
        """Добавляет фильтр по ID родительского объекта."""
        self._filters.append(SearchFilter(Type=SearchFilterType.BY_PARENT, Value=parent_id))
        return self

    def with_attribute(
        self,
        attribute_id: str,
        value: Any,
        operator: SearchOperatorType = SearchOperatorType.EQUALS,
        logic: SearchLogicType = SearchLogicType.NONE,
    ) -> Self:
        """
        Добавляет условие поиска по значению атрибута (по ID атрибута).

        Args:
            attribute_id: ID атрибута для фильтрации.
            value: Значение атрибута для поиска.
            operator: Оператор сравнения (по умолчанию EQUALS).
            logic: Логика объединения с другими условиями (по умолчанию NONE).
        """
        condition = SearchCondition(
            Type=SearchConditionType.ATTRIBUTE,
            Value=str(value),
            Attribute=UUID(attribute_id),
            Operator=operator,
            Logic=logic,
            Direction=SearchDirectionType.NONE,
        )
        self._conditions.append(condition)
        return self

    def with_attribute_name(
        self,
        attribute_name: str,
        value: Any,
        operator: SearchOperatorType = SearchOperatorType.EQUALS,
        logic: SearchLogicType = SearchLogicType.NONE,
    ) -> Self:
        """
        Добавляет условие поиска по значению атрибута (по имени атрибута).

        Имя атрибута будет разрешено в ID атрибута в контексте выбранного класса.

        Args:
            attribute_name: Имя атрибута для фильтрации.
            value: Значение атрибута для поиска.
            operator: Оператор сравнения (по умолчанию EQUALS).
            logic: Логика объединения с другими условиями (по умолчанию NONE).
        """
        # Создаем временное условие с именем атрибута в качестве специального маркера
        # Реальный ID атрибута будет разрешен в _prepare_conditions()
        condition = SearchCondition(
            Type=SearchConditionType.ATTRIBUTE,
            Value=str(value),
            Attribute=None,  # Будет заполнено в _prepare_conditions
            Operator=operator,
            Logic=logic,
            Direction=SearchDirectionType.NONE,
        )
        # Временно сохраняем имя атрибута в Group для разрешения позже
        condition.Group = attribute_name
        self._conditions.append(condition)
        return self

    async def _prepare_filters(self) -> list[SearchFilter]:
        """
        Подготавливает финальный список фильтров, разрешая имена в ID.
        """
        filters = self._filters.copy()

        if self._class_name:
            logger.debug(f"Поиск ID для класса с именем '{self._class_name}'...")
            matching_classes = await self._class_service.find_by_name(self._class_name)
            exact_match = [cls for cls in matching_classes if cls.Name.lower() == self._class_name.lower()]

            if len(exact_match) == 0:
                raise ValueError(f"Класс с именем '{self._class_name}' не найден.")
            if len(exact_match) > 1:
                class_ids = [str(c.Id) for c in exact_match]
                raise ValueError(
                    f"Найдено несколько классов с именем '{self._class_name}'. IDs: {class_ids}. Уточните запрос."
                )

            class_id = str(exact_match[0].Id)
            logger.debug(f"Найден класс '{self._class_name}' с ID: {class_id}.")
            filters.append(SearchFilter(Type=SearchFilterType.BY_CLASS, Value=class_id))

        return filters

    async def _prepare_conditions(self) -> list[SearchCondition]:
        """
        Подготавливает финальный список условий, разрешая имена атрибутов в ID.
        """
        conditions = []

        for condition in self._conditions:
            # Проверяем, нужно ли разрешить имя атрибута в ID
            if condition.Type == SearchConditionType.ATTRIBUTE and condition.Attribute is None and condition.Group:
                attribute_name = condition.Group

                if not self._class_name:
                    raise ValueError(
                        f"Для поиска по имени атрибута '{attribute_name}' необходимо указать класс через with_class_name()"
                    )

                logger.debug(f"Поиск ID для атрибута '{attribute_name}' в классе '{self._class_name}'...")

                # Получаем класс для доступа к его атрибутам
                matching_classes = await self._class_service.find_by_name(self._class_name)
                exact_match = [cls for cls in matching_classes if cls.Name.lower() == self._class_name.lower()]

                if not exact_match:
                    raise ValueError(f"Класс с именем '{self._class_name}' не найден.")

                target_class = exact_match[0]

                # Получаем атрибуты класса
                attributes = await self._class_service.get_attributes(str(target_class.Id))
                target_attribute = next((a for a in attributes if a.Name == attribute_name), None)

                if not target_attribute:
                    available_attrs = [a.Name for a in attributes]
                    raise ValueError(
                        f"Атрибут '{attribute_name}' не найден в классе '{self._class_name}'. "
                        f"Доступные атрибуты: {available_attrs}"
                    )

                attribute_id = target_attribute.Id
                logger.debug(f"Найден ID для атрибута '{attribute_name}': {attribute_id}")

                # Создаем новое условие с правильным ID атрибута
                updated_condition = SearchCondition(
                    Type=condition.Type,
                    Value=condition.Value,
                    Attribute=attribute_id,
                    Operator=condition.Operator,
                    Logic=condition.Logic,
                    Direction=condition.Direction,
                    Contextual=condition.Contextual,
                    Group=None,  # Очищаем временное имя атрибута
                )
                conditions.append(updated_condition)
            else:
                # Условие уже готово к использованию
                conditions.append(condition)

        return conditions

    async def find_all(self) -> list[NeoObject]:
        """Выполняет поиск всех объектов по заданным фильтрам и условиям."""
        final_filters = await self._prepare_filters()
        final_conditions = await self._prepare_conditions()
        request = SearchRequest(
            Filters=final_filters,
            Conditions=final_conditions,
            Mode=SearchQueryMode.ACTUAL_ONLY,
        )
        return await self._client.objects.search_all(request)

    async def find_one(self) -> Optional[NeoObject]:
        """
        Выполняет поиск и возвращает один объект или None.

        Raises:
            NeosintezAPIError: Если найдено более одного объекта.
        """
        final_filters = await self._prepare_filters()
        final_conditions = await self._prepare_conditions()
        request = SearchRequest(
            Filters=final_filters,
            Conditions=final_conditions,
            Mode=SearchQueryMode.ACTUAL_ONLY,
        )
        all_found = await self._client.objects.search_all(request)

        if len(all_found) > 1:
            # Попытаемся найти точное совпадение по имени, если оно было в фильтрах
            name_filter = next((f for f in self._filters if f.Type == SearchFilterType.BY_NAME), None)
            if name_filter:
                exact_match = [obj for obj in all_found if obj.Name.lower() == str(name_filter.Value).lower()]
                if len(exact_match) == 1:
                    return exact_match[0]

            # Если точного совпадения нет или оно не помогло, вызываем ошибку
            object_ids = [str(o.Id) for o in all_found]
            raise NeosintezAPIError(
                status_code=409,  # Conflict
                message=f"Найдено несколько объектов ({len(all_found)}), удовлетворяющих условиям.",
                response_data={"conflicting_ids": object_ids},
            )

        return all_found[0] if all_found else None


class ObjectSearchService:
    """
    Предоставляет методы для поиска объектов в Неосинтез.
    """

    def __init__(self, client: "NeosintezClient"):
        self.client = client
        # Ленивая инициализация, чтобы не создавать сервис без необходимости
        self._class_service: Optional[ClassService] = None

    @property
    def class_service(self) -> "ClassService":
        """Возвращает экземпляр ClassService, создавая его при первом доступе."""
        if self._class_service is None:
            # Импортируем здесь, чтобы избежать циклических зависимостей
            from neosintez_api.services.class_service import ClassService

            self._class_service = ClassService(self.client)
        return self._class_service

    def query(self) -> SearchQueryBuilder:
        """
        Начинает новый поисковый запрос с помощью построителя.

        Returns:
            Экземпляр SearchQueryBuilder для построения запроса.
        """
        return SearchQueryBuilder(self.client, self.class_service)

    async def find_object_by_name_and_class(self, name: str, class_name: str) -> Optional[NeoObject]:
        """
        Находит один объект по имени и имени класса.
        """
        logger.info(f"Поиск объекта '{name}' в классе '{class_name}'")
        try:
            # Используем новый query builder с with_class_name
            return await self.query().with_name(name).with_class_name(class_name).find_one()
        except (NeosintezAPIError, ValueError) as e:
            if isinstance(e, NeosintezAPIError) and e.status_code == 409:
                logger.error(
                    f"Найдено несколько объектов с именем '{name}' в классе '{class_name}'. IDs: {e.response_data.get('conflicting_ids')}"
                )
            else:
                logger.error(f"Ошибка при поиске объекта '{name}' в классе '{class_name}'", exc_info=True)
            raise

    async def find_objects_by_class(self, class_name: str, parent_id: Optional[str] = None) -> list[NeoObject]:
        """
        Находит объекты по имени класса и опционально по ID родителя.
        """
        logger.info(f"Поиск объектов в классе '{class_name}'" + (f" у родителя '{parent_id}'" if parent_id else ""))
        try:
            # Используем новый query builder с with_class_name
            query = self.query().with_class_name(class_name)
            if parent_id:
                query.with_parent_id(parent_id)

            found_objects = await query.find_all()

            logger.info(f"Найдено {len(found_objects)} объектов.")
            return found_objects
        except (NeosintezAPIError, ValueError) as e:
            logger.error(f"Ошибка при поиске объектов: {e}", exc_info=True)
            raise
