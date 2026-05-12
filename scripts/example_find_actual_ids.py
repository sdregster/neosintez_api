"""
Скрипт для поиска актуальных ID классов и атрибутов для тестирования.

Помогает найти реальные ID в системе для создания рабочего примера поиска.
"""

import asyncio
import json
import logging
import os

from dotenv import load_dotenv

from neosintez_api import NeosintezAPIError, NeosintezClient
from neosintez_api.services import ClassService


# Настройка логирования для вывода информации в консоль
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


async def main():
    """
    Главная функция для поиска актуальных ID.
    """
    load_dotenv()
    
    # Подключение к API Неосинтез
    async with NeosintezClient() as client:
        class_service = ClassService(client)
        
        logging.info("\n=== ПОИСК АКТУАЛЬНЫХ ID ДЛЯ ТЕСТИРОВАНИЯ ===")
        
        # --- Поиск классов по ключевым словам ---
        keywords = ["объект", "оборудование", "капитальный", "эксплуатация", "технический"]
        
        found_classes = {}
        
        for keyword in keywords:
            logging.info("\nПоиск классов по ключевому слову: '%s'", keyword)
            try:
                classes = await class_service.find_by_name(keyword)
                
                if classes:
                    logging.info("Найдено классов: %d", len(classes))
                    for cls in classes[:5]:  # Показываем первые 5
                        class_id = str(cls.Id)
                        found_classes[class_id] = {
                            "name": cls.Name,
                            "id": class_id,
                            "keyword": keyword
                        }
                        logging.info("  - %s (ID: %s)", cls.Name, class_id)
                else:
                    logging.info("Классы не найдены")
                    
            except Exception as e:
                logging.error("Ошибка поиска классов по '%s': %s", keyword, e)
        
        # --- Поиск атрибутов в найденных классах ---
        logging.info("\n=== ПОИСК АТРИБУТОВ В НАЙДЕННЫХ КЛАССАХ ===")
        
        attribute_keywords = ["тип", "наименование", "название", "имя", "мвз", "код"]
        found_attributes = {}
        
        for class_id, class_info in list(found_classes.items())[:3]:  # Берем первые 3 класса
            logging.info("\nАтрибуты класса '%s' (ID: %s):", class_info["name"], class_id)
            
            try:
                attributes = await class_service.get_attributes(class_id)
                
                if attributes:
                    logging.info("Найдено атрибутов: %d", len(attributes))
                    
                    for attr in attributes:
                        attr_id = str(attr.Id)
                        attr_name = attr.Name.lower()
                        
                        # Проверяем, содержит ли имя атрибута ключевые слова
                        for keyword in attribute_keywords:
                            if keyword in attr_name:
                                found_attributes[attr_id] = {
                                    "name": attr.Name,
                                    "id": attr_id,
                                    "type": attr.Type,
                                    "class_name": class_info["name"],
                                    "class_id": class_id,
                                    "keyword": keyword
                                }
                                logging.info("  - %s (ID: %s, Тип: %s) [%s]", 
                                           attr.Name, attr_id, attr.Type, keyword)
                                break
                else:
                    logging.info("Атрибуты не найдены")
                    
            except Exception as e:
                logging.error("Ошибка получения атрибутов для класса %s: %s", class_id, e)
        
        # --- Поиск объектов для тестирования ---
        logging.info("\n=== ПОИСК ОБЪЕКТОВ ДЛЯ ТЕСТИРОВАНИЯ ===")
        
        test_objects = []
        
        for class_id, class_info in list(found_classes.items())[:2]:  # Берем первые 2 класса
            logging.info("\nПоиск объектов в классе '%s':", class_info["name"])
            
            try:
                # Используем простой поиск без условий
                search_service = client.search
                objects = await search_service.query().with_class_id(class_id).find_all()
                
                if objects:
                    logging.info("Найдено объектов: %d", len(objects))
                    
                    # Берем первые 3 объекта
                    for obj in objects[:3]:
                        test_objects.append({
                            "id": str(obj.Id),
                            "name": obj.Name,
                            "class_id": str(obj.ClassId),
                            "class_name": class_info["name"],
                            "parent_id": str(obj.ParentId) if obj.ParentId else None,
                            "attributes": {}
                        })
                        
                        # Добавляем атрибуты если доступны
                        if hasattr(obj, 'Attributes') and obj.Attributes:
                            for attr_id, attr_value in obj.Attributes.items():
                                test_objects[-1]["attributes"][str(attr_id)] = attr_value
                        
                        logging.info("  - %s (ID: %s)", obj.Name, obj.Id)
                else:
                    logging.info("Объекты не найдены")
                    
            except Exception as e:
                logging.error("Ошибка поиска объектов в классе %s: %s", class_id, e)
        
        # --- Сохранение результатов ---
        logging.info("\n=== СОХРАНЕНИЕ РЕЗУЛЬТАТОВ ===")
        
        os.makedirs("data", exist_ok=True)
        
        results = {
            "found_classes": found_classes,
            "found_attributes": found_attributes,
            "test_objects": test_objects,
            "summary": {
                "classes_found": len(found_classes),
                "attributes_found": len(found_attributes),
                "objects_found": len(test_objects)
            }
        }
        
        output_file = "data/actual_ids_for_testing.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        logging.info("Результаты сохранены в файл: %s", output_file)
        
        # --- Вывод рекомендаций ---
        logging.info("\n=== РЕКОМЕНДАЦИИ ДЛЯ ТЕСТИРОВАНИЯ ===")
        
        if found_classes:
            logging.info("Для тестирования поиска используйте следующие ID классов:")
            for class_id, class_info in list(found_classes.items())[:3]:
                logging.info("  - %s: %s", class_info["name"], class_id)
        
        if found_attributes:
            logging.info("\nДля тестирования поиска по атрибутам используйте:")
            for attr_id, attr_info in list(found_attributes.items())[:3]:
                logging.info("  - %s (%s): %s", attr_info["name"], attr_info["class_name"], attr_id)
        
        if test_objects:
            logging.info("\nДля тестирования фильтрации по родителю используйте:")
            for obj in test_objects[:3]:
                if obj["parent_id"]:
                    logging.info("  - %s: %s", obj["name"], obj["parent_id"])


if __name__ == "__main__":
    # Для Windows, где может быть ошибка с ProactorEventLoop
    if os.name == "nt":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
