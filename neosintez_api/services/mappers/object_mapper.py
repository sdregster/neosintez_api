"""
Маппер для преобразования между Pydantic-моделями и API-представлением объектов.
"""

import logging
from typing import Any, Dict, List

from pydantic import BaseModel

from ...utils import build_attribute_body


logger = logging.getLogger("neosintez_api.services.mappers.object_mapper")


class ObjectMapper:
    @staticmethod
    async def model_to_attributes(model: BaseModel, attr_meta_by_name: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Преобразует Pydantic-модель в список атрибутов для API.
        Игнорирует стандартные поля (id, name, class_id, parent_id).

        Args:
            model: Экземпляр Pydantic-модели объекта.
            attr_meta_by_name: Словарь метаданных атрибутов по их оригинальному имени (алиасу).

        Returns:
            Список атрибутов для API в формате [{"Id": "...", "Value": "..."}, ...].
        """
        attributes = []
        model_fields = model.__class__.model_fields
        standard_fields = {"id", "name", "class_id", "parent_id"}

        for field_name, field_info in model_fields.items():
            # Пропускаем системные поля, которые не являются атрибутами
            if field_name.startswith("_"):
                continue

            # Пропускаем стандартные поля, которые не являются атрибутами
            if field_name in standard_fields:
                continue

            # Алиас - это оригинальное имя атрибута в Неосинтезе
            alias = field_info.alias
            if not alias:
                logger.warning(f"Поле '{field_name}' не имеет алиаса и будет проигнорировано.")
                continue

            if alias in attr_meta_by_name:
                attr_meta = attr_meta_by_name[alias]
                # Получаем значение поля из модели
                value = getattr(model, field_name)

                if value is not None:
                    attr_body = build_attribute_body(attr_meta, value)
                    attributes.append(attr_body)
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug(f"Подготовлен атрибут '{alias}' (поле: {field_name}) со значением: {value}")
            else:
                logger.warning(f"Атрибут '{alias}' (поле: {field_name}) не найден в метаданных класса.")

        return attributes
