"""
Простой рабочий пример поиска для тестирования API.

Использует минимальные условия для проверки работоспособности поиска.
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
    Главная функция для демонстрации простого поиска.
    """
    load_dotenv()
    
    # Подключение к API Неосинтез
    async with NeosintezClient() as client:
        
        logging.info("\n=== ПРОСТОЙ ПРИМЕР ПОИСКА ===")
        
        # --- Тест 1: Поиск только по классу (без условий) ---
        logging.info("\n--- Тест 1: Поиск только по классу ---")
        
        try:
            # Используем только один класс
            class_id = "943b8289-3552-ea11-910d-005056b6948b"  # _Объекты (базовый)
            
            filters = [SearchFilter(Type=5, Value=class_id)]  # BY_CLASS
            conditions = []  # Без условий
            
            search_request = SearchRequest(
                Filters=filters,
                Conditions=conditions,
                Mode=SearchQueryMode.ACTUAL_ONLY,
            )
            
            logging.info("Поиск в классе %s без условий...", class_id)
            results = await client.objects.search_all(search_request)
            
            logging.info("Найдено объектов: %d", len(results))
            
            if results:
                logging.info("Первые 3 объекта:")
                for i, obj in enumerate(results[:3]):
                    logging.info("  %d. %s (ID: %s)", i + 1, obj.Name, obj.Id)
            
        except Exception as e:
            logging.error("Ошибка в тесте 1: %s", e)
        
        # --- Тест 2: Поиск с одним простым условием ---
        logging.info("\n--- Тест 2: Поиск с одним условием ---")
        
        try:
            class_id = "943b8289-3552-ea11-910d-005056b6948b"
            attribute_id = "d7c2c661-1e78-ea11-9110-005056b6948b"  # Наименование объекта
            
            filters = [SearchFilter(Type=5, Value=class_id)]
            conditions = [
                SearchCondition(
                    Type=SearchConditionType.ATTRIBUTE,
                    Attribute=UUID(attribute_id),
                    Operator=SearchOperatorType.EQUALS,
                    Value="тест",  # Простое значение
                    Logic=SearchLogicType.NONE,
                )
            ]
            
            search_request = SearchRequest(
                Filters=filters,
                Conditions=conditions,
                Mode=SearchQueryMode.ACTUAL_ONLY,
            )
            
            logging.info("Поиск с условием 'наименование = тест'...")
            results = await client.objects.search_all(search_request)
            
            logging.info("Найдено объектов: %d", len(results))
            
            if results:
                logging.info("Найденные объекты:")
                for i, obj in enumerate(results[:5]):
                    logging.info("  %d. %s (ID: %s)", i + 1, obj.Name, obj.Id)
            
        except Exception as e:
            logging.error("Ошибка в тесте 2: %s", e)
        
        # --- Тест 3: Поиск с условием EXISTS ---
        logging.info("\n--- Тест 3: Поиск с условием EXISTS ---")
        
        try:
            class_id = "943b8289-3552-ea11-910d-005056b6948b"
            attribute_id = "d7c2c661-1e78-ea11-9100-005056b6948b"  # Наименование объекта
            
            filters = [SearchFilter(Type=5, Value=class_id)]
            conditions = [
                SearchCondition(
                    Type=SearchConditionType.ATTRIBUTE,
                    Attribute=UUID(attribute_id),
                    Operator=SearchOperatorType.EXISTS,
                    Value="None",  # Для EXISTS используется "None"
                    Logic=SearchLogicType.NONE,
                )
            ]
            
            search_request = SearchRequest(
                Filters=filters,
                Conditions=conditions,
                Mode=SearchQueryMode.ACTUAL_ONLY,
            )
            
            logging.info("Поиск объектов с существующим атрибутом 'наименование'...")
            results = await client.objects.search_all(search_request)
            
            logging.info("Найдено объектов: %d", len(results))
            
            if results:
                logging.info("Первые 5 объектов с атрибутом:")
                for i, obj in enumerate(results[:5]):
                    logging.info("  %d. %s (ID: %s)", i + 1, obj.Name, obj.Id)
                    
                    # Показываем значение атрибута
                    if hasattr(obj, 'Attributes') and obj.Attributes:
                        name_value = obj.Attributes.get(attribute_id)
                        if name_value:
                            logging.info("     Наименование: %s", name_value)
            
        except Exception as e:
            logging.error("Ошибка в тесте 3: %s", e)
        
        # --- Тест 4: Поиск в нескольких классах ---
        logging.info("\n--- Тест 4: Поиск в нескольких классах ---")
        
        try:
            class_ids = [
                "943b8289-3552-ea11-910d-005056b6948b",  # _Объекты (базовый)
                "b3a40bd4-9579-ea11-9110-005056b6948b",  # Элемент факторного анализа
            ]
            
            filters = []
            for class_id in class_ids:
                filters.append(SearchFilter(Type=5, Value=class_id))
            
            conditions = []  # Без условий
            
            search_request = SearchRequest(
                Filters=filters,
                Conditions=conditions,
                Mode=SearchQueryMode.ACTUAL_ONLY,
            )
            
            logging.info("Поиск в %d классах без условий...", len(class_ids))
            results = await client.objects.search_all(search_request)
            
            logging.info("Найдено объектов: %d", len(results))
            
            if results:
                # Статистика по классам
                class_stats = {}
                for obj in results:
                    class_id = str(obj.ClassId)
                    class_stats[class_id] = class_stats.get(class_id, 0) + 1
                
                logging.info("Распределение по классам:")
                for class_id, count in class_stats.items():
                    logging.info("  Класс %s: %d объектов", class_id, count)
            
        except Exception as e:
            logging.error("Ошибка в тесте 4: %s", e)
        
        # --- Сохранение результатов всех тестов ---
        logging.info("\n=== СОХРАНЕНИЕ РЕЗУЛЬТАТОВ ===")
        
        os.makedirs("data", exist_ok=True)
        
        test_results = {
            "test_summary": {
                "description": "Простые тесты поиска для проверки работоспособности API",
                "tests_performed": [
                    "Поиск только по классу",
                    "Поиск с одним условием EQUALS",
                    "Поиск с условием EXISTS",
                    "Поиск в нескольких классах"
                ]
            },
            "note": "Если все тесты показывают 0 результатов, это может означать что в системе нет объектов в указанных классах или они не соответствуют условиям поиска."
        }
        
        output_file = "data/simple_search_test_results.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(test_results, f, ensure_ascii=False, indent=2)
        
        logging.info("Результаты тестов сохранены в файл: %s", output_file)


if __name__ == "__main__":
    # Для Windows, где может быть ошибка с ProactorEventLoop
    if os.name == "nt":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
