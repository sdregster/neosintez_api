#!/usr/bin/env python
"""
Скрипт для получения информации о трех разных классах объектов и их атрибутах
для создания Excel шаблона импорта вложенных объектов.
"""

import asyncio
import json
import logging
import os
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
logger = logging.getLogger("neosintez_classes_for_import")


class UUIDEncoder(json.JSONEncoder):
    """
    JSON-encoder для сериализации UUID.
    """

    def default(self, obj):
        if isinstance(obj, UUID):
            # Если объект - UUID, преобразуем его в строку
            return str(obj)
        return super().default(obj)


async def get_all_classes() -> Dict[str, Any]:
    """
    Получает список всех классов объектов из Neosintez.

    Returns:
        Словарь с информацией о классах
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

            return result

        except NeosintezAuthError as e:
            logger.error(f"Ошибка аутентификации: {e!s}")
        except NeosintezConnectionError as e:
            logger.error(f"Ошибка соединения: {e!s}")
        except Exception as e:
            logger.error(f"Неожиданная ошибка: {e!s}")

    return result


async def get_class_attributes(
    client: NeosintezClient, class_id: str
) -> List[Dict[str, Any]]:
    """
    Получает атрибуты класса из Neosintez.

    Args:
        client: Клиент API Neosintez
        class_id: ID класса

    Returns:
        Список атрибутов класса
    """
    try:
        logger.info(f"Получение атрибутов класса {class_id}")
        attributes = await client.classes.get_attributes(class_id)
        logger.info(f"Получено {len(attributes)} атрибутов для класса {class_id}")

        # Преобразование атрибутов в список словарей
        attributes_list = []
        for attr in attributes:
            # Определение типа атрибута
            attr_type = ""
            if hasattr(attr, "Type") and attr.Type:
                attr_type = (
                    attr.Type.Name if hasattr(attr.Type, "Name") else str(attr.Type)
                )

            attr_dict = {
                "id": str(attr.Id),
                "name": attr.Name,
                "type": attr_type,
                "description": getattr(attr, "Description", ""),
                "required": getattr(attr, "Required", False),
                "is_collection": getattr(attr, "IsCollection", False),
            }

            # Добавляем доп. информацию для атрибутов-ссылок
            if hasattr(attr, "Items") and attr.Items:
                attr_dict["items"] = [
                    {"id": str(item.Id), "name": item.Name} for item in attr.Items
                ]

            attributes_list.append(attr_dict)

        # Сортируем атрибуты по имени
        attributes_list.sort(key=lambda x: x["name"])
        return attributes_list

    except Exception as e:
        logger.error(f"Ошибка при получении атрибутов класса {class_id}: {e!s}")
        return []


async def select_diverse_classes(
    classes_list: List[Dict[str, Any]], count: int = 3
) -> List[Dict[str, Any]]:
    """
    Выбирает несколько разнообразных классов из списка.

    В данной реализации мы будем искать классы, которые соответствуют заданным критериям:
    1. "Папка" - базовый тип для структурирования данных
    2. "Документ" или аналогичный класс с атрибутами для документации
    3. "Оборудование" или аналогичный класс с техническими атрибутами

    Args:
        classes_list: Список классов
        count: Количество классов для выбора

    Returns:
        Список выбранных классов
    """
    selected_classes = []
    target_keywords = [
        "папка",
        "документ",
        "оборудование",
        "компонент",
        "элемент",
        "здание",
        "помещение",
    ]

    # Сначала попытаемся найти классы по ключевым словам
    found_keywords = set()
    for keyword in target_keywords:
        if len(selected_classes) >= count:
            break

        for cls in classes_list:
            cls_name_lower = cls["name"].lower()

            # Проверяем, содержит ли имя класса ключевое слово
            # и не было ли это ключевое слово уже найдено
            if keyword in cls_name_lower and keyword not in found_keywords:
                selected_classes.append(cls)
                found_keywords.add(keyword)
                logger.info(
                    f"Выбран класс по ключевому слову '{keyword}': {cls['name']}"
                )
                break

    # Если не нашли достаточно классов по ключевым словам, добавляем другие
    if len(selected_classes) < count:
        # Выбираем случайные классы из оставшихся
        remaining_count = count - len(selected_classes)

        # Получаем ID уже выбранных классов
        selected_ids = {cls["id"] for cls in selected_classes}

        # Выбираем дополнительные классы, которые еще не выбраны
        additional_classes = []
        for cls in classes_list:
            if cls["id"] not in selected_ids:
                additional_classes.append(cls)
                remaining_count -= 1
                logger.info(f"Выбран дополнительный класс: {cls['name']}")
                if remaining_count == 0:
                    break

        selected_classes.extend(additional_classes)

    # Обрезаем до нужного количества, если выбрали больше
    return selected_classes[:count]


async def get_classes_with_attributes(save_to_file: bool = True) -> Dict[str, Any]:
    """
    Получает информацию о нескольких разнообразных классах объектов и их атрибутах.

    Args:
        save_to_file: Сохранять ли результаты в JSON-файл

    Returns:
        Dict с информацией о выбранных классах и их атрибутах
    """
    # Загрузка настроек
    settings = load_settings()

    result = {
        "classes": [],
    }

    try:
        # Получаем список всех классов
        all_classes_info = await get_all_classes()
        if not all_classes_info["classes"]:
            logger.error("Не удалось получить список классов")
            return result

        # Выбираем 3 разнообразных класса
        selected_classes = await select_diverse_classes(
            all_classes_info["classes"], count=3
        )

        # Инициализация клиента API
        async with NeosintezClient(settings) as client:
            # Аутентификация
            logger.info("Попытка аутентификации...")
            token = await client.auth()
            logger.info(f"Получен токен: {token[:10]}...")

            # Получаем атрибуты для каждого выбранного класса
            for cls in selected_classes:
                # Получаем атрибуты класса
                attributes = await get_class_attributes(client, cls["id"])

                # Добавляем информацию о классе и его атрибутах в результат
                class_info = {
                    "id": cls["id"],
                    "name": cls["name"],
                    "description": cls["description"],
                    "attributes_count": len(attributes),
                    "attributes": attributes,
                }

                result["classes"].append(class_info)
                logger.info(f"Класс '{cls['name']}' имеет {len(attributes)} атрибутов")

        # Сохраняем результаты в файл
        if save_to_file:
            os.makedirs("data", exist_ok=True)
            output_file = os.path.join("data", "classes_for_import.json")

            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2, cls=UUIDEncoder)
            logger.info(
                f"Информация о {len(result['classes'])} классах сохранена в {output_file}"
            )

        return result

    except Exception as e:
        logger.error(f"Ошибка при получении классов с атрибутами: {e!s}")
        import traceback

        logger.error(f"Трассировка: {traceback.format_exc()}")

        return result


async def main():
    """
    Основная функция для запуска скрипта.
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Получение информации о классах объектов для импорта"
    )
    parser.add_argument(
        "--no-save", action="store_true", help="Не сохранять результаты в файл"
    )
    args = parser.parse_args()

    # Получаем информацию о классах и их атрибутах
    result = await get_classes_with_attributes(save_to_file=not args.no_save)

    # Выводим информацию о выбранных классах
    print(f"\nВыбрано {len(result['classes'])} классов для импорта:\n")

    for i, cls in enumerate(result["classes"], 1):
        print(f"{i}. {cls['name']} (ID: {cls['id']})")
        print(f"   Описание: {cls['description']}")
        print(f"   Количество атрибутов: {cls['attributes_count']}")

        # Выводим первые 5 атрибутов для примера
        if cls["attributes"]:
            print("   Примеры атрибутов:")
            for j, attr in enumerate(cls["attributes"][:5], 1):
                print(f"      {j}. {attr['name']} (Тип: {attr['type']})")

            if len(cls["attributes"]) > 5:
                print(f"      ... и еще {len(cls['attributes']) - 5} атрибутов")

        print()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Прервано пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e!s}")
