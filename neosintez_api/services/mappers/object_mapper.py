"""
Маппер для преобразования между Pydantic-моделями и API-представлением объектов.
"""

import logging
from typing import Any, Dict, List, Type, TypeVar

from pydantic import BaseModel

from ...utils import build_attribute_body


T = TypeVar("T", bound=BaseModel)
logger = logging.getLogger("neosintez_api.services.mappers.object_mapper")


class ObjectMapper:
    @staticmethod
    async def model_to_attributes(model: BaseModel, attr_meta_by_name: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Преобразует модель в список атрибутов для API.

        Args:
            model: Pydantic-модель объекта
            attr_meta_by_name: Словарь метаданных атрибутов по имени

        Returns:
            List[Dict[str, Any]]: Список атрибутов для API в формате [{"Id": "...", "Value": "..."}, ...]
        """
        attributes = []
        model_data = model.model_dump(by_alias=True)

        for attr_name, value in model_data.items():
            if attr_name == "Name" or value is None:
                continue

            if attr_name in attr_meta_by_name:
                attr_meta = attr_meta_by_name[attr_name]
                attr_id = attr_meta.get("Id") if isinstance(attr_meta, dict) else getattr(attr_meta, "Id", None)

                if attr_id:
                    # Конвертируем UUID в строку если необходимо
                    attr_id_str = str(attr_id)

                    # Используем build_attribute_body для правильного форматирования
                    attr_obj = build_attribute_body(attr_meta, value)

                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug(f"Добавлен атрибут {attr_name}={value}")

                    attributes.append(attr_obj)
                else:
                    logger.warning(f"Атрибут {attr_name} не имеет ID в метаданных")
            else:
                logger.warning(f"Атрибут {attr_name} не найден в метаданных класса")

        return attributes

    @staticmethod
    def api_to_model(model_class: Type[T], object_data: Dict[str, Any]) -> T:
        """
        Преобразует данные API в модель.

        Args:
            model_class: Класс модели
            object_data: Данные объекта из API

        Returns:
            T: Экземпляр модели
        """
        model_data = {"Name": object_data.get("Name", "")}

        # Обрабатываем атрибуты из объекта API
        if object_data.get("Attributes"):
            for attr_id, attr_data in object_data["Attributes"].items():
                if isinstance(attr_data, dict) and "Name" in attr_data and "Value" in attr_data:
                    attr_name = attr_data["Name"]
                    attr_value = attr_data["Value"]

                    if attr_value is not None:
                        # Поиск поля в модели по имени или алиасу
                        for field_name, field_info in model_class.model_fields.items():
                            if field_info.alias == attr_name or field_name == attr_name:
                                model_data[field_name] = attr_value
                                if logger.isEnabledFor(logging.DEBUG):
                                    logger.debug(f"Установлено поле {field_name}={attr_value}")
                                break

        return model_class(**model_data)
