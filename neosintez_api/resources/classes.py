"""
Ресурсный класс для работы с классами "Классы объектов" в API Неосинтез.
"""

import logging
from typing import List, Optional, Any, Dict

from ..models import EntityClass, Attribute, AttributeListResponse
from .base import BaseResource


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
                    if "Attributes" in class_data and class_data["Attributes"]:
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
                                logging.error(f"Ошибка при обработке атрибута {attr_id}: {str(e)}")
                                # Добавляем минимальную информацию об атрибуте
                                attributes.append(Attribute(Id=attr_id, Name=f"Attribute {attr_id}"))
                                
                    return attributes
            
            # Если класс не найден или у него нет атрибутов, пробуем получить атрибуты через общий эндпоинт
            return await self._get_attributes_from_common_endpoint(class_id)
            
        except Exception as e:
            logging.error(f"Ошибка при получении атрибутов класса {class_id}: {str(e)}")
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
                        logging.error(f"Ошибка при обработке атрибута через общий эндпоинт: {str(e)}")
                
                return class_attributes
            return []
        except Exception as e:
            logging.error(f"Ошибка при получении атрибутов через общий эндпоинт для класса {class_id}: {str(e)}")
            return []
