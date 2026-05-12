"""
Пример использования нового Fluent Search API (SearchQueryBuilder)
для удобного поиска объектов в Неосинтез.
"""

import asyncio
import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

from neosintez_api import NeosintezAPIError, NeosintezClient
from neosintez_api.core.enums import SearchOperatorType
from neosintez_api.services import ClassService


# Настройка логирования для вывода информации в консоль
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


async def main():
    """
    Главная функция для демонстрации поиска.
    """
    load_dotenv()
    # Подключение к API Неосинтез
    async with NeosintezClient() as client:
        # Получаем сервисы через свойства клиента
        search_service = client.search
        class_service = ClassService(client)

        try:
            class_name = "Электронная спецификация"

            all_objects = (
                await search_service.query()
                .with_class_name(class_name)
                .with_attribute_name("Шифр комплекта", "", SearchOperatorType.EXISTS)
                .with_attribute_name("Объект строительства", "", SearchOperatorType.EXISTS)
                # .with_attribute_name("Актуальность", "Да")
                .find_all()
            )
            logging.info(f"Найдено {len(all_objects)} объектов c классом '{class_name}'")

            # Сохранение полезной нагрузки запроса (payload) один раз, если её ещё нет
            # ВАЖНО: сервер ожидает GUID'ы класса и атрибутов, поэтому получаем их через ClassService
            payload_path = Path("payload_specs_search.json")
            if not payload_path.exists():
                try:
                    # Найти класс по имени (берём точное совпадение)
                    found_classes = await class_service.find_by_name(class_name)
                    target_class = next((c for c in found_classes if c.Name == class_name), None)
                    if not target_class:
                        raise ValueError(f"Класс '{class_name}' не найден для сохранения payload")

                    class_id = str(target_class.Id)

                    # Получить атрибуты класса и найти нужные по имени
                    attrs = await class_service.get_attributes(class_id)
                    def find_attr_id(name: str) -> str:
                        attr = next((a for a in attrs if a.Name == name), None)
                        if not attr:
                            raise ValueError(f"Атрибут '{name}' не найден в классе '{class_name}'")
                        return str(attr.Id)

                    attr_cipher_id = find_attr_id("Шифр комплекта")
                    attr_object_id = find_attr_id("Объект строительства")

                    # Минимально достаточный payload для API: BY_CLASS + два условия ATTRIBUTE EXISTS
                    # Типы соответствуют: Filter.Type=5 (BY_CLASS), Condition.Type=1 (ATTRIBUTE), Operator=7 (EXISTS)
                    payload = {
                        "Filters": [
                            {"Type": 5, "Value": class_id},
                        ],
                        "Conditions": [
                            {"Type": 1, "Attribute": attr_cipher_id, "Operator": int(SearchOperatorType.EXISTS)},
                            {"Type": 1, "Attribute": attr_object_id, "Operator": int(SearchOperatorType.EXISTS)},
                        ],
                        "Mode": 1,
                    }

                    payload_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
                    logging.info("Сохранён payload поиска в %s", payload_path)
                except Exception as write_err:
                    logging.warning("Не удалось сохранить payload: %s", write_err)

        except (ValueError, NeosintezAPIError) as e:
            logging.error(f"Ошибка: {e}", exc_info=True)


if __name__ == "__main__":
    # Для Windows, где может быть ошибка с ProactorEventLoop
    if os.name == "nt":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
