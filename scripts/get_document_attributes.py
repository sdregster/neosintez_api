#!/usr/bin/env python
"""
Скрипт для получения атрибутов класса "Документ" из системы Neosintez.
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict
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


async def get_class_attributes(class_name: str, save_to_file: bool = True) -> Dict[str, Any]:
    """
    Получает атрибуты указанного класса объектов в Neosintez.

    Args:
        class_name: Имя класса объектов ("Документ", "Папка" и т.д.)
        save_to_file: Сохранять ли результаты в JSON-файл

    Returns:
        Dict с информацией о классе и его атрибутах
    """
    # Загрузка настроек из переменных окружения
    settings = load_settings()
    logger.info(f"Загружены настройки для подключения к {settings.base_url}")

    result = {
        "class_name": class_name,
        "found": False,
        "class_id": None,
        "attributes": [],
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

            # Поиск нужного класса по имени
            entity_class = None
            for entity in entities:
                if entity.Name == class_name:
                    entity_class = entity
                    result["found"] = True
                    result["class_id"] = str(entity.Id)
                    logger.info(f"Найден класс '{class_name}' (ID: {entity.Id})")
                    break

            # Если класс не найден, ищем частичное совпадение
            if not entity_class:
                for entity in entities:
                    if class_name.lower() in entity.Name.lower():
                        entity_class = entity
                        result["found"] = True
                        result["class_id"] = str(entity.Id)
                        result["class_name"] = entity.Name  # Используем точное имя класса
                        logger.info(
                            f"Найдено частичное совпадение для '{class_name}': '{entity.Name}' (ID: {entity.Id})"
                        )
                        break

            if not entity_class:
                logger.error(f"Класс '{class_name}' не найден в системе")
                return result

            # Получение атрибутов класса
            class_id = str(entity_class.Id)
            logger.info(f"Получение атрибутов класса {class_id}")
            attributes = await client.classes.get_attributes(class_id)
            logger.info(f"Получено {len(attributes)} атрибутов для класса {class_name}")

            # Преобразование атрибутов в список словарей для JSON
            attributes_list = []
            for attr in attributes:
                attr_dict = {
                    "id": str(attr.Id),
                    "name": attr.Name,
                    "type": getattr(attr, "ClrType", "Unknown"),
                    "is_required": getattr(attr, "IsRequired", False),
                    "is_collection": getattr(attr, "IsCollection", False),
                    "description": getattr(attr, "Description", ""),
                }
                attributes_list.append(attr_dict)
                logger.info(f"Атрибут: {attr.Name} (ID: {attr.Id}, тип: {getattr(attr, 'ClrType', 'Unknown')})")

            result["attributes"] = attributes_list

            # Сохраняем результаты в файл
            if save_to_file:
                output_dir = Path("data")
                output_dir.mkdir(exist_ok=True)

                output_file = output_dir / f"{class_name.lower()}_attributes.json"
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False, indent=2, cls=UUIDEncoder)
                logger.info(f"Результаты сохранены в {output_file}")

            return result

        except NeosintezAuthError as e:
            logger.error(f"Ошибка аутентификации: {e!s}")
        except NeosintezConnectionError as e:
            logger.error(f"Ошибка соединения: {e!s}")
        except Exception as e:
            logger.error(f"Неожиданная ошибка: {e!s}")

    return result


async def main():
    """
    Основная функция для запуска получения атрибутов.
    """
    import argparse

    parser = argparse.ArgumentParser(description="Получение атрибутов класса объектов из Neosintez")
    parser.add_argument(
        "--class-name",
        default="Документ",
        help="Имя класса объектов (по умолчанию: 'Документ')",
    )
    parser.add_argument("--no-save", action="store_true", help="Не сохранять результаты в файл")
    args = parser.parse_args()

    # Получаем атрибуты класса
    result = await get_class_attributes(class_name=args.class_name, save_to_file=not args.no_save)

    # Выводим результаты в консоль
    if result["found"]:
        print(f"\nРезультаты для класса '{result['class_name']}' (ID: {result['class_id']}):")
        print(f"Найдено {len(result['attributes'])} атрибутов:\n")

        for idx, attr in enumerate(result["attributes"], 1):
            print(f"{idx}. {attr['name']} (ID: {attr['id']})")
            print(f"   Тип: {attr['type']}")
            print(f"   Обязательный: {'Да' if attr['is_required'] else 'Нет'}")
            if attr["description"]:
                print(f"   Описание: {attr['description']}")
            print()
    else:
        print(f"Класс '{args.class_name}' не найден в системе!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Прервано пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e!s}")
