"""
Тест исправления fluent API для оператора EXISTS.

Проверяет, что исправление в SearchQueryBuilder корректно обрабатывает
оператор EXISTS и передает "None" вместо пустой строки.
"""

import asyncio
import logging
import os

from dotenv import load_dotenv

from neosintez_api import NeosintezClient
from neosintez_api.core.enums import SearchOperatorType


# Настройка логирования
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def test_fluent_search_with_exists():
    """
    Тестирует fluent API с оператором EXISTS после исправления.
    """
    logger.info("🚀 Тестирование исправленного fluent API с оператором EXISTS")

    load_dotenv()

    async with NeosintezClient() as client:
        search_service = client.search

        # Тест 1: Простой EXISTS с пустой строкой
        logger.info("\n--- Тест 1: EXISTS с пустой строкой ---")
        try:
            objects1 = (
                await search_service.query()
                .with_class_name("Объект эксплуатации")
                .with_attribute("94193ed0-2705-f011-91d5-005056b6948b", "", SearchOperatorType.EXISTS)
                .find_all()
            )
            logger.info(f"✅ Тест 1: получено {len(objects1)} объектов")
        except Exception as e:
            logger.error(f"❌ Тест 1 не прошел: {e}")

        # Тест 2: EXISTS с None
        logger.info("\n--- Тест 2: EXISTS с None ---")
        try:
            objects2 = (
                await search_service.query()
                .with_class_name("Объект эксплуатации")
                .with_attribute("94193ed0-2705-f011-91d5-005056b6948b", None, SearchOperatorType.EXISTS)
                .find_all()
            )
            logger.info(f"✅ Тест 2: получено {len(objects2)} объектов")
        except Exception as e:
            logger.error(f"❌ Тест 2 не прошел: {e}")

        # Тест 3: EXISTS с именем атрибута (пустая строка)
        logger.info("\n--- Тест 3: EXISTS с именем атрибута (пустая строка) ---")
        try:
            objects3 = (
                await search_service.query()
                .with_class_name("Объект эксплуатации")
                .with_attribute_name("ТЭП объекта", "", SearchOperatorType.EXISTS)
                .find_all()
            )
            logger.info(f"✅ Тест 3: получено {len(objects3)} объектов")
        except Exception as e:
            logger.error(f"❌ Тест 3 не прошел: {e}")

        # Тест 4: EXISTS с именем атрибута (None)
        logger.info("\n--- Тест 4: EXISTS с именем атрибута (None) ---")
        try:
            objects4 = (
                await search_service.query()
                .with_class_name("Объект эксплуатации")
                .with_attribute_name("ТЭП объекта", None, SearchOperatorType.EXISTS)
                .find_all()
            )
            logger.info(f"✅ Тест 4: получено {len(objects4)} объектов")
        except Exception as e:
            logger.error(f"❌ Тест 4 не прошел: {e}")

        # Тест 5: Двойной EXISTS (как в оригинальной проблеме)
        logger.info("\n--- Тест 5: Двойной EXISTS (как в оригинальной проблеме) ---")
        try:
            objects5 = (
                await search_service.query()
                .with_class_name("Объект эксплуатации")
                .with_attribute("94193ed0-2705-f011-91d5-005056b6948b", "", SearchOperatorType.EXISTS)
                .with_attribute("a2c63c73-de0a-f011-91d7-005056b6948b", "", SearchOperatorType.EXISTS)
                .find_all()
            )
            logger.info(f"✅ Тест 5: получено {len(objects5)} объектов")

            # Проверяем, что получили ожидаемое количество
            if len(objects5) == 4:
                logger.info("🎯 ЦЕЛЕВОЙ ПОКАЗАТЕЛЬ ДОСТИГНУТ: 4 объекта")
            else:
                logger.warning(f"⚠️ Неожиданное количество объектов: {len(objects5)} (ожидалось 4)")

        except Exception as e:
            logger.error(f"❌ Тест 5 не прошел: {e}")

        # Тест 6: Сравнение с сырым запросом
        logger.info("\n--- Тест 6: Сравнение с сырым запросом ---")
        try:
            # Сырой запрос для сравнения
            raw_payload = {
                "Mode": 0,
                "Filters": [{"Type": 5, "Value": "8cedae0c-7e23-ed11-9141-005056b6948b"}],
                "Conditions": [
                    {
                        "Type": 1,
                        "Direction": 1,
                        "Operator": 7,
                        "Logic": 0,
                        "Attribute": "94193ed0-2705-f011-91d5-005056b6948b",
                    },
                    {
                        "Type": 1,
                        "Direction": 1,
                        "Operator": 7,
                        "Logic": 2,
                        "Attribute": "a2c63c73-de0a-f011-91d7-005056b6948b",
                    },
                ],
            }

            status, response_data = await client._request_raw(
                method="POST",
                endpoint="/api/objects/search?skip=0&take=20",
                data=raw_payload,
                headers={"X-HTTP-Method-Override": "GET", "Accept": "application/json, text/plain, */*"},
            )

            if status == 200:
                raw_objects = response_data.get("Result", [])
                logger.info(f"📊 Сырой запрос: {len(raw_objects)} объектов")

                # Сравниваем с fluent запросом
                if len(objects5) == len(raw_objects):
                    logger.info("✅ Количество объектов совпадает!")
                else:
                    logger.warning(f"⚠️ Разное количество объектов: fluent={len(objects5)}, raw={len(raw_objects)}")
            else:
                logger.error(f"❌ Сырой запрос не прошел: статус {status}")

        except Exception as e:
            logger.error(f"❌ Тест 6 не прошел: {e}")


async def main():
    """
    Главная функция тестирования.
    """
    logger.info("🚀 Запуск тестирования исправления fluent API")

    try:
        await test_fluent_search_with_exists()
        logger.info("\n🎉 ТЕСТИРОВАНИЕ ЗАВЕРШЕНО!")
    except Exception as e:
        logger.error(f"❌ Ошибка при тестировании: {e}")
        import traceback

        logger.error(f"Трассировка: {traceback.format_exc()}")


if __name__ == "__main__":
    if os.name == "nt":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
