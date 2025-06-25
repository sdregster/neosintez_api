"""
Скрипт для проверки импортированных объектов в Neosintez.
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from typing import Dict, Any

from dotenv import load_dotenv

from neosintez_api.client import NeosintezClient
from neosintez_api.config import load_settings
from neosintez_api.exceptions import NeosintezAuthError, NeosintezConnectionError

from import_ks2_xlsx_template import NeosintezExcelImporter, UUIDEncoder

# Загрузка переменных окружения из .env файла
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("neosintez_checker")


async def check_objects(object_id: str, deep: bool = False) -> Dict[str, Any]:
    """
    Проверяет объекты в Neosintez.
    
    Args:
        object_id: ID объекта для проверки
        deep: Если True, выполняет глубокую проверку иерархии
        
    Returns:
        Dict[str, Any]: Результаты проверки
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
            
            # Проверка существования объекта
            try:
                parent_obj = await client.objects.get_by_id(object_id)
                logger.info(f"Объект найден: {parent_obj.Name} (ID: {parent_obj.Id})")
            except Exception as e:
                logger.error(f"Ошибка при получении объекта: {str(e)}")
                return {"error": str(e)}
            
            # Создаем имитацию импортера для использования методов проверки
            # (без указания Excel файла, т.к. он не нужен для проверки)
            importer = NeosintezExcelImporter(
                client=client,
                excel_path="",  # Пустой путь, т.к. файл не используется
                target_object_id=object_id,
            )
            
            # Получаем информацию об иерархии объектов
            if deep:
                # Глубокая проверка (рекурсивно)
                logger.info("Выполняется глубокая проверка иерархии объектов...")
                result = await importer.verify_object_hierarchy()
            else:
                # Простая проверка (только прямые дочерние объекты)
                logger.info("Выполняется проверка дочерних объектов...")
                children = await client.objects.get_children(object_id)
                result = {
                    "parent_id": object_id,
                    "parent_name": parent_obj.Name,
                    "children_count": len(children),
                    "children": [
                        {
                            "id": str(child.Id),
                            "name": child.Name,
                            "entity_id": str(child.EntityId) if hasattr(child, 'EntityId') else None,
                            "entity_name": child.Entity.Name if hasattr(child, 'Entity') and hasattr(child.Entity, 'Name') else None
                        } for child in children
                    ]
                }
            
            return result
            
        except NeosintezAuthError as e:
            logger.error(f"Ошибка аутентификации: {str(e)}")
            return {"error": str(e)}
        except NeosintezConnectionError as e:
            logger.error(f"Ошибка соединения: {str(e)}")
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"Неожиданная ошибка: {str(e)}")
            import traceback
            logger.error(f"Трассировка: {traceback.format_exc()}")
            return {"error": str(e), "traceback": traceback.format_exc()}


async def main():
    """
    Основная функция скрипта.
    """
    # Настройка аргументов командной строки
    parser = argparse.ArgumentParser(description="Проверка объектов в Neosintez")
    parser.add_argument("--id", default="a7928b22-5a25-f011-91dd-005056b6948b", 
                        help="ID объекта для проверки")
    parser.add_argument("--deep", action="store_true", 
                        help="Выполнить глубокую проверку иерархии")
    parser.add_argument("--output", default="object_check.json", 
                        help="Имя файла для сохранения результатов")
    
    args = parser.parse_args()
    
    # Выполняем проверку
    logger.info(f"Начало проверки объекта {args.id}...")
    result = await check_objects(args.id, args.deep)
    
    # Сохраняем результат в файл
    output_file = os.path.join("data", args.output)
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=4, cls=UUIDEncoder)
    
    logger.info(f"Проверка завершена. Результаты сохранены в {output_file}")
    
    # Выводим статистику
    if "children" in result:
        logger.info(f"Найдено {len(result['children'])} дочерних объектов")
        
        # Группируем объекты по типам
        types = {}
        for child in result["children"]:
            entity_type = child.get("entity_name", "Неизвестный тип")
            if entity_type not in types:
                types[entity_type] = 0
            types[entity_type] += 1
        
        logger.info("Распределение по типам:")
        for entity_type, count in types.items():
            logger.info(f"  {entity_type}: {count} объектов")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Прервано пользователем")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Критическая ошибка: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1) 