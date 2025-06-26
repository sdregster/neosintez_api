#!/usr/bin/env python
"""
Скрипт для получения информации обо всех атрибутах в системе Neosintez.
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Dict, List, Any
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
logger = logging.getLogger("neosintez_all_attributes")


class UUIDEncoder(json.JSONEncoder):
    """
    JSON-encoder для сериализации UUID.
    """

    def default(self, obj):
        if isinstance(obj, UUID):
            # Если объект - UUID, преобразуем его в строку
            return str(obj)
        return super().default(obj)


async def get_all_attributes(save_to_file: bool = True) -> Dict[str, Any]:
    """
    Получает список всех атрибутов в системе Neosintez.

    Args:
        save_to_file: Сохранять ли результаты в JSON-файл

    Returns:
        Dict с информацией о всех атрибутах
    """
    # Загрузка настроек из переменных окружения
    settings = load_settings()
    logger.info(f"Загружены настройки для подключения к {settings.base_url}")

    result = {
        "total_attributes": 0,
        "attributes": [],
    }

    # Инициализация клиента API
    async with NeosintezClient(settings) as client:
        try:
            # Аутентификация
            logger.info("Попытка аутентификации...")
            token = await client.auth()
            logger.info(f"Получен токен: {token[:10]}...")

            # Получение списка всех атрибутов
            logger.info("Получение списка всех атрибутов из Neosintez")
            attributes = await client.attributes.get_all()
            logger.info(f"Получено {len(attributes)} атрибутов")

            result["total_attributes"] = len(attributes)

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
                    "entity_id": str(attr.EntityId)
                    if hasattr(attr, "EntityId") and attr.EntityId
                    else None,
                }

                # Добавляем дополнительные поля в зависимости от типа атрибута
                if hasattr(attr, "DefaultValue") and attr.DefaultValue is not None:
                    attr_dict["default_value"] = attr.DefaultValue

                if hasattr(attr, "ValidationRule") and attr.ValidationRule:
                    attr_dict["validation_rule"] = attr.ValidationRule

                if hasattr(attr, "Items") and attr.Items:
                    attr_dict["items"] = [
                        {"id": str(item.Id), "name": item.Name} for item in attr.Items
                    ]

                attributes_list.append(attr_dict)

            # Сортируем атрибуты по имени для удобства
            attributes_list.sort(key=lambda x: x["name"])
            result["attributes"] = attributes_list

            # Сохраняем результаты в файл
            if save_to_file:
                output_dir = Path("data")
                output_dir.mkdir(exist_ok=True)

                output_file = output_dir / "all_attributes.json"
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False, indent=2, cls=UUIDEncoder)
                logger.info(
                    f"Информация о {len(attributes_list)} атрибутах сохранена в {output_file}"
                )

            return result

        except NeosintezAuthError as e:
            logger.error(f"Ошибка аутентификации: {str(e)}")
        except NeosintezConnectionError as e:
            logger.error(f"Ошибка соединения: {str(e)}")
        except Exception as e:
            logger.error(f"Неожиданная ошибка: {str(e)}")

    return result


async def filter_attributes_by_entity(entity_id: str) -> List[Dict[str, Any]]:
    """
    Фильтрует атрибуты по ID сущности.

    Args:
        entity_id: ID сущности/класса

    Returns:
        Список атрибутов для указанной сущности
    """
    result = await get_all_attributes(save_to_file=False)

    # Фильтруем атрибуты по ID сущности
    filtered_attributes = []
    for attr in result.get("attributes", []):
        if attr.get("entity_id") == entity_id:
            filtered_attributes.append(attr)

    logger.info(
        f"Найдено {len(filtered_attributes)} атрибутов для сущности {entity_id}"
    )
    return filtered_attributes


async def main():
    """
    Основная функция для запуска скрипта.
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Получение информации об атрибутах в Neosintez"
    )
    parser.add_argument(
        "--entity-id", type=str, help="ID сущности/класса для фильтрации атрибутов"
    )
    parser.add_argument(
        "--no-save", action="store_true", help="Не сохранять результаты в файл"
    )
    args = parser.parse_args()

    # Если указан ID сущности, фильтруем атрибуты
    if args.entity_id:
        attributes = await filter_attributes_by_entity(args.entity_id)

        # Находим имя класса
        class_name = "Неизвестный класс"
        async with NeosintezClient(load_settings()) as client:
            await client.auth()
            all_classes = await client.classes.get_all()
            for cls in all_classes:
                if str(cls.Id) == args.entity_id:
                    class_name = cls.Name
                    break

        # Выводим атрибуты
        print(f"\nАтрибуты класса '{class_name}' (ID: {args.entity_id}):")
        print(f"Всего атрибутов: {len(attributes)}\n")

        if attributes:
            for i, attr in enumerate(attributes, 1):
                print(f"{i}. {attr['name']} (Тип: {attr.get('type', 'Неизвестный')})")
                if attr.get("description"):
                    print(f"   Описание: {attr['description']}")
                if attr.get("required") is True:
                    print("   Обязательный: Да")
                if attr.get("is_collection") is True:
                    print("   Коллекция: Да")
                if "default_value" in attr:
                    print(f"   Значение по умолчанию: {attr['default_value']}")
                print()
        else:
            print("Атрибуты не найдены.")

        # Сохраняем отфильтрованные атрибуты в файл
        if not args.no_save and attributes:
            output_dir = Path("data")
            output_dir.mkdir(exist_ok=True)

            output_file = output_dir / f"{class_name.replace(' ', '_')}_attributes.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "class_id": args.entity_id,
                        "class_name": class_name,
                        "attributes_count": len(attributes),
                        "attributes": attributes,
                    },
                    f,
                    ensure_ascii=False,
                    indent=2,
                    cls=UUIDEncoder,
                )
            logger.info(
                f"Информация об атрибутах класса '{class_name}' сохранена в {output_file}"
            )

    # Иначе получаем все атрибуты
    else:
        result = await get_all_attributes(save_to_file=not args.no_save)

        # Выводим первые 20 атрибутов для примера
        print(f"\nВсего атрибутов: {result['total_attributes']}\n")
        print("Первые 20 атрибутов:")

        for i, attr in enumerate(result["attributes"][:20], 1):
            print(f"{i}. {attr['name']} (Тип: {attr.get('type', 'Неизвестный')})")
            if attr.get("entity_id"):
                print(f"   ID сущности: {attr['entity_id']}")

        if result["total_attributes"] > 20:
            print(f"\n... и еще {result['total_attributes'] - 20} атрибутов")
            print("Используйте --entity-id для фильтрации атрибутов по ID сущности")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Прервано пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {str(e)}")
