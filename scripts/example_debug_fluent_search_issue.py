"""
Диагностический пример для выявления проблемы с fluent API и оператором EXISTS.

Проблема: Fluent API формирует неправильный запрос для оператора EXISTS,
что приводит к ошибке 500 от API Неосинтез.
"""

import asyncio
import json
import logging
import os
from typing import Any, Dict, Tuple

from dotenv import load_dotenv

from neosintez_api import NeosintezAPIError, NeosintezClient
from neosintez_api.core.enums import SearchOperatorType


# Настройка логирования
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def make_raw_request_with_payload_logging(client: NeosintezClient, payload: Dict[str, Any]) -> Tuple[int, Any]:
    """
    Выполняет сырой HTTP запрос с логированием payload.

    Args:
        client: Экземпляр NeosintezClient
        payload: Данные запроса

    Returns:
        Tuple[int, Any]: Статус ответа и тело ответа
    """
    logger.info("🔍 Выполняю сырой HTTP запрос...")
    logger.info(f"📤 Payload: {json.dumps(payload, indent=2, ensure_ascii=False)}")

    try:
        status, response_data = await client._request_raw(
            method="POST",
            endpoint="/api/objects/search?skip=0&take=20",
            data=payload,
            headers={"X-HTTP-Method-Override": "GET", "Accept": "application/json, text/plain, */*"},
        )

        logger.info(f"📥 Статус ответа: {status}")

        if status == 200:
            if isinstance(response_data, dict):
                result = response_data.get("Result", [])
                total = response_data.get("Total", 0)
                logger.info(f"✅ Получено {len(result)} объектов (Total: {total})")
            else:
                logger.warning(f"⚠️ Неожиданный формат ответа: {type(response_data)}")
        else:
            logger.error(f"❌ Ошибка API: {status} - {response_data}")

        return status, response_data

    except Exception as e:
        logger.error(f"❌ Ошибка при выполнении сырого запроса: {e}")
        raise


async def make_fluent_request_with_debugging(client: NeosintezClient) -> Tuple[int, Any]:
    """
    Выполняет fluent API запрос с детальной отладкой.

    Args:
        client: Экземпляр NeosintezClient

    Returns:
        Tuple[int, Any]: Статус ответа и тело ответа
    """
    logger.info("🔍 Выполняю fluent API запрос с отладкой...")

    try:
        search_service = client.search

        # Создаем fluent запрос
        logger.info("🔧 Создание fluent запроса...")
        query_builder = (
            search_service.query()
            .with_class_name("Объект эксплуатации")
            .with_attribute("94193ed0-2705-f011-91d5-005056b6948b", "", SearchOperatorType.EXISTS)
            .with_attribute("a2c63c73-de0a-f011-91d7-005056b6948b", "", SearchOperatorType.EXISTS)
        )

        logger.info("📝 Fluent запрос создан")

        # Попробуем получить внутренний запрос для анализа
        try:
            # Получаем внутренний объект запроса
            internal_request = query_builder._build_request()
            logger.info(
                f"📋 Внутренний запрос fluent API: {json.dumps(internal_request, indent=2, ensure_ascii=False)}"
            )
        except Exception as e:
            logger.warning(f"⚠️ Не удалось получить внутренний запрос: {e}")

        # Выполняем запрос
        logger.info("🚀 Выполняю fluent запрос...")
        objects = await query_builder.find_all()

        logger.info(f"📥 Получено {len(objects)} объектов через fluent API")
        return 200, {"Result": objects, "Total": len(objects)}

    except NeosintezAPIError as e:
        logger.error(f"❌ Ошибка API в fluent запросе: {e}")
        return 500, str(e)
    except Exception as e:
        logger.error(f"❌ Ошибка при выполнении fluent запроса: {e}")
        raise


async def compare_payloads():
    """
    Сравнивает payload'ы сырого и fluent запросов.
    """
    logger.info("🔍 Сравнение payload'ов сырого и fluent запросов...")

    # Рабочий payload для сырого запроса
    working_payload = {
        "Mode": 0,
        "Filters": [{"Type": 5, "Value": "8cedae0c-7e23-ed11-9141-005056b6948b"}],
        "Conditions": [
            {
                "Type": 1,
                "Direction": 1,  # INSIDE
                "Operator": 7,  # EXISTS
                "Logic": 0,
                "Attribute": "94193ed0-2705-f011-91d5-005056b6948b",
            },
            {
                "Type": 1,
                "Direction": 1,  # INSIDE
                "Operator": 7,  # EXISTS
                "Logic": 2,  # AND
                "Attribute": "a2c63c73-de0a-f011-91d7-005056b6948b",
            },
        ],
    }

    logger.info("📋 Рабочий payload (сырой запрос):")
    logger.info(json.dumps(working_payload, indent=2, ensure_ascii=False))

    # Анализируем проблемы в fluent API
    logger.info("\n🔍 Анализ проблем в fluent API:")
    logger.info("1. Проблема с полем 'Value': fluent API добавляет Value='' для EXISTS")
    logger.info("2. Проблема с полем 'Direction': fluent API устанавливает Direction=0 вместо 1")
    logger.info("3. Возможная проблема с логикой формирования запроса")

    return working_payload


