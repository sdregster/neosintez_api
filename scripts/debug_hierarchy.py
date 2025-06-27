#!/usr/bin/env python
"""
Отладка иерархического импорта - проверяем parent_id.
"""

import asyncio
import logging

from neosintez_api.config import NeosintezSettings
from neosintez_api.core.client import NeosintezClient
from neosintez_api.hierarchical_excel_import import HierarchicalExcelImporter
from neosintez_api.resources.classes import ClassesResource
from neosintez_api.resources.objects import ObjectsResource

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger("debug_hierarchy")


async def debug_hierarchy_import():
    """Отладка иерархического импорта."""
    
    settings = NeosintezSettings()
    client = NeosintezClient(settings)
    client.classes = ClassesResource(client)
    client.objects = ObjectsResource(client)
    
    # Авторизация
    await client.auth()
    logger.info("Авторизация успешна")
    
    # Создаем импортер
    importer = HierarchicalExcelImporter(client)
    
    # Тестовый файл и родитель
    excel_path = "data/test_example.xlsx"
    parent_id = "5f82d752-9652-f011-91e5-005056b6948b"
    
    logger.info(f"Отладка импорта из {excel_path} в родителя {parent_id}")
    
    # Получаем предварительный просмотр
    preview = await importer.preview_import(excel_path, parent_id)
    
    logger.info("Объекты для импорта:")
    for level, objects in preview.objects_by_level.items():
        logger.info(f"  Уровень {level}:")
        for obj in objects:
            logger.info(f"    - {obj['name']} (класс: {obj['class_name']}, атрибуты: {obj['attributes']})")
    
    # Имитируем логику создания объектов с детальным логированием
    created_objects = []
    
    for level in sorted(preview.objects_by_level.keys()):
        objects = preview.objects_by_level[level]
        logger.info(f"\n=== СОЗДАНИЕ ОБЪЕКТОВ УРОВНЯ {level} ===")
        
        for obj_data in objects:
            # Определяем родительский объект
            if level == 1:
                current_parent_id = parent_id
                logger.info(f"Уровень 1: использую переданный parent_id = {current_parent_id}")
            else:
                # Ищем родителя среди созданных объектов предыдущего уровня
                parent_level = level - 1
                logger.info(f"Уровень {level}: ищу родителя среди объектов уровня {parent_level}")
                
                obj_list = [f"{obj['name']} (уровень {obj['level']}, ID {obj['id']})" for obj in created_objects]
                logger.info(f"Доступные созданные объекты: {obj_list}")
                
                current_parent_id = None
                for obj in reversed(created_objects):
                    if obj["level"] == parent_level:
                        current_parent_id = obj["id"]
                        logger.info(f"Найден родитель: {obj['name']} (ID: {current_parent_id})")
                        break
                
                if not current_parent_id:
                    logger.error(f"НЕ НАЙДЕН родительский объект для уровня {level}!")
                    continue
            
            logger.info(f"Создание объекта '{obj_data['name']}' (уровень {level}) с родителем {current_parent_id}")
            
            # Получаем класс
            entity_class = await importer._get_class_by_name(obj_data["class_name"])
            class_id = entity_class.get("Id")
            
            # Данные для создания объекта БЕЗ поля Parent (parent_id передается в query параметрах)
            object_data = {
                "Name": obj_data["name"],
                "Entity": {"Id": class_id, "Name": obj_data["class_name"]}
            }
            
            logger.info(f"Данные объекта для API: {object_data}")
            logger.info(f"Parent ID передается как query параметр: {current_parent_id}")
            
            try:
                # Создаем объект с parent_id в query параметрах
                response = await client.objects.create(object_data, parent_id=current_parent_id)
                object_id = response.get("Id")
                
                logger.info(f"Объект создан с ID: {object_id}")
                logger.info(f"Полный ответ API: {response}")
                
                # Сохраняем информацию о созданном объекте
                created_object = {
                    "id": object_id,
                    "name": obj_data["name"],
                    "class_name": obj_data["class_name"],
                    "level": level,
                    "parent_id": current_parent_id,
                    "attributes": obj_data.get("attributes", {}),
                }
                created_objects.append(created_object)
                
                # Проверяем иерархию созданного объекта через path endpoint
                try:
                    path_info = await client.objects.get_path(object_id)
                    if path_info and hasattr(path_info, 'Ancestors') and path_info.Ancestors:
                        # Последний предок - это непосредственный родитель
                        immediate_parent = path_info.Ancestors[-1]
                        actual_parent_id = immediate_parent.Id if hasattr(immediate_parent, 'Id') else immediate_parent.get('Id')
                        actual_parent_name = immediate_parent.Name if hasattr(immediate_parent, 'Name') else immediate_parent.get('Name')
                        
                        logger.info(f"Проверка через path: родитель объекта - {actual_parent_name} ({actual_parent_id})")
                        
                        if str(actual_parent_id) == str(current_parent_id):
                            logger.info("✅ ИЕРАРХИЯ РАБОТАЕТ ПРАВИЛЬНО!")
                        else:
                            logger.warning(f"НЕСООТВЕТСТВИЕ: ожидался родитель {current_parent_id}, но получен {actual_parent_id}")
                    else:
                        logger.warning("Path endpoint не вернул информацию о предках")
                        
                        # Альтернативная проверка через get_by_id
                        created_obj_info = await client.objects.get_by_id(object_id)
                        if created_obj_info:
                            actual_parent = created_obj_info.get("Parent", {}).get("Id") if isinstance(created_obj_info, dict) else getattr(created_obj_info, "Parent", {}).get("Id")
                            logger.info(f"Fallback проверка через get_by_id: созданный объект имеет родителя {actual_parent}")
                
                except Exception as e:
                    logger.error(f"Ошибка при проверке иерархии: {e}")
                    # Fallback на старый способ
                    created_obj_info = await client.objects.get_by_id(object_id)
                    if created_obj_info:
                        actual_parent = created_obj_info.get("Parent", {}).get("Id") if isinstance(created_obj_info, dict) else getattr(created_obj_info, "Parent", {}).get("Id")
                        logger.info(f"Fallback проверка: созданный объект имеет родителя {actual_parent}")
                
            except Exception as e:
                logger.error(f"Ошибка при создании объекта: {e}")
    
    logger.info("\n=== ИТОГОВЫЕ СОЗДАННЫЕ ОБЪЕКТЫ ===")
    for obj in created_objects:
        logger.info(f"- {obj['name']} (ID: {obj['id']}, Уровень: {obj['level']}, Родитель: {obj['parent_id']})")


if __name__ == "__main__":
    asyncio.run(debug_hierarchy_import()) 