"""
Сервисы-помощники для разрешения (resolving) различных сущностей.
Например, для преобразования строковых значений атрибутов в ID.
"""

from typing import TYPE_CHECKING, Optional


if TYPE_CHECKING:
    from neosintez_api.core.client import NeosintezClient
    from neosintez_api.models import Attribute

from neosintez_api.services.object_search_service import ObjectSearchService


class AttributeResolver:
    """
    Отвечает за "разрешение" значений атрибутов.
    Например, находит ID для строкового значения ссылочного атрибута.
    """

    def __init__(self, client: "NeosintezClient"):
        self.search_service = ObjectSearchService(client)

    async def resolve_link_attribute_as_object(self, attr_meta: "Attribute", attr_value: str) -> dict:
        """
        Находит объект для ссылочного атрибута по его строковому значению.

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

        possible_options = await self.search_service.find_objects_by_class(
            class_id=linked_class_id, parent_id=parent_id
        )

        found_option = next(
            (option for option in possible_options if option.Name.lower() == attr_value.lower()),
            None,
        )

        if found_option:
            return {"Id": str(found_option.Id), "Name": found_option.Name}
        else:
            raise ValueError(
                f"Не удалось найти связанный объект с именем '{attr_value}' для атрибута '{attr_meta.Name}'."
            )
