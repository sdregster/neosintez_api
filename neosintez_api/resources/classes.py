"""
Ресурсный класс для работы с классами "Классы объектов" в API Неосинтез.
"""

import logging
from typing import Any, Dict, List, Optional

from ..exceptions import ApiError
from ..models import Attribute, EntityClass
from ..services.cache import TTLCache
from .base import BaseResource


# Настройка логгера
logger = logging.getLogger("neosintez_api.resources.classes")


class ClassesResource(BaseResource):
    """
    Ресурсный класс для работы с классами "Классы объектов" в API Неосинтез.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # TTL кэш для атрибутов классов с автоматической инвалидацией (30 минут)
        self._attr_cache = TTLCache[List[Attribute]](default_ttl=1800, max_size=200)

    async def get(self, exclude_attributes: bool = False) -> list[dict[str, Any]]:
        """
        Получает список классов объектов из API.

        Args:
            exclude_attributes: Если True, возвращает классы без атрибутов и вьюэров (параметр only=true).
                                 По умолчанию False, возвращает классы с атрибутами.

        Returns:
            list[dict[str, Any]]: Список словарей с данными классов.
        """
        endpoint = "api/structure/entities"
        params = {"only": str(exclude_attributes).lower()}

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
            all_classes = await self.get(exclude_attributes=True)
            logger.debug(f"Получено {len(all_classes)} классов для поиска '{name}'")

            # Фильтруем классы по имени (нечувствительно к регистру)
            name_lower = name.lower()
            matches = []

            for cls_data in all_classes:
                # Используем .get() для безопасного доступа к ключу
                class_name = cls_data.get("Name", "")
                class_id = cls_data.get("Id")
                if class_id and name_lower in class_name.lower():
                    matches.append({"id": str(class_id), "name": class_name})

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
        Получает список атрибутов для указанного класса объектов с кэшированием.

        Args:
            class_id: Идентификатор класса объектов

        Returns:
            List[Attribute]: Список атрибутов класса
        """
        class_id = str(class_id)
        cached_attributes = self._attr_cache.get(class_id)
        if cached_attributes is not None:
            logger.debug(f"Атрибуты для класса {class_id} найдены в кэше.")
            return cached_attributes

        logger.debug(f"Получение атрибутов для класса {class_id} из API.")
        attributes = await self._fetch_attributes(class_id)

        self._attr_cache.set(class_id, attributes)
        logger.debug(f"Атрибуты для класса {class_id} сохранены в кэш.")

        return attributes

    async def _fetch_attributes(self, class_id: str) -> List[Attribute]:
        """
        Получает список атрибутов для указанного класса объектов.
        Вынесено для удобства кэширования.
        """
        # Новая реализация: получаем все классы с атрибутами, затем фильтруем нужный
        try:
            # Сначала попробуем получить все классы с атрибутами
            all_classes = await self.get(exclude_attributes=False)

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

    def invalidate_attributes_cache(self, class_id: str) -> None:
        """Инвалидирует кэш атрибутов для указанного класса."""
        self._attr_cache.remove(str(class_id))
        logger.info(f"Кэш атрибутов для класса {class_id} инвалидирован.")

    def clear_attributes_cache(self) -> None:
        """Очищает весь кэш атрибутов."""
        self._attr_cache.clear()
        logger.info("Весь кэш атрибутов очищен.")
