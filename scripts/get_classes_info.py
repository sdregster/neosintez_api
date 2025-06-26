#!/usr/bin/env python
"""
Скрипт для получения информации о всех классах объектов в системе Neosintez.
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict, List
from uuid import UUID

# Загрузка переменных окружения из .env файла
from dotenv import load_dotenv

from neosintez_api.client import NeosintezClient
from neosintez_api.config import load_settings
from neosintez_api.exceptions import NeosintezAuthError, NeosintezConnectionError


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


async def get_all_classes(save_to_file: bool = True) -> Dict[str, Any]:
    """
    Получает список всех классов объектов в Neosintez с их основными характеристиками.

    Args:
        save_to_file: Сохранять ли результаты в JSON-файл

    Returns:
        Dict с информацией о всех классах
    """
    # Загрузка настроек из переменных окружения
    settings = load_settings()
    logger.info(f"Загружены настройки для подключения к {settings.base_url}")

    result = {
        "total_classes": 0,
        "classes": [],
    }

    # Инициализация клиента API
    async with NeosintezClient(settings) as client:
        try:
            # Аутентификация
            logger.info("Попытка аутентификации...")
            token = await client.auth()
            logger.info(f"Получен токен: {token[:10]}...")

            # Получение списка всех классов объектов
            logger.info("Получение списка классов объектов из Neosintez")
            entities = await client.classes.get_all()
            logger.info(f"Получено {len(entities)} классов")

            result["total_classes"] = len(entities)

            # Преобразование классов в список словарей для JSON
            classes_list = []
            for entity in entities:
                entity_dict = {
                    "id": str(entity.Id),
                    "name": entity.Name,
                    "description": getattr(entity, "Description", ""),
                }
                classes_list.append(entity_dict)

            # Сортируем классы по имени для удобства
            classes_list.sort(key=lambda x: x["name"])
            result["classes"] = classes_list

            # Сохраняем результаты в файл
            if save_to_file:
                output_dir = Path("data")
                output_dir.mkdir(exist_ok=True)

                output_file = output_dir / "all_classes.json"
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False, indent=2, cls=UUIDEncoder)
                logger.info(
                    f"Информация о {len(classes_list)} классах сохранена в {output_file}"
                )

            return result

        except NeosintezAuthError as e:
            logger.error(f"Ошибка аутентификации: {e!s}")
        except NeosintezConnectionError as e:
            logger.error(f"Ошибка соединения: {e!s}")
        except Exception as e:
            logger.error(f"Неожиданная ошибка: {e!s}")

    return result


async def search_class_by_name(
    name_pattern: str, case_sensitive: bool = False
) -> List[Dict[str, Any]]:
    """
    Поиск классов по имени.

    Args:
        name_pattern: Строка для поиска в имени класса
        case_sensitive: Учитывать ли регистр при поиске

    Returns:
        Список словарей с найденными классами
    """
    result = await get_all_classes(save_to_file=False)

    matched_classes = []
    search_term = name_pattern if case_sensitive else name_pattern.lower()

    for cls in result.get("classes", []):
        cls_name = cls["name"] if case_sensitive else cls["name"].lower()
        if search_term in cls_name:
            matched_classes.append(cls)

    logger.info(f"Найдено {len(matched_classes)} классов, содержащих '{name_pattern}'")
    return matched_classes


async def main():
    """
    Основная функция для запуска получения информации о классах.
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Получение информации о классах объектов в Neosintez"
    )
    parser.add_argument("--search", type=str, help="Поиск класса по части имени")
    parser.add_argument(
        "--case-sensitive", action="store_true", help="Учитывать регистр при поиске"
    )
    parser.add_argument(
        "--no-save", action="store_true", help="Не сохранять результаты в файл"
    )
    args = parser.parse_args()

    # Если указан параметр поиска, ищем классы по имени
    if args.search:
        matched_classes = await search_class_by_name(
            name_pattern=args.search, case_sensitive=args.case_sensitive
        )

        # Выводим найденные классы
        if matched_classes:
            print(f"\nНайдены классы, содержащие '{args.search}':\n")
            for i, cls in enumerate(matched_classes, 1):
                print(f"{i}. {cls['name']} (ID: {cls['id']})")
                if cls["description"]:
                    print(f"   Описание: {cls['description']}")
                print()
        else:
            print(f"Классы, содержащие '{args.search}', не найдены")

    # Иначе получаем и выводим все классы
    else:
        result = await get_all_classes(save_to_file=not args.no_save)

        # Выводим первые 20 классов для примера
        print(f"\nВсего классов: {result['total_classes']}\n")
        print("Первые 20 классов:")

        for i, cls in enumerate(result["classes"][:20], 1):
            print(f"{i}. {cls['name']} (ID: {cls['id']})")

        if result["total_classes"] > 20:
            print(f"\n... и еще {result['total_classes'] - 20} классов")
            print("Используйте --search для поиска конкретного класса")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Прервано пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e!s}")
