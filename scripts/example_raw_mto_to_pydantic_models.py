"""
Комбинированный пример: сырой MTO-поиск → Pydantic-модели.

1) Выполняет поиск по предоставленной нагрузке (МТО) на портале operation
2) Для каждого найденного объекта создаёт Pydantic-модель через ObjectToModelFactory
3) Сохраняет удобные для использования модельки в JSON
"""

import asyncio
import json
import logging
import os
from uuid import UUID

from dotenv import load_dotenv

from neosintez_api import NeosintezAPIError
from neosintez_api.config import NeosintezConfig
from neosintez_api.core.client import NeosintezClient
from neosintez_api.core.enums import (
    SearchConditionType,
    SearchLogicType,
    SearchOperatorType,
    SearchQueryMode,
)
from neosintez_api.models import SearchCondition, SearchFilter, SearchRequest
from neosintez_api.services import ObjectToModelFactory
from neosintez_api.utils import CustomJSONEncoder


# Настройка логирования
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


async def main() -> None:
    """
    Выполняет MTO-поиск и преобразует найденные объекты в Pydantic-модели.
    """
    load_dotenv()

    # Конфигурация и переключение на operation при необходимости
    config = NeosintezConfig()
    if "construction.irkutskoil.ru" in str(config.base_url):
        config.base_url = str(config.base_url).replace("construction", "operation")
        logging.info("Используем URL: %s", config.base_url)

    async with NeosintezClient(config) as client:
        # 1) Подготовка сырого запроса (из нагрузки по МТО)
        logging.info("\n=== СОЗДАНИЕ СЫРОГО MTO-ЗАПРОСА ===")

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

        search_request = SearchRequest(
            Filters=filters,
            Conditions=conditions,
            Mode=SearchQueryMode.ACTUAL_ONLY,
        )

        # 2) Выполнение поиска
        logging.info("\n=== ВЫПОЛНЕНИЕ ПОИСКА ===")
        try:
            results = await client.objects.search_all(search_request)
            count = len(results)
            logging.info("Найдено объектов: %d", count)

            if not results:
                logging.warning("Объекты не найдены. Прекращаю выполнение.")
                return

            # 3) Преобразование в Pydantic-модели
            logging.info("\n=== ПРЕОБРАЗОВАНИЕ В PYDANTIC-МОДЕЛИ ===")
            factory = ObjectToModelFactory(client)

            models_json: list[dict] = []
            for idx, obj in enumerate(results, 1):
                try:
                    blueprint = await factory.create_from_object_id(str(obj.Id))
                    models_json.append(blueprint.model_instance.model_dump(by_alias=True))
                    if idx % 25 == 0 or idx == count:
                        logging.info("Создано моделей: %d/%d", idx, count)
                except Exception as e:  # преобразование отдельных объектов может падать
                    logging.warning("Не удалось создать модель для объекта %s: %s", obj.Id, e)

            # 4) Сохранение моделей
            os.makedirs("data", exist_ok=True)
            output_file = "data/raw_mto_models.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump({"count": len(models_json), "models": models_json}, f, ensure_ascii=False, indent=2, cls=CustomJSONEncoder)
            logging.info("Сохранены модели: %s", output_file)

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


