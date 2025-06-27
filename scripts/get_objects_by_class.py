#!/usr/bin/env python
"""
Скрипт для получения объектов по классу и их атрибутов.

Этот скрипт позволяет получить список объектов указанного класса
и информацию об их атрибутах.
"""

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

# Загрузка переменных окружения из .env файла
from dotenv import load_dotenv

from neosintez_api.client import NeosintezClient
from neosintez_api.config import load_settings
from neosintez_api.models import EntityClass, Object, SearchFilter, SearchRequest


load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("neosintez_objects")


class UUIDEncoder(json.JSONEncoder):
    """
    JSON-encoder для сериализации UUID.
    """

    def default(self, obj):
        if isinstance(obj, UUID):
            # Если объект - UUID, преобразуем его в строку
            return str(obj)
        return super().default(obj)


async def get_class_by_id(class_id: str) -> Optional[EntityClass]:
    """
    Получает информацию о классе по его ID.

    Args:
        class_id: ID класса

    Returns:
        Optional[EntityClass]: Информация о классе или None, если класс не найден
    """
    settings = load_settings()

    # Инициализация клиента API
    async with NeosintezClient(settings) as client:
        try:
            # Аутентификация
            await client.auth()

            # Получаем список всех классов
            all_classes = await client.classes.get_all()

            # Ищем класс по ID
            for cls in all_classes:
                if str(cls.Id) == class_id:
                    return cls

            logger.error(f"Класс с ID {class_id} не найден")
            return None

        except Exception as e:
            logger.error(f"Ошибка при получении информации о классе: {e!s}")
            return None


async def get_objects_by_class(class_id: str, limit: int = 10) -> List[Object]:
    """
    Получает список объектов указанного класса.

    Args:
        class_id: ID класса
        limit: Максимальное количество объектов для получения

    Returns:
        List[Object]: Список объектов класса
    """
    settings = load_settings()

    # Инициализация клиента API
    async with NeosintezClient(settings) as client:
        try:
            # Аутентификация
            await client.auth()

            # Создаем поисковый запрос для поиска объектов по классу
            search_request = SearchRequest(
                Filters=[
                    SearchFilter(
                        Type=5,  # ByClass
                        Value=class_id,
                    )
                ],
                Take=limit,
                Skip=0,
            )

            # Выполняем поиск объектов
            logger.info(f"Поиск объектов класса с ID {class_id}")
            search_result = await client.objects.search(search_request)

            if not search_result or not search_result.Result:
                logger.info(f"Объекты класса с ID {class_id} не найдены")
                return []

            logger.info(f"Найдено {len(search_result.Result)} объектов класса")
            return search_result.Result

        except Exception as e:
            logger.error(f"Ошибка при поиске объектов класса: {e!s}")
            return []


async def get_object_attributes(object_id: str) -> Dict[str, Any]:
    """
    Получает атрибуты объекта по его ID.

    Args:
        object_id: ID объекта

    Returns:
        Dict[str, Any]: Словарь с атрибутами объекта
    """
    settings = load_settings()

    # Инициализация клиента API
    async with NeosintezClient(settings) as client:
        try:
            # Аутентификация
            await client.auth()

            # Получаем детальную информацию об объекте
            logger.info(f"Получение информации об объекте с ID {object_id}")
            object_info = await client.objects.get_by_id(object_id)

            if not object_info:
                logger.error(f"Объект с ID {object_id} не найден")
                return {}

            # Получаем атрибуты объекта
            logger.info(f"Получение атрибутов объекта {object_info.Name}")

            # Проверяем, есть ли атрибуты в объекте
            if not object_info.Attributes:
                logger.info(f"У объекта {object_info.Name} нет атрибутов")
                return {}

            return object_info.Attributes

        except Exception as e:
            logger.error(f"Ошибка при получении атрибутов объекта: {e!s}")
            return {}


async def save_objects_info_to_file(
    class_info: EntityClass,
    objects: List[Object],
    objects_attributes: List[Dict[str, Any]],
) -> bool:
    """
    Сохраняет информацию об объектах класса и их атрибутах в JSON-файл.

    Args:
        class_info: Информация о классе
        objects: Список объектов класса
        objects_attributes: Список словарей с атрибутами объектов

    Returns:
        bool: True, если сохранение успешно
    """
    # Создаём словарь с информацией
    result = {
        "class": {
            "id": str(class_info.Id),
            "name": class_info.Name,
            "description": class_info.Description or "",
        },
        "objects": [],
    }

    # Добавляем информацию об объектах и их атрибутах
    for i, obj in enumerate(objects):
        obj_dict = {
            "id": str(obj.Id),
            "name": obj.Name,
            "description": obj.Description or "",
            "attributes": objects_attributes[i] if i < len(objects_attributes) else {},
        }
        result["objects"].append(obj_dict)

    # Сохраняем результаты в файл
    try:
        output_dir = Path("data")
        output_dir.mkdir(exist_ok=True)

        # Создаём безопасное имя файла из имени класса
        safe_name = class_info.Name.replace(" ", "_").replace("/", "_")
        output_file = output_dir / f"{safe_name}_objects.json"

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2, cls=UUIDEncoder)
        logger.info(f"Информация об объектах класса '{class_info.Name}' сохранена в {output_file}")

        return True
    except Exception as e:
        logger.error(f"Ошибка при сохранении информации в файл: {e!s}")
        return False


async def main():
    """
    Основная функция для запуска скрипта.
    """
    import argparse

    parser = argparse.ArgumentParser(description="Получение объектов по классу и их атрибутов")
    parser.add_argument("--id", type=str, required=True, help="ID класса")
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Максимальное количество объектов для получения",
    )
    args = parser.parse_args()

    # Получаем информацию о классе
    class_info = await get_class_by_id(args.id)

    if not class_info:
        print(f"Класс с ID {args.id} не найден")
        return 1

    print("\nИнформация о классе:")
    print(f"Имя: {class_info.Name}")
    print(f"ID: {class_info.Id}")
    if class_info.Description:
        print(f"Описание: {class_info.Description}")

    # Получаем объекты класса
    objects = await get_objects_by_class(args.id, args.limit)

    if not objects:
        print(f"\nОбъекты класса '{class_info.Name}' не найдены")
        return 0

    print(f"\nНайдено {len(objects)} объектов класса '{class_info.Name}':")
    for i, obj in enumerate(objects, 1):
        print(f"\n{i}. {obj.Name} (ID: {obj.Id})")
        if obj.Description:
            print(f"   Описание: {obj.Description}")

    # Получаем атрибуты для каждого объекта
    print("\nПолучение атрибутов объектов...")
    objects_attributes = []

    for obj in objects:
        attributes = await get_object_attributes(str(obj.Id))
        objects_attributes.append(attributes)

    # Выводим информацию об атрибутах
    print("\nАтрибуты объектов:")

    # Собираем все уникальные атрибуты
    all_attributes = set()
    for attrs in objects_attributes:
        all_attributes.update(attrs.keys())

    if not all_attributes:
        print("Атрибуты не найдены")
    else:
        print(f"Найдено {len(all_attributes)} уникальных атрибутов:")
        for attr in sorted(all_attributes):
            print(f"- {attr}")

        # Сохраняем информацию в файл
        await save_objects_info_to_file(class_info, objects, objects_attributes)

    return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("Прервано пользователем")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Критическая ошибка: {e!s}")
        sys.exit(1)
