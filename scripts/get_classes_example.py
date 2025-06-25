"""
Скрипт для получения списка классов из Neosintez.
"""

import asyncio
import json
import logging
from typing import List
from uuid import UUID

from dotenv import load_dotenv

from neosintez_api.client import NeosintezClient
from neosintez_api.config import load_settings
from neosintez_api.exceptions import NeosintezAuthError, NeosintezConnectionError
from neosintez_api.models import EntityClass

load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("neosintez_classes")


class UUIDEncoder(json.JSONEncoder):
    """
    JSON-encoder для сериализации UUID.
    """

    def default(self, obj):
        if isinstance(obj, UUID):
            # Если объект - UUID, преобразуем его в строку
            return str(obj)
        return super().default(obj)


async def get_classes() -> List[EntityClass]:
    """
    Получает список классов из Neosintez.

    Returns:
        Список классов
    """
    # Загрузка настроек из переменных окружения
    settings = load_settings()
    logger.info(f"Загружены настройки для подключения к {settings.base_url}")

    # Инициализация клиента API
    async with NeosintezClient(settings) as client:
        try:
            # Аутентификация
            logger.info("Попытка аутентификации...")
            token = await client.auth()
            logger.info(f"Получен токен: {token[:10]}...")

            # Получение списка классов
            logger.info("Получение списка классов...")
            entities = await client.classes.get_all()
            logger.info(f"Получено {len(entities)} классов")

            # Сохраняем результат в файл для анализа
            with open("data/classes.json", "w", encoding="utf-8") as f:
                json.dump(
                    [
                        {
                            "Id": str(entity.Id),
                            "Name": entity.Name,
                            "Description": entity.Description,
                        }
                        for entity in entities
                    ],
                    f,
                    ensure_ascii=False,
                    indent=4,
                )

            logger.info("Список классов сохранен в data/classes.json")

            # Поиск классов по имени
            search_terms = ["Документ", "Папка", "документ", "папка"]
            found_classes = []

            for term in search_terms:
                for entity in entities:
                    if term in entity.Name:
                        found_classes.append(entity)

            # Выводим найденные классы
            logger.info(
                f"Найдено {len(found_classes)} классов по запросу {search_terms}:"
            )
            for entity in found_classes:
                logger.info(f"  {entity.Name} (ID: {entity.Id})")

            return entities

        except NeosintezAuthError as e:
            logger.error(f"Ошибка аутентификации: {str(e)}")
        except NeosintezConnectionError as e:
            logger.error(f"Ошибка соединения: {str(e)}")
        except Exception as e:
            logger.error(f"Неожиданная ошибка: {str(e)}")

    return []


async def main():
    """
    Основная функция.
    """
    await get_classes()


if __name__ == "__main__":
    asyncio.run(main())