async def test_different_approaches(client: NeosintezClient):
    """
    Тестирует различные подходы к формированию запроса.
    """
    logger.info("🔍 Тестирование различных подходов...")

    search_service = client.search

    # Подход 1: Только с with_attribute (без Value)
    logger.info("\n--- Подход 1: with_attribute без Value ---")
    try:
        query1 = (
            search_service.query()
            .with_class_name("Объект эксплуатации")
            .with_attribute("94193ed0-2705-f011-91d5-005056b6948b", None, SearchOperatorType.EXISTS)
        )
        objects1 = await query1.find_all()
        logger.info(f"✅ Подход 1: получено {len(objects1)} объектов")
    except Exception as e:
        logger.error(f"❌ Подход 1 не работает: {e}")

    # Подход 2: С with_attribute_name
    logger.info("\n--- Подход 2: with_attribute_name ---")
    try:
        query2 = (
            search_service.query()
            .with_class_name("Объект эксплуатации")
            .with_attribute_name("ТЭП объекта", None, SearchOperatorType.EXISTS)
        )
        objects2 = await query2.find_all()
        logger.info(f"✅ Подход 2: получено {len(objects2)} объектов")
    except Exception as e:
        logger.error(f"❌ Подход 2 не работает: {e}")

    # Подход 3: Ручное создание SearchRequest
    logger.info("\n--- Подход 3: Ручное создание SearchRequest ---")
    try:
        from neosintez_api.core.enums import SearchConditionType, SearchDirectionType, SearchFilterType, SearchLogicType
        from neosintez_api.models import SearchCondition, SearchFilter, SearchRequest

        manual_request = SearchRequest(
            Filters=[SearchFilter(Type=SearchFilterType.BY_CLASS, Value="8cedae0c-7e23-ed11-9141-005056b6948b")],
            Conditions=[
                SearchCondition(
                    Type=SearchConditionType.ATTRIBUTE,
                    Direction=SearchDirectionType.INSIDE,
                    Operator=SearchOperatorType.EXISTS,
                    Logic=SearchLogicType.NONE,
                    Attribute="94193ed0-2705-f011-91d5-005056b6948b",
                ),
                SearchCondition(
                    Type=SearchConditionType.ATTRIBUTE,
                    Direction=SearchDirectionType.INSIDE,
                    Operator=SearchOperatorType.EXISTS,
                    Logic=SearchLogicType.AND,
                    Attribute="a2c63c73-de0a-f011-91d7-005056b6948b",
                ),
            ],
            Mode=0,
        )

        objects3 = await client.objects.search_all(manual_request)
        logger.info(f"✅ Подход 3: получено {len(objects3)} объектов")
    except Exception as e:
        logger.error(f"❌ Подход 3 не работает: {e}")


async def main():
    """
    Главная функция диагностики.
    """
    logger.info("🚀 Запуск диагностики проблемы с fluent API")

    load_dotenv()

    async with NeosintezClient() as client:
        # Сравнение payload'ов
        working_payload = await compare_payloads()

        # Тест сырого запроса
        logger.info("\n" + "=" * 50)
        logger.info("🔍 ТЕСТ 1: Сырой HTTP запрос")
        logger.info("=" * 50)

        status1, response1 = await make_raw_request_with_payload_logging(client, working_payload)

        # Тест fluent запроса
        logger.info("\n" + "=" * 50)
        logger.info("🔍 ТЕСТ 2: Fluent API запрос")
        logger.info("=" * 50)

        status2, response2 = await make_fluent_request_with_debugging(client)

        # Тест различных подходов
        logger.info("\n" + "=" * 50)
        logger.info("🔍 ТЕСТ 3: Различные подходы")
        logger.info("=" * 50)

        await test_different_approaches(client)

        # Вывод результатов
        logger.info("\n" + "=" * 50)
        logger.info("📊 РЕЗУЛЬТАТЫ ДИАГНОСТИКИ")
        logger.info("=" * 50)

        logger.info(f"Сырой запрос: статус {status1}")
        logger.info(f"Fluent запрос: статус {status2}")

        if status1 == 200 and status2 != 200:
            logger.error("❌ ПРОБЛЕМА ПОДТВЕРЖДЕНА: fluent API не работает")
            logger.info("🔧 РЕКОМЕНДАЦИИ:")
            logger.info("1. Проверить формирование запроса в SearchQueryBuilder")
            logger.info("2. Исправить проблему с полем 'Value' для EXISTS")
            logger.info("3. Исправить проблему с полем 'Direction' для EXISTS")
            logger.info("4. Добавить тесты для оператора EXISTS")
        elif status1 == 200 and status2 == 200:
            logger.info("✅ Оба запроса работают корректно")
        else:
            logger.error("❌ Проблема с сырым запросом")


if __name__ == "__main__":
    if os.name == "nt":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
