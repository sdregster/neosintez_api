"""
Маппер для преобразования между Pydantic-моделями и API-представлением объектов.
"""

import logging
from typing import Any, Dict, List

from pydantic import BaseModel

from ...core.enums import WioAttributeType
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

                attr_type_val = attr_meta.get("Type")
                value = getattr(model, field_name)

                if attr_type_val is not None and attr_type_val == WioAttributeType.FILE:
                    # Файловый атрибут: ожидаем dict с нужными ключами
                    if isinstance(value, dict):
                        required_keys = {"Id", "Name", "Extension", "Size", "MediaType", "TempToken"}
                        if required_keys.issubset(value.keys()):
                            attr_body = build_attribute_body(attr_meta, value)
                            attributes.append(attr_body)
                            if logger.isEnabledFor(logging.DEBUG):
                                logger.debug(
                                    f"Подготовлен файловый атрибут '{alias}' (поле: {field_name}) со значением: {value}"
                                )
                        else:
                            logger.error(
                                f"Файловый атрибут '{alias}' (поле: {field_name}) содержит некорректный dict: {value}. Пропущен."
                            )
                        continue
                    elif isinstance(value, str):
                        logger.error(
                            f"Файловый атрибут '{alias}' (поле: {field_name}) содержит строку вместо dict (ошибка обработки). Пропущен."
                        )
                        continue
                    elif value is None:
                        continue
                    else:
                        logger.error(
                            f"Файловый атрибут '{alias}' (поле: {field_name}) имеет неподдерживаемый тип: {type(value)}. Пропущен."
                        )
                        continue
                # Обычные атрибуты
                if value is not None:
                    attr_body = build_attribute_body(attr_meta, value)
                    attributes.append(attr_body)
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug(f"Подготовлен атрибут '{alias}' (поле: {field_name}) со значением: {value}")
            else:
                logger.warning(f"Атрибут '{alias}' (поле: {field_name}) не найден в метаданных класса.")

        return attributes
