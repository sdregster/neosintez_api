"""
Пример сырого поиска с одним фильтром и условием EXISTS.

Скрипт повторяет инфраструктуру `example_raw_equipment_search_request.py`, но использует
минимальную полезную нагрузку: один фильтр по классу и одно условие с оператором EXISTS.
"""

import asyncio
import json
import logging
import os
from uuid import UUID

from dotenv import load_dotenv

from neosintez_api import NeosintezAPIError, NeosintezClient
from neosintez_api.config import NeosintezConfig
from neosintez_api.core.enums import (
    SearchConditionType,
    SearchDirectionType,
    SearchLogicType,
    SearchOperatorType,
    SearchQueryMode,
)
from neosintez_api.models import SearchCondition, SearchFilter, SearchRequest
from neosintez_api.utils import CustomJSONEncoder


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


async def main() -> None:
    """
    Запускает поиск по минимальной сырой нагрузке (один фильтр + одно условие).
    """
    load_dotenv()

    config = NeosintezConfig()
    if "construction.irkutskoil.ru" in str(config.base_url):
        config.base_url = str(config.base_url).replace("construction", "operation")
        logging.info("Используем URL: %s", config.base_url)

    async with NeosintezClient(config) as client:
        logging.info("\n=== СОЗДАНИЕ МИНИМАЛЬНОГО СЫРОГО ЗАПРОСА ===")

        filters = [
            SearchFilter(
                Type=5,  # BY_CLASS
                Value="36029c57-c1be-f011-91fa-005056b6948b",
            ),
        ]

        conditions = [
            SearchCondition(
                Type=SearchConditionType.ATTRIBUTE,
                Attribute=UUID("723bba30-4175-ed11-9152-005056b6948b"),
                Operator=SearchOperatorType.EXISTS,
                Direction=SearchDirectionType.NONE,
                Logic=SearchLogicType.NONE,
            ),
        ]

        search_request = SearchRequest(
            Filters=filters,
            Conditions=conditions,
            Mode=SearchQueryMode.ACTUAL_ONLY,
        )

        logging.info("Создан запрос: 1 фильтр BY_CLASS и 1 условие EXISTS по атрибуту.")

        logging.info("\n=== ВЫПОЛНЕНИЕ ПОИСКА ===")
        try:
            logging.info("Отправляем запрос к API...")
            results = await client.objects.search_all(search_request)

            count = len(results)
            logging.info("Найдено объектов: %d", count)

            os.makedirs("data", exist_ok=True)
            output_file = "data/raw_minimal_search_results.json"
            serializable = [obj.model_dump(by_alias=True) for obj in results]
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump({"count": count, "results": serializable}, f, ensure_ascii=False, indent=2, cls=CustomJSONEncoder)
            logging.info("Сохранено в: %s", output_file)

        except NeosintezAPIError as e:
            logging.error("Ошибка API при выполнении поиска: %s", e)
            logging.error("Статус код: %d", e.status_code)
            if e.response_data:
                logging.error("Данные ответа: %s", e.response_data)
        except Exception as e:  # noqa: BLE001
            logging.error("Неожиданная ошибка: %s", e, exc_info=True)


if __name__ == "__main__":
    if os.name == "nt":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())

