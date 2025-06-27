"""
Ресурсный класс для работы с атрибутами в API Неосинтез.
"""

import logging
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from ..models import Attribute, AttributeListResponse
from .base import BaseResource


class AttributesResource(BaseResource):
    """
    Ресурсный класс для работы с атрибутами в API Неосинтез.
    """

    def __init__(self, client):
        """
        Инициализирует ресурс с родительским клиентом.

        Args:
            client: Экземпляр NeosintezClient
        """
        super().__init__(client)
        self._logger = logging.getLogger("neosintez_api")

    async def get_all(self) -> List[Attribute]:
        """
        Получает список атрибутов из API.

        Returns:
            List[Attribute]: Список моделей атрибутов
        """
        endpoint = "api/attributes"

        result = await self._request("GET", endpoint)
        if isinstance(result, dict) and "Result" in result:
            # Используем модель AttributeListResponse для валидации и преобразования данных
            response = AttributeListResponse.model_validate(result)
            return response.Result
        return []

    async def get_by_id(self, attribute_id: Union[str, UUID]) -> Optional[Attribute]:
        """
        Получает информацию об атрибуте по его идентификатору.

        Args:
            attribute_id: Идентификатор атрибута

        Returns:
            Optional[Attribute]: Информация об атрибуте или None, если атрибут не найден
        """
        endpoint = f"api/attributes/{attribute_id}"

        try:
            result = await self._request("GET", endpoint)
            if isinstance(result, dict):
                return Attribute.model_validate(result)
        except Exception:
            return None

        return None

    async def get_for_entity(self, entity_id: Union[str, UUID]) -> List[Attribute]:
        """
        Получает список атрибутов для указанного класса сущности.

        Args:
            entity_id: Идентификатор класса сущности

        Returns:
            List[Attribute]: Список атрибутов для класса
        """
        endpoint = f"api/structure/entities/{entity_id}/attributes"

        try:
            result = await self._request("GET", endpoint)
            if isinstance(result, list):
                return [Attribute.model_validate(item) for item in result]
        except Exception as e:
            self._logger.error(f"Ошибка при получении атрибутов для сущности: {e!s}")
        return []

    async def update_values(
        self,
        object_id: Union[str, UUID],
        attributes_values: Dict[str, Any],
    ) -> bool:
        """
        Обновляет значения атрибутов для указанного объекта.

        DEPRECATED: Этот метод устарел и может работать некорректно.
        Используйте вместо него метод set_attributes.

        Args:
            object_id: Идентификатор объекта
            attributes_values: Словарь со значениями атрибутов (ID атрибута -> значение)

        Returns:
            bool: True, если обновление успешно
        """
        self._logger.warning(
            "Метод update_values устарел и может работать некорректно. Используйте вместо него метод set_attributes."
        )
        endpoint = f"api/objects/{object_id}/attributes"

        await self._request("PUT", endpoint, data=attributes_values)
        return True

    async def set_attributes(
        self,
        object_id: Union[str, UUID],
        attributes: List[Dict[str, Any]],
    ) -> bool:
        """
        Устанавливает атрибуты для указанного объекта.

        Каждый атрибут в списке должен содержать следующие поля:
        - Id: UUID атрибута
        - Name: Имя атрибута
        - Type: Тип атрибута (число)
        - Value: Значение атрибута

        Пример:
        ```python
        attributes = [
            {
                "Id": "12edafe4-ca98-ef11-91c1-005056b6948b",
                "Name": "Описание",
                "Type": 1,  # String
                "Value": "Значение атрибута"
            }
        ]
        ```

        Args:
            object_id: Идентификатор объекта
            attributes: Список атрибутов для установки

        Returns:
            bool: True, если атрибуты успешно установлены
        """
        endpoint = f"api/objects/{object_id}/attributes"

        try:
            await self._request("PUT", endpoint, data=attributes)
            self._logger.info(f"Атрибуты объекта {object_id} успешно обновлены")
            return True
        except Exception as e:
            self._logger.error(f"Ошибка при установке атрибутов объекта {object_id}: {e!s}")
            return False

    async def get_value(self, object_id: Union[str, UUID], attribute_id: Union[str, UUID]) -> Optional[Any]:
        """
        Получает значение атрибута для указанного объекта.

        Args:
            object_id: Идентификатор объекта
            attribute_id: Идентификатор атрибута

        Returns:
            Optional[Any]: Значение атрибута или None, если атрибут не найден
        """
        endpoint = f"api/objects/{object_id}/attributes/{attribute_id}"

        try:
            result = await self._request("GET", endpoint)
            if isinstance(result, dict) and "Value" in result:
                return result["Value"]
        except Exception as e:
            self._logger.error(f"Ошибка при получении значения атрибута {attribute_id} для объекта {object_id}: {e!s}")

        return None
