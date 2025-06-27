"""
Ресурсный класс для работы с классами "Классы объектов" в API Неосинтез.
"""

import logging
from typing import Any, Dict, List, Optional

from ..exceptions import ApiError
from ..models import Attribute, EntityClass
from .base import BaseResource


# Настройка логгера
logger = logging.getLogger("neosintez_api.resources.classes")


class ClassesResource(BaseResource):
    """
    Ресурсный класс для работы с классами "Классы объектов" в API Неосинтез.
    """

    async def get_all(self, only_top_level: bool = False) -> List[EntityClass]:
        """
        Получает список классов объектов из API.

        Args:
            only_top_level: Если True, возвращает только классы верхнего уровня

        Returns:
            List[EntityClass]: Список моделей классов
        """
        endpoint = "api/structure/entities"
        params = {"only": str(only_top_level).lower()}

        result = await self._request("GET", endpoint, params=params)
        if isinstance(result, list):
            return [EntityClass.model_validate(item) for item in result]
        return []

    async def get_all_with_attributes(self) -> List[Dict[str, Any]]:
        """
        Получает список классов объектов вместе с их атрибутами.

        Returns:
            List[Dict[str, Any]]: Список классов с атрибутами
        """
        endpoint = "api/structure/entities"
        params = {"only": "false"}  # Параметр, чтобы получить атрибуты вместе с классами

        result = await self._request("GET", endpoint, params=params)
        if isinstance(result, list):
            return result
        return []

    async def get_classes_by_name(self, name: str) -> List[Dict[str, Any]]:
        """
        Ищет классы по имени среди всех классов в API.

        Args:
            name: Название класса или его часть

        Returns:
            List[Dict[str, Any]]: Список найденных классов
        """
        try:
            # Получаем все классы
            all_classes = await self.get_all()
            logger.debug(f"Получено {len(all_classes)} классов для поиска '{name}'")

            # Фильтруем классы по имени (нечувствительно к регистру)
            name_lower = name.lower()
            matches = []

            for cls in all_classes:
                if name_lower in cls.Name.lower():
                    matches.append({"id": str(cls.Id), "name": cls.Name})

            logger.debug(f"Найдено {len(matches)} классов с именем, содержащим '{name}'")
            return matches

        except Exception as e:
            logger.error(f"Ошибка при поиске классов по имени '{name}': {e!s}")
            return []

    async def get_by_id(self, entity_id: str) -> Optional[EntityClass]:
        """
        Получает информацию о классе объектов по его идентификатору.

        Args:
            entity_id: Идентификатор класса объектов

        Returns:
            Optional[EntityClass]: Информация о классе объектов или None, если класс не найден
        """
        endpoint = f"api/structure/entities/{entity_id}"

        try:
            result = await self._request("GET", endpoint)
            if isinstance(result, dict):
                return EntityClass.model_validate(result)
        except Exception:
            return None

        return None

    async def get_children(self, parent_id: str) -> List[EntityClass]:
        """
        Получает список дочерних классов для указанного родительского класса.

        Args:
            parent_id: Идентификатор родительского класса

        Returns:
            List[EntityClass]: Список дочерних классов
        """
        endpoint = f"api/structure/entities/{parent_id}/children"

        result = await self._request("GET", endpoint)
        if isinstance(result, list):
            return [EntityClass.model_validate(item) for item in result]
        return []

    async def get_attributes(self, class_id: str) -> List[Attribute]:
        """
        Получает список атрибутов для указанного класса объектов.

        Args:
            class_id: Идентификатор класса объектов

        Returns:
            List[Attribute]: Список атрибутов класса
        """
        # Новая реализация: получаем все классы с атрибутами, затем фильтруем нужный
        try:
            # Сначала попробуем получить все классы с атрибутами
            all_classes = await self.get_all_with_attributes()

            # Найдем нужный класс по ID
            for class_data in all_classes:
                if str(class_data.get("Id")) == class_id:
                    # Извлекаем атрибуты из класса
                    attributes = []
                    if class_data.get("Attributes"):
                        for attr_id, attr_data in class_data["Attributes"].items():
                            try:
                                # Создаем базовую структуру атрибута
                                attr_dict = {"Id": attr_id}

                                # Если attr_data - словарь, копируем все его поля
                                if isinstance(attr_data, dict):
                                    attr_dict.update(attr_data)
                                # Если attr_data - число (скорее всего тип атрибута), сохраняем как Type
                                elif isinstance(attr_data, (int, float)):
                                    attr_dict["Type"] = int(attr_data)
                                # В других случаях просто добавляем автоматическое имя
                                else:
                                    attr_dict["Name"] = f"Attribute {attr_id}"

                                # Если имя не задано, добавляем его
                                if "Name" not in attr_dict:
                                    attr_dict["Name"] = f"Attribute {attr_id}"

                                # Создаем объект атрибута
                                attributes.append(Attribute.model_validate(attr_dict))
                            except Exception as e:
                                logger.error(f"Ошибка при обработке атрибута {attr_id}: {e!s}")
                                # Добавляем минимальную информацию об атрибуте
                                attributes.append(Attribute(Id=attr_id, Name=f"Attribute {attr_id}"))

                    return attributes

            # Если класс не найден или у него нет атрибутов, пробуем получить атрибуты через общий эндпоинт
            return await self._get_attributes_from_common_endpoint(class_id)

        except Exception as e:
            logger.error(f"Ошибка при получении атрибутов класса {class_id}: {e!s}")
            # Пробуем получить атрибуты через общий эндпоинт как запасной вариант
            return await self._get_attributes_from_common_endpoint(class_id)

    async def _get_attributes_from_common_endpoint(self, class_id: str) -> List[Attribute]:
        """
        Получает атрибуты класса через общий эндпоинт атрибутов.

        Args:
            class_id: Идентификатор класса

        Returns:
            List[Attribute]: Список атрибутов класса
        """
        try:
            # Получаем все атрибуты
            endpoint = "api/attributes"
            result = await self._request("GET", endpoint)

            if isinstance(result, dict) and "Result" in result:
                all_attributes = result["Result"]
                # Фильтруем атрибуты по EntityId
                class_attributes = []

                for attr in all_attributes:
                    try:
                        if attr.get("EntityId") and str(attr["EntityId"]) == class_id:
                            class_attributes.append(Attribute.model_validate(attr))
                    except Exception as e:
                        logger.error(f"Ошибка при обработке атрибута через общий эндпоинт: {e!s}")

                return class_attributes
            return []
        except Exception as e:
            logger.error(f"Ошибка при получении атрибутов через общий эндпоинт для класса {class_id}: {e!s}")
            return []

    async def find_by_name(self, class_name: str) -> str:
        """
        Находит класс по имени.

        Args:
            class_name: Имя класса для поиска

        Returns:
            str: ID найденного класса

        Raises:
            ApiError: Если класс не найден
        """
        classes = await self.get_classes_by_name(class_name)
        if not classes:
            raise ApiError(404, f"Класс '{class_name}' не найден", None)

        # Возвращаем ID первого найденного класса
        return classes[0]["id"]
