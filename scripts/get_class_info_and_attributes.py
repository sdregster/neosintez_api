#!/usr/bin/env python
"""
Скрипт для получения информации о классе и его атрибутах.

Этот скрипт позволяет получить детальную информацию о конкретном классе
объектов в системе Neosintez и его атрибутах.
"""

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from uuid import UUID

# Загрузка переменных окружения из .env файла
from dotenv import load_dotenv

from neosintez_api.client import NeosintezClient
from neosintez_api.config import load_settings
from neosintez_api.exceptions import NeosintezAuthError, NeosintezConnectionError
from neosintez_api.models import Attribute, EntityClass

load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("neosintez_class_info")


class UUIDEncoder(json.JSONEncoder):
    """
    JSON-encoder для сериализации UUID.
    """

    def default(self, obj):
        if isinstance(obj, UUID):
            # Если объект - UUID, преобразуем его в строку
            return str(obj)
        return super().default(obj)


async def find_class_by_name(name_pattern: str, case_sensitive: bool = False) -> List[EntityClass]:
    """
    Ищет классы по части имени.
    
    Args:
        name_pattern: Строка для поиска в имени класса
        case_sensitive: Учитывать ли регистр при поиске
        
    Returns:
        Список найденных классов
    """
    settings = load_settings()
    
    # Инициализация клиента API
    async with NeosintezClient(settings) as client:
        try:
            # Аутентификация
            await client.auth()
            
            # Получение списка всех классов
            logger.info("Получение списка классов из Neosintez")
            all_classes = await client.classes.get_all()
            logger.info(f"Получено {len(all_classes)} классов")
            
            # Фильтрация классов по имени
            matched_classes = []
            search_term = name_pattern if case_sensitive else name_pattern.lower()
            
            for cls in all_classes:
                cls_name = cls.Name if case_sensitive else cls.Name.lower()
                if search_term in cls_name:
                    matched_classes.append(cls)
            
            logger.info(f"Найдено {len(matched_classes)} классов, соответствующих запросу '{name_pattern}'")
            return matched_classes
            
        except Exception as e:
            logger.error(f"Ошибка при поиске классов: {str(e)}")
            return []


async def get_class_info_and_attributes(class_id: str) -> Tuple[Optional[EntityClass], List[Attribute]]:
    """
    Получает информацию о классе и его атрибуты.
    
    Args:
        class_id: ID класса в формате UUID
        
    Returns:
        Tuple[Optional[EntityClass], List[Attribute]]: Информация о классе и список атрибутов
    """
    settings = load_settings()
    
    # Инициализация клиента API
    async with NeosintezClient(settings) as client:
        try:
            # Аутентификация
            await client.auth()
            
            # Получаем информацию о классе
            class_info = None
            logger.info(f"Поиск класса с ID {class_id}")
            
            # Получаем список всех классов
            all_classes = await client.classes.get_all()
            
            # Ищем класс по ID
            for cls in all_classes:
                if str(cls.Id) == class_id:
                    class_info = cls
                    break
                    
            if not class_info:
                logger.error(f"Класс с ID {class_id} не найден")
                return None, []
                
            logger.info(f"Найден класс: {class_info.Name}")
            
            # Получаем атрибуты класса
            logger.info(f"Получение атрибутов класса {class_info.Name}")
            
            try:
                # Пробуем получить атрибуты стандартным методом
                attributes = await client.attributes.get_for_entity(class_id)
                logger.info(f"Получено {len(attributes)} атрибутов")
            except Exception as e:
                logger.warning(f"Не удалось получить атрибуты стандартным методом: {str(e)}")
                attributes = []
                
            # Если не удалось получить атрибуты стандартным методом, пробуем получить через поиск
            if not attributes:
                logger.info("Получение списка всех атрибутов")
                all_attributes = await client.attributes.get_all()
                logger.info(f"Получено {len(all_attributes)} атрибутов")
                
                # Фильтруем атрибуты по EntityId
                filtered_attributes = []
                for attr in all_attributes:
                    if hasattr(attr, "EntityId") and attr.EntityId and str(attr.EntityId) == class_id:
                        filtered_attributes.append(attr)
                        
                logger.info(f"Отфильтровано {len(filtered_attributes)} атрибутов для класса {class_info.Name}")
                attributes = filtered_attributes
            
            return class_info, attributes
            
        except Exception as e:
            logger.error(f"Ошибка при получении информации о классе и атрибутах: {str(e)}")
            return None, []
            

