"""
Рабочий пример сложного поиска с актуальными ID из системы.

Использует реальные ID классов и атрибутов, найденные в системе.
"""

import asyncio
import json
import logging
import os
from uuid import UUID

from dotenv import load_dotenv

from neosintez_api import NeosintezAPIError, NeosintezClient
from neosintez_api.core.enums import SearchConditionType, SearchLogicType, SearchOperatorType, SearchQueryMode
from neosintez_api.models import SearchCondition, SearchFilter, SearchRequest


# Настройка логирования для вывода информации в консоль
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


async def main():
    """
    Главная функция для демонстрации рабочего поиска.
    """
    load_dotenv()
    
    # Подключение к API Неосинтез
    async with NeosintezClient() as client:
        
        logging.info("\n=== РАБОЧИЙ ПРИМЕР СЛОЖНОГО ПОИСКА ===")
        
        # --- Используем актуальные ID из системы ---
        
        # ID классов (найденные в системе)
        class_ids = [
            "943b8289-3552-ea11-910d-005056b6948b",  # _Объекты (базовый)
            "b3a40bd4-9579-ea11-9110-005056b6948b",  # Элемент факторного анализа полной стоимости объектов
        ]
        
        # ID атрибутов (найденные в системе)
        attribute_name_id = "d7c2c661-1e78-ea11-9110-005056b6948b"  # Наименование объекта
        attribute_code_id = "c97567d2-5ce4-e911-80cf-9706d383f138"  # Код проекта
        
        logging.info("Используем актуальные ID из системы:")
        logging.info("  Классы: %d", len(class_ids))
        logging.info("  Атрибут наименования: %s", attribute_name_id)
        logging.info("  Атрибут кода: %s", attribute_code_id)
        
        # --- Создаем фильтры ---
        filters = []
        for class_id in class_ids:
            filters.append(SearchFilter(Type=5, Value=class_id))  # BY_CLASS
        
        # --- Создаем условия поиска ---
        conditions = [
            # Условие 1: Наименование содержит "объект" (EQUALS)
            SearchCondition(
                Type=SearchConditionType.ATTRIBUTE,
                Attribute=UUID(attribute_name_id),
                Operator=SearchOperatorType.CONTAINS,
                Value="объект",
                Logic=SearchLogicType.NONE,
            ),
            # Условие 2: Код проекта содержит "2024" (OR)
            SearchCondition(
                Type=SearchConditionType.ATTRIBUTE,
                Attribute=UUID(attribute_code_id),
                Operator=SearchOperatorType.CONTAINS,
                Value="2024",
                Logic=SearchLogicType.OR,
            ),
            # Условие 3: Код проекта содержит "2023" (OR)
            SearchCondition(
                Type=SearchConditionType.ATTRIBUTE,
                Attribute=UUID(attribute_code_id),
                Operator=SearchOperatorType.CONTAINS,
                Value="2023",
                Logic=SearchLogicType.OR,
            ),
        ]
        
        # --- Создаем поисковый запрос ---
        search_request = SearchRequest(
            Filters=filters,
            Conditions=conditions,
            Mode=SearchQueryMode.ACTUAL_ONLY,
        )
        
        logging.info("\nСоздан поисковый запрос:")
        logging.info("  Фильтры: %d классов", len(filters))
        logging.info("  Условия: %d (наименование содержит 'объект' AND (код содержит '2024' OR код содержит '2023'))", len(conditions))
        
        # --- Выполнение поиска ---
        logging.info("\n=== ВЫПОЛНЕНИЕ ПОИСКА ===")
        
        try:
            logging.info("Отправляем запрос к API...")
            results = await client.objects.search_all(search_request)
            
            # --- Обработка результатов ---
            logging.info("\n=== РЕЗУЛЬТАТЫ ПОИСКА ===")
            logging.info("Найдено объектов: %d", len(results))
            
            if results:
                # Выводим первые 10 результатов
                logging.info("\nПервые результаты:")
                for i, obj in enumerate(results[:10]):
                    logging.info("  %d. ID: %s", i + 1, obj.Id)
                    logging.info("     Имя: %s", obj.Name)
                    logging.info("     Класс: %s", obj.ClassId)
                    
                    # Показываем атрибуты если они доступны
                    if hasattr(obj, 'Attributes') and obj.Attributes:
                        name_attr = obj.Attributes.get(attribute_name_id)
                        code_attr = obj.Attributes.get(attribute_code_id)
                        if name_attr:
                            logging.info("     Наименование: %s", name_attr)
                        if code_attr:
                            logging.info("     Код проекта: %s", code_attr)
                    logging.info("")
                
                if len(results) > 10:
                    logging.info("... и ещё %d объектов.", len(results) - 10)
                
                # --- Сохранение результатов ---
                logging.info("\n=== СОХРАНЕНИЕ РЕЗУЛЬТАТОВ ===")
                
                os.makedirs("data", exist_ok=True)
                
                results_data = {
                    "search_config": {
                        "class_ids": class_ids,
                        "attribute_name_id": attribute_name_id,
                        "attribute_code_id": attribute_code_id,
                        "search_conditions": [
                            "наименование содержит 'объект'",
                            "код содержит '2024' OR код содержит '2023'"
                        ]
                    },
                    "raw_request": {
                        "filters": [{"type": f.Type, "value": f.Value} for f in filters],
                        "conditions": [
                            {
                                "type": c.Type,
                                "attribute": str(c.Attribute),
                                "operator": c.Operator,
                                "value": c.Value,
                                "logic": c.Logic,
                            } for c in conditions
                        ],
                        "mode": search_request.Mode,
                    },
                    "results_count": len(results),
                    "results": []
                }
                
                # Добавляем результаты
                for obj in results:
                    obj_data = {
                        "id": str(obj.Id),
                        "name": obj.Name,
                        "class_id": str(obj.ClassId),
                        "parent_id": str(obj.ParentId) if obj.ParentId else None,
                        "attributes": {}
                    }
                    
                    if hasattr(obj, 'Attributes') and obj.Attributes:
                        for attr_id, attr_value in obj.Attributes.items():
                            obj_data["attributes"][str(attr_id)] = attr_value
                    
                    results_data["results"].append(obj_data)
                
                # Сохраняем в файл
                output_file = "data/working_search_results.json"
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(results_data, f, ensure_ascii=False, indent=2)
                
                logging.info("Результаты сохранены в файл: %s", output_file)
                
                # --- Статистика ---
                logging.info("\n=== СТАТИСТИКА ===")
                
                # Статистика по классам
                class_stats = {}
                for obj in results:
                    class_id = str(obj.ClassId)
                    class_stats[class_id] = class_stats.get(class_id, 0) + 1
                
                logging.info("Распределение по классам:")
                for class_id, count in class_stats.items():
                    logging.info("  Класс %s: %d объектов", class_id, count)
                
                # Статистика по кодам проектов
                code_stats = {}
                for obj in results:
                    if hasattr(obj, 'Attributes') and obj.Attributes:
                        code_attr = obj.Attributes.get(attribute_code_id)
                        if code_attr:
                            code_stats[str(code_attr)] = code_stats.get(str(code_attr), 0) + 1
                
                if code_stats:
                    logging.info("\nРаспределение по кодам проектов:")
                    for code, count in list(code_stats.items())[:10]:  # Показываем первые 10
                        logging.info("  %s: %d объектов", code, count)
                
            else:
                logging.warning("Объекты не найдены.")
                logging.info("Попробуйте изменить условия поиска:")
                logging.info("  - Изменить ключевые слова в условиях")
                logging.info("  - Использовать другие операторы (EQUALS вместо CONTAINS)")
                logging.info("  - Добавить или убрать фильтры по классам")
                
        except NeosintezAPIError as e:
            logging.error("Ошибка API при выполнении поиска: %s", e)
            logging.error("Статус код: %d", e.status_code)
            if e.response_data:
                logging.error("Данные ответа: %s", e.response_data)
        except Exception as e:
            logging.error("Неожиданная ошибка: %s", e, exc_info=True)


if __name__ == "__main__":
    # Для Windows, где может быть ошибка с ProactorEventLoop
    if os.name == "nt":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
