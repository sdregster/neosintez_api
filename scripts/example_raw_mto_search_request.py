"""
Пример использования сырого поискового запроса напрямую.

Демонстрирует выполнение поиска с использованием точных данных из сырой нагрузки
без разрешения имен в ID. Позволяет быстро протестировать API запрос.
"""

import asyncio
import json
import logging
import os
from uuid import UUID

from dotenv import load_dotenv

from neosintez_api import NeosintezAPIError, NeosintezClient
from neosintez_api.config import NeosintezConfig
from neosintez_api.core.enums import SearchConditionType, SearchLogicType, SearchOperatorType, SearchQueryMode
from neosintez_api.utils import CustomJSONEncoder
from neosintez_api.models import SearchCondition, SearchFilter, SearchRequest


# Настройка логирования для вывода информации в консоль
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


async def main():
    """
    Главная функция для демонстрации сырого поискового запроса.
    """
    load_dotenv()

    # Создаем конфигурацию и переопределяем портал на operation при необходимости
    config = NeosintezConfig()
    if "construction.irkutskoil.ru" in str(config.base_url):
        config.base_url = str(config.base_url).replace("construction", "operation")
        logging.info("Используем URL: %s", config.base_url)

    # Подключение к API Неосинтез с переданной конфигурацией
    async with NeosintezClient(config) as client:
        # --- Сырые данные из нагрузки ---
        logging.info("\n=== СОЗДАНИЕ СЫРОГО ЗАПРОСА ===")

        # Создаем фильтры точно как в предоставленной нагрузке (МТО)
        filters = [
            SearchFilter(Type=5, Value="4ae2f84c-2682-eb11-9113-005056b6948b"),
            SearchFilter(Type=5, Value="d73b9192-06b9-eb11-9115-005056b6948b"),
            SearchFilter(Type=5, Value="bf9214f7-2e82-eb11-9113-005056b6948b"),
            SearchFilter(Type=5, Value="507a0276-3082-eb11-9113-005056b6948b"),
            SearchFilter(Type=5, Value="7e6e4b3b-2f82-eb11-9113-005056b6948b"),
            SearchFilter(Type=5, Value="0903e553-3082-eb11-9113-005056b6948b"),
            SearchFilter(Type=5, Value="ec577614-d0bd-eb11-9115-005056b6948b"),
            SearchFilter(Type=5, Value="7eeca8ed-2f82-eb11-9113-005056b6948b"),
            SearchFilter(Type=5, Value="555a3d6d-2f82-eb11-9113-005056b6948b"),
            SearchFilter(Type=5, Value="437cf2e2-4331-ec11-9117-005056b6948b"),
            SearchFilter(Type=5, Value="a1bfb596-2f82-eb11-9113-005056b6948b"),
            SearchFilter(Type=5, Value="6cc01bd7-2482-eb11-9113-005056b6948b"),
            SearchFilter(Type=5, Value="79809e76-2582-eb11-9113-005056b6948b"),
            SearchFilter(Type=5, Value="f683409c-26c7-eb11-9115-005056b6948b"),
            SearchFilter(Type=5, Value="980a96c8-2582-eb11-9113-005056b6948b"),
            SearchFilter(Type=5, Value="dad9b034-3082-eb11-9113-005056b6948b"),
            SearchFilter(Type=4, Value="a4e111df-a062-ee11-9184-005056b6948b"),
        ]

        # Создаем условия точно как в предоставленной нагрузке (МТО)
        conditions = [
            SearchCondition(
                Type=SearchConditionType.ATTRIBUTE,
                Attribute=UUID("b106b50b-9337-ea11-9100-005056b6e70e"),
                Operator=SearchOperatorType.NOT_EQUALS,
                Value="Оборудование",
                Logic=SearchLogicType.NONE,
            ),
            SearchCondition(
                Type=SearchConditionType.ATTRIBUTE,
                Attribute=UUID("d4c8b526-9337-ea11-9100-005056b6e70e"),
                Operator=SearchOperatorType.NOT_CONTAINS,
                Value="лафет",
                Logic=SearchLogicType.OR,
            ),
            SearchCondition(
                Type=SearchConditionType.ATTRIBUTE,
                Attribute=UUID("d4c8b526-9337-ea11-9100-005056b6e70e"),
                Operator=SearchOperatorType.NOT_CONTAINS,
                Value="Электродвигатель ОВиК",
                Logic=SearchLogicType.OR,
            ),
            SearchCondition(
                Type=SearchConditionType.ATTRIBUTE,
                Attribute=UUID("d4c8b526-9337-ea11-9100-005056b6e70e"),
                Operator=SearchOperatorType.NOT_CONTAINS,
                Value="гидрант",
                Logic=SearchLogicType.OR,
            ),
            SearchCondition(
                Type=SearchConditionType.ATTRIBUTE,
                Attribute=UUID("d4c8b526-9337-ea11-9100-005056b6e70e"),
                Operator=SearchOperatorType.NOT_CONTAINS,
                Value="Оборудование ОВиК",
                Logic=SearchLogicType.OR,
            ),
        ]

        # Создаем поисковый запрос
        search_request = SearchRequest(
            Filters=filters,
            Conditions=conditions,
            Mode=SearchQueryMode.ACTUAL_ONLY,
        )

        logging.info("Создан поисковый запрос:")
        logging.info("  Фильтры: %d (3 класса + 1 родитель)", len(filters))
        logging.info("  Условия: %d (1 EQUALS + 4 CONTAINS с OR)", len(conditions))
        logging.info("  Режим: ACTUAL_ONLY")

        # --- Выполнение поиска ---
        logging.info("\n=== ВЫПОЛНЕНИЕ ПОИСКА ===")

        try:
            # Выполняем поиск напрямую через клиент
            logging.info("Отправляем запрос к API...")
            results = await client.objects.search_all(search_request)

            # Короткий вывод
            count = len(results)
            logging.info("Найдено объектов: %d", count)

            # Сохраняем полный ответ в JSON
            os.makedirs("data", exist_ok=True)
            output_file = "data/raw_mto_search_results.json"
            serializable = [obj.model_dump(by_alias=True) for obj in results]
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump({"count": count, "results": serializable}, f, ensure_ascii=False, indent=2, cls=CustomJSONEncoder)
            logging.info("Сохранено в: %s", output_file)

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
