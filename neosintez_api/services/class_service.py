"""
Сервисный слой для работы с классами объектов.
Обеспечивает удобный доступ к метаданным классов и их атрибутам.
"""

import logging
from typing import TYPE_CHECKING, List, Optional

from ..models import Attribute, EntityClass


if TYPE_CHECKING:
    from ..core.client import NeosintezClient

# Настройка логгера
logger = logging.getLogger("neosintez_api.services.class_service")


class ClassService:
    """
    Сервис для работы с классами объектов в Неосинтезе.
    Предоставляет высокоуровневые, кэшируемые методы для получения
    информации о классах и их атрибутах.
    """

    def __init__(self, client: "NeosintezClient"):
        """
        Инициализирует сервис с клиентом API.

        Args:
            client: Экземпляр клиента для взаимодействия с API.
        """
        self.client = client
        # Эти кэши будут содержать всю информацию о классах после первого запроса
        self._class_cache = {}  # type: Dict[str, EntityClass]
        self._attr_cache = {}  # type: Dict[str, List[Attribute]]
        self._cache_loaded = False

    async def _ensure_cache_loaded(self) -> None:
        """
        Проверяет, загружен ли кэш, и если нет - выполняет полную загрузку.
        Получает все классы со всеми атрибутами за один запрос.
        """
        if self._cache_loaded:
            return

        logger.info("Кэш классов пуст. Выполняется полная загрузка классов и атрибутов...")
        # Запрашиваем все классы с их атрибутами
        all_classes_data = await self.client.classes.get(exclude_attributes=False)

        for class_data in all_classes_data:
            try:
                # Валидируем и кэшируем класс
                class_model = EntityClass.model_validate(class_data)
                class_id = str(class_model.Id)
                self._class_cache[class_id] = class_model

                # Валидируем и кэшируем атрибуты
                attributes = []
                if class_data.get("Attributes"):
                    for attr_id, attr_data in class_data["Attributes"].items():
                        # Дополняем данные атрибута его ID, если его нет
                        if isinstance(attr_data, dict) and "Id" not in attr_data:
                            attr_data["Id"] = attr_id
                        attributes.append(Attribute.model_validate(attr_data))
                self._attr_cache[class_id] = attributes

            except Exception as e:
                class_id_str = class_data.get("Id", "N/A")
                logger.error(f"Ошибка при обработке данных для класса {class_id_str}: {e}")

        self._cache_loaded = True
        logger.info(f"Кэш успешно загружен. Всего классов: {len(self._class_cache)}.")

    async def get_by_id(self, class_id: str) -> Optional[EntityClass]:
        """
        Получает информацию о классе по его ID из кэша.

        Args:
            class_id: Идентификатор класса.

        Returns:
            Pydantic-модель EntityClass или None, если класс не найден.
        """
        await self._ensure_cache_loaded()
        logger.debug(f"Поиск класса по ID: {class_id} в кэше.")
        return self._class_cache.get(class_id)

    async def find_by_name(self, name: str) -> List[EntityClass]:
        """
        Находит классы в кэше, имя которых содержит указанную подстроку.
        Поиск нечувствителен к регистру.
        """
        await self._ensure_cache_loaded()
        logger.debug(f"Поиск классов по имени, содержащему: '{name}' в кэше.")

        name_lower = name.lower()
        matching_classes = [cls for cls in self._class_cache.values() if name_lower in cls.Name.lower()]

        logger.info(f"Найдено {len(matching_classes)} классов по запросу '{name}' в кэше.")
        return matching_classes

    async def find_by_names(self, names: List[str]) -> List[EntityClass]:
        """
        Находит классы в кэше по списку точных имен.
        Поиск чувствителен к регистру для точного совпадения.

        Args:
            names: Список точных имен классов для поиска.

        Returns:
            Список найденных классов.
        """
        await self._ensure_cache_loaded()
        logger.debug(f"Поиск классов по точным именам: {names} в кэше.")

        # Создаем множество имен для быстрого поиска
        names_set = {name.lower() for name in names}
        matching_classes = []

        for cls in self._class_cache.values():
            if cls.Name.lower() in names_set:
                matching_classes.append(cls)

        logger.info(f"Найдено {len(matching_classes)} классов по запросу {names} в кэше.")
        return matching_classes

    async def get_all(self) -> List[EntityClass]:
        """
        Получает все классы, доступные в системе, из кэша.
        """
        await self._ensure_cache_loaded()
        logger.debug("Запрос всех классов из кэша.")
        return list(self._class_cache.values())

    async def get_attributes(self, class_id: str) -> List[Attribute]:
        """
        Получает список атрибутов для указанного класса из кэша.
        """
        await self._ensure_cache_loaded()
        logger.debug(f"Запрос атрибутов для класса с ID: {class_id} из кэша.")
        return self._attr_cache.get(class_id, [])
