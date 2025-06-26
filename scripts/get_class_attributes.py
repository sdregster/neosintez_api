#!/usr/bin/env python
"""
Скрипт для получения информации об атрибутах конкретного класса в системе Neosintez.
"""

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Dict, Any
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
logger = logging.getLogger("neosintez_attributes")


class UUIDEncoder(json.JSONEncoder):
    """
    JSON-encoder для сериализации UUID.
    """

    def default(self, obj):
        if isinstance(obj, UUID):
            # Если объект - UUID, преобразуем его в строку
            return str(obj)
        return super().default(obj)


async def get_class_attributes(class_id: str) -> Dict[str, Any]:
    """
    Получает информацию об атрибутах конкретного класса.

    Args:
        class_id: Идентификатор класса в формате UUID (строка)

    Returns:
        Dict с информацией о классе и его атрибутах
    """
    # Загрузка настроек
    settings = load_settings()
    logger.info(f"Загружены настройки для подключения к {settings.base_url}")

    result = {
        "class_id": class_id,
        "class_name": "",
        "attributes_count": 0,
        "attributes": [],
    }

    # Инициализация клиента API
    async with NeosintezClient(settings) as client:
        try:
            # Аутентификация
            logger.info("Попытка аутентификации...")
            token = await client.auth()
            logger.info(f"Получен токен: {token[:10]}...")

            # Пытаемся получить имя класса через поиск среди всех классов
            logger.info(f"Поиск информации о классе {class_id}")
            all_classes = await client.classes.get_all()

            class_name = "Неизвестный класс"
            for cls in all_classes:
                if str(cls.Id) == class_id:
                    class_name = cls.Name
                    logger.info(f"Найден класс: {class_name}")
                    break

            result["class_name"] = class_name

            # Получение атрибутов класса
            logger.info(f"Получение атрибутов класса {class_name}")
            attributes = await client.attributes.get_for_entity(class_id)
            logger.info(f"Получено {len(attributes)} атрибутов")

            result["attributes_count"] = len(attributes)

            # Преобразование атрибутов в список словарей для JSON
            attributes_list = []
            for attr in attributes:
                attr_dict = {
                    "id": str(attr.Id),
                    "name": attr.Name,
                    "type": getattr(attr, "Type", None),
                    "required": getattr(attr, "Required", False),
                    "description": getattr(attr, "Description", ""),
                    "is_collection": getattr(attr, "IsCollection", False),
                }

                # Добавляем дополнительные поля в зависимости от типа атрибута
                if hasattr(attr, "DefaultValue"):
                    attr_dict["default_value"] = attr.DefaultValue

                if hasattr(attr, "ValidationRule"):
                    attr_dict["validation_rule"] = attr.ValidationRule

                if hasattr(attr, "Items") and attr.Items:
                    attr_dict["items"] = [
                        {"id": str(item.Id), "name": item.Name} for item in attr.Items
                    ]

                attributes_list.append(attr_dict)

            # Сортируем атрибуты по имени
            attributes_list.sort(key=lambda x: x["name"])
            result["attributes"] = attributes_list

            # Сохранение результатов в файл
            output_dir = Path("data")
            output_dir.mkdir(exist_ok=True)

            # Создаём безопасное имя файла из имени класса
            safe_name = result["class_name"].replace(" ", "_").replace("/", "_")
            output_file = output_dir / f"{safe_name}_attributes.json"

            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2, cls=UUIDEncoder)
            logger.info(
                f"Атрибуты класса '{result['class_name']}' сохранены в {output_file}"
            )

            return result

        except NeosintezAuthError as e:
            logger.error(f"Ошибка аутентификации: {str(e)}")
        except NeosintezConnectionError as e:
            logger.error(f"Ошибка соединения: {str(e)}")
        except Exception as e:
            logger.error(f"Неожиданная ошибка: {str(e)}")

    return result


async def print_attributes_info(result: Dict[str, Any]) -> None:
    """
    Выводит информацию об атрибутах класса в консоль.

    Args:
        result: Словарь с информацией о классе и атрибутах
    """
    if not result.get("class_name"):
        print("Информация о классе не найдена")
        return

    print(
        f"\nАтрибуты класса: {result['class_name']} (всего: {result['attributes_count']})\n"
    )

    # Типы атрибутов в виде словаря для перевода
    attr_types = {
        "String": "Строка",
        "Number": "Число",
        "DateTime": "Дата/Время",
        "Boolean": "Булево",
        "Item": "Элемент (ссылка)",
        "File": "Файл",
        "ItemCollection": "Коллекция элементов",
    }

    for i, attr in enumerate(result["attributes"], 1):
        type_str = attr_types.get(attr["type"], attr["type"])
        required = "Обязательный" if attr.get("required") else "Необязательный"
        collection = "Коллекция" if attr.get("is_collection") else "Одиночный"

        print(f"{i}. {attr['name']}")
        print(f"   Тип: {type_str} | {required} | {collection}")

        if attr.get("description"):
            print(f"   Описание: {attr['description']}")

        if attr.get("default_value") is not None:
            print(f"   Значение по умолчанию: {attr['default_value']}")

        if attr.get("validation_rule"):
            print(f"   Правило валидации: {attr['validation_rule']}")

        if attr.get("items"):
            print(f"   Возможные значения ({len(attr['items'])}):")
            for j, item in enumerate(attr["items"][:5], 1):
                print(f"      {j}. {item['name']} (ID: {item['id']})")
            if len(attr["items"]) > 5:
                print(f"      ... и еще {len(attr['items']) - 5}")

        print()


async def main():
    """
    Основная функция для запуска скрипта.
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Получение информации об атрибутах класса в Neosintez"
    )
    parser.add_argument("class_id", help="ID класса (UUID)")
    parser.add_argument(
        "--quiet", "-q", action="store_true", help="Не выводить информацию в консоль"
    )
    args = parser.parse_args()

    # Проверяем формат UUID
    if not args.class_id or len(args.class_id) < 32:
        print("Ошибка: Необходимо указать корректный ID класса (UUID)")
        print("Получите ID класса с помощью скрипта get_classes_info.py")
        return 1

    # Получаем информацию об атрибутах класса
    result = await get_class_attributes(args.class_id)

    # Если не тихий режим, выводим информацию в консоль
    if not args.quiet:
        await print_attributes_info(result)

    return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("Прервано пользователем")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Критическая ошибка: {str(e)}")
        sys.exit(1)