async def save_class_info_to_file(class_info: EntityClass, attributes: List[Attribute]) -> bool:
    """
    Сохраняет информацию о классе и его атрибутах в JSON-файл.
    
    Args:
        class_info: Информация о классе
        attributes: Список атрибутов класса
        
    Returns:
        bool: True, если сохранение успешно
    """
    # Создаём словарь с информацией
    result = {
        "class": {
            "id": str(class_info.Id),
            "name": class_info.Name,
            "description": class_info.Description or ""
        },
        "attributes": []
    }
    
    # Добавляем информацию об атрибутах
    for attr in attributes:
        attr_dict = {
            "id": str(attr.Id),
            "name": attr.Name,
        }
        
        # Добавляем тип атрибута, если есть
        if attr.Type:
            attr_dict["type"] = {
                "id": attr.Type.Id,
                "name": attr.Type.Name
            }
            
        # Добавляем дополнительные поля, если они есть
        if hasattr(attr, "Description") and attr.Description:
            attr_dict["description"] = attr.Description
            
        if hasattr(attr, "IsCollection") and attr.IsCollection is not None:
            attr_dict["is_collection"] = attr.IsCollection
            
        if hasattr(attr, "DefaultValue") and attr.DefaultValue is not None:
            attr_dict["default_value"] = attr.DefaultValue
            
        if hasattr(attr, "ValidationRule") and attr.ValidationRule:
            attr_dict["validation_rule"] = attr.ValidationRule
            
        if hasattr(attr, "Items") and attr.Items:
            attr_dict["items"] = [
                {"id": str(item.Id), "name": item.Name}
                for item in attr.Items
            ]
            
        result["attributes"].append(attr_dict)
        
    # Сохраняем результаты в файл
    try:
        output_dir = Path("data")
        output_dir.mkdir(exist_ok=True)
        
        # Создаём безопасное имя файла из имени класса
        safe_name = class_info.Name.replace(" ", "_").replace("/", "_")
        output_file = output_dir / f"{safe_name}_info.json"
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2, cls=UUIDEncoder)
        logger.info(f"Информация о классе '{class_info.Name}' сохранена в {output_file}")
        
        return True
    except Exception as e:
        logger.error(f"Ошибка при сохранении информации в файл: {str(e)}")
        return False


async def main():
    """
    Основная функция для запуска скрипта.
    """
    import argparse
    
    parser = argparse.ArgumentParser(description="Получение информации о классе и его атрибутах")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--id", type=str, help="ID класса")
    group.add_argument("--search", type=str, help="Поиск класса по имени")
    parser.add_argument("--case-sensitive", action="store_true", help="Учитывать регистр при поиске")
    args = parser.parse_args()
    
    if args.search:
        # Поиск классов по имени
        matched_classes = await find_class_by_name(args.search, args.case_sensitive)
        
        if not matched_classes:
            print(f"Классы, содержащие '{args.search}' в имени, не найдены")
            return 1
            
        # Выводим список найденных классов
        print(f"\nНайдено {len(matched_classes)} классов, содержащих '{args.search}':\n")
        for i, cls in enumerate(matched_classes, 1):
            print(f"{i}. {cls.Name} (ID: {cls.Id})")
            if cls.Description:
                print(f"   Описание: {cls.Description}")
            print()
            
        # Если найден только один класс, предлагаем получить его атрибуты
        if len(matched_classes) == 1:
            class_id = str(matched_classes[0].Id)
            print(f"Найден один класс, получаем информацию о его атрибутах...\n")
        else:
            # Иначе предлагаем выбрать класс из списка
            while True:
                try:
                    choice = input("Выберите номер класса для получения его атрибутов (или 'q' для выхода): ")
                    if choice.lower() == 'q':
                        return 0
                        
                    choice_idx = int(choice) - 1
                    if 0 <= choice_idx < len(matched_classes):
                        class_id = str(matched_classes[choice_idx].Id)
                        break
                    else:
                        print(f"Пожалуйста, введите число от 1 до {len(matched_classes)}")
                except ValueError:
                    print("Пожалуйста, введите число или 'q' для выхода")
    else:
        # Получаем информацию о классе по ID
        class_id = args.id
        
    # Получаем информацию о классе и его атрибуты
    class_info, attributes = await get_class_info_and_attributes(class_id)
    
    if not class_info:
        print(f"Класс с ID {class_id} не найден")
        return 1
        
    # Выводим информацию о классе
    print(f"\nИнформация о классе:")
    print(f"Имя: {class_info.Name}")
    print(f"ID: {class_info.Id}")
    if class_info.Description:
        print(f"Описание: {class_info.Description}")
        
    # Выводим информацию об атрибутах
    print(f"\nАтрибуты класса ({len(attributes)}):")
    if not attributes:
        print("Атрибуты не найдены")
    else:
        # Группируем атрибуты по типу
        types = {}
        for attr in attributes:
            if attr.Type:
                type_name = attr.Type.Name
                if type_name not in types:
                    types[type_name] = []
                types[type_name].append(attr)
                
        # Выводим атрибуты по группам
        for type_name, attrs in sorted(types.items()):
            print(f"\n{type_name} ({len(attrs)}):")
            for i, attr in enumerate(sorted(attrs, key=lambda a: a.Name), 1):
                print(f"{i}. {attr.Name}")
                
        # Сохраняем информацию в файл
        await save_class_info_to_file(class_info, attributes)
    
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