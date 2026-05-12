"""
Пример использования сложного поискового запроса с множественными фильтрами и условиями.

Демонстрирует построение запроса аналогичного сырой нагрузке:
- Поиск в нескольких классах одновременно
- Фильтрация по родительскому объекту
- Множественные условия по атрибутам с разными операторами
- Использование логики OR для объединения альтернативных условий
"""

import asyncio
import json
import logging
import os

from dotenv import load_dotenv

from neosintez_api import NeosintezAPIError, NeosintezClient
from neosintez_api.core.enums import SearchLogicType, SearchOperatorType
from neosintez_api.services import ClassService
from neosintez_api.config import NeosintezConfig


# Настройка логирования для вывода информации в консоль
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


async def main():
    """
    Главная функция для демонстрации сложного поиска.
    """
    load_dotenv()

    # Создаем конфигурацию и переопределяем портал на operation при необходимости
    config = NeosintezConfig()
    if "construction.irkutskoil.ru" in str(config.base_url):
        config.base_url = str(config.base_url).replace("construction", "operation")
        logging.info("Используем URL: %s", config.base_url)

    # Подключение к API Неосинтез с переданной конфигурацией
    async with NeosintezClient(config) as client:
        # Получаем сервисы через свойства клиента
        search_service = client.search
        class_service = ClassService(client)

        # --- Конфигурация поиска на основе сырой нагрузки ---
        logging.info("\n=== КОНФИГУРАЦИЯ ПОИСКА ===")

        # ID классов для поиска (из сырой нагрузки Type=5)
        class_ids = [
            "4ae2f84c-2682-eb11-9113-005056b6948b",
            "d73b9192-06b9-eb11-9115-005056b6948b",
            "bf9214f7-2e82-eb11-9113-005056b6948b",
        ]

        # ID родительского объекта (из сырой нагрузки Type=4)
        parent_id = "a4e111df-a062-ee11-9184-005056b6948b"

        # ID атрибутов из сырой нагрузки
        attribute_type_id = "b106b50b-9337-ea11-9100-005056b6e70e"  # Тип объекта
        attribute_name_id = "d4c8b526-9337-ea11-9100-005056b6e70e"  # Наименование

        logging.info("Классы для поиска: %d", len(class_ids))
        logging.info("Родительский объект: %s", parent_id)
        logging.info("Атрибут типа объекта: %s", attribute_type_id)
        logging.info("Атрибут наименования: %s", attribute_name_id)

        # --- Получение информации о классах и атрибутах ---
        logging.info("\n=== ПОЛУЧЕНИЕ ИНФОРМАЦИИ О КЛАССАХ ===")

        class_info = {}
        for class_id in class_ids:
            try:
                class_obj = await class_service.get_by_id(class_id)
                if class_obj:
                    class_info[class_id] = {"name": class_obj.Name, "id": str(class_obj.Id)}
                    logging.info("Класс найден: %s (ID: %s)", class_obj.Name, class_id)
                else:
                    logging.warning("Класс с ID %s не найден", class_id)
            except NeosintezAPIError as e:
                logging.error("Ошибка получения класса %s: %s", class_id, e)

        # --- Получение информации об атрибутах ---
        logging.info("\n=== ПОЛУЧЕНИЕ ИНФОРМАЦИИ ОБ АТРИБУТАХ ===")

        attribute_info = {}
        if class_ids:
            # Используем первый найденный класс для получения атрибутов
            first_class_id = next(iter(class_info.keys()), None)
            if first_class_id:
                try:
                    attributes = await class_service.get_attributes(first_class_id)

                    # Ищем нужные атрибуты по ID
                    for attr in attributes:
                        attr_id = str(attr.Id)
                        if attr_id in [attribute_type_id, attribute_name_id]:
                            attribute_info[attr_id] = {"name": attr.Name, "id": attr_id, "type": attr.Type}
                            logging.info("Атрибут найден: %s (ID: %s, Тип: %s)", attr.Name, attr_id, attr.Type)

                except NeosintezAPIError as e:
                    logging.error("Ошибка получения атрибутов для класса %s: %s", first_class_id, e)

        # --- Построение сложного поискового запроса ---
        logging.info("\n=== ВЫПОЛНЕНИЕ СЛОЖНОГО ПОИСКА ===")

        try:
            # Строим запрос через fluent API
            query_builder = search_service.query()

            # Добавляем фильтры по классам
            for class_id in class_ids:
                query_builder.with_class_id(class_id)

            # Добавляем фильтр по родителю
            query_builder.with_parent_id(parent_id)

            # Добавляем первое условие: тип объекта = "Оборудование" (EQUALS)
            query_builder.with_attribute(attribute_type_id, "Оборудование", SearchOperatorType.EQUALS)

            # Добавляем условия по наименованию с логикой OR
            equipment_names = ["лафет", "Электродвигатель ОВиК", "гидрант", "Оборудование ОВиК"]

            for i, name in enumerate(equipment_names):
                # Для первого условия OR не указываем логику (автоматически станет AND)
                # Для остальных явно указываем OR
                logic = SearchLogicType.OR if i > 0 else SearchLogicType.NONE

                query_builder.with_attribute(attribute_name_id, name, SearchOperatorType.CONTAINS, logic)

            # Выполняем поиск
            logging.info("Выполняем поиск...")
            results = await query_builder.find_all()

            # --- Обработка результатов ---
            logging.info("\n=== РЕЗУЛЬТАТЫ ПОИСКА ===")
            logging.info("Найдено объектов: %d", len(results))

            if results:
                # Выводим первые 15 результатов
                logging.info("\nПервые результаты:")
                for i, obj in enumerate(results[:15]):
                    logging.info("  %d. ID: %s", i + 1, obj.Id)
                    logging.info("     Имя: %s", obj.Name)
                    logging.info("     Класс (EntityId): %s", obj.EntityId)

                    # Показываем атрибуты если они доступны
                    if hasattr(obj, "Attributes") and obj.Attributes:
                        type_attr = obj.Attributes.get(attribute_type_id)
                        name_attr = obj.Attributes.get(attribute_name_id)
                        if type_attr:
                            logging.info("     Тип объекта: %s", type_attr)
                        if name_attr:
                            logging.info("     Наименование: %s", name_attr)
                    logging.info("")

                if len(results) > 15:
                    logging.info("... и ещё %d объектов.", len(results) - 15)

                # --- Сохранение результатов в JSON ---
                logging.info("\n=== СОХРАНЕНИЕ РЕЗУЛЬТАТОВ ===")

                # Создаем директорию data если её нет
                os.makedirs("data", exist_ok=True)

                # Подготавливаем данные для сохранения
                results_data = {
                    "search_config": {
                        "class_ids": class_ids,
                        "parent_id": parent_id,
                        "attribute_type_id": attribute_type_id,
                        "attribute_name_id": attribute_name_id,
                        "equipment_names": equipment_names,
                    },
                    "class_info": class_info,
                    "attribute_info": attribute_info,
                    "results_count": len(results),
                    "results": [],
                }

                # Добавляем результаты
                for obj in results:
                    obj_data = {
                        "id": str(obj.Id),
                        "name": obj.Name,
                        "class_id": str(obj.ClassId),
                        "parent_id": str(obj.ParentId) if obj.ParentId else None,
                        "attributes": {},
                    }

                    # Добавляем атрибуты если они доступны
                    if hasattr(obj, "Attributes") and obj.Attributes:
                        for attr_id, attr_value in obj.Attributes.items():
                            obj_data["attributes"][attr_id] = attr_value

                    results_data["results"].append(obj_data)

                # Сохраняем в файл
                output_file = "data/complex_search_results.json"
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(results_data, f, ensure_ascii=False, indent=2)

                logging.info("Результаты сохранены в файл: %s", output_file)

                # --- Статистика ---
                logging.info("\n=== СТАТИСТИКА ===")

                # Статистика по классам
                class_stats = {}
                for obj in results:
                    class_id = str(obj.EntityId)
                    class_name = class_info.get(class_id, {}).get("name", "Неизвестный класс")
                    class_stats[class_name] = class_stats.get(class_name, 0) + 1

                logging.info("Распределение по классам:")
                for class_name, count in class_stats.items():
                    logging.info("  %s: %d объектов", class_name, count)

                # Статистика по типам оборудования
                equipment_stats = {}
                for obj in results:
                    if hasattr(obj, "Attributes") and obj.Attributes:
                        name_attr = obj.Attributes.get(attribute_name_id)
                        if name_attr:
                            # Ищем совпадения с нашими ключевыми словами
                            for keyword in equipment_names:
                                if keyword.lower() in str(name_attr).lower():
                                    equipment_stats[keyword] = equipment_stats.get(keyword, 0) + 1
                                    break

                if equipment_stats:
                    logging.info("\nРаспределение по типам оборудования:")
                    for equipment_type, count in equipment_stats.items():
                        logging.info("  %s: %d объектов", equipment_type, count)

            else:
                logging.warning("Объекты не найдены. Проверьте правильность ID классов, родителя и атрибутов.")

        except (ValueError, NeosintezAPIError) as e:
            logging.error("Ошибка при выполнении поиска: %s", e, exc_info=True)


if __name__ == "__main__":
    # Для Windows, где может быть ошибка с ProactorEventLoop
    if os.name == "nt":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
