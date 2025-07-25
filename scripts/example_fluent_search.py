"""
Пример использования нового Fluent Search API (SearchQueryBuilder)
для удобного поиска объектов в Неосинтез.
"""

import asyncio
import logging
import os

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

        # --- Пример 1: Найти один объект по имени и имени класса ---
        logging.info("\n--- Пример 1: Поиск одного объекта по имени и классу (по имени) ---")
        try:
            class_name = "Объект капитальных вложений"
            object_name = "Газопровод с метанолопроводом от узла задвижек до скв. № 24"

            # Цепочка вызовов теперь полностью синхронна до .find_one()
            found_object = await search_service.query().with_name(object_name).with_class_name(class_name).find_one()

            if found_object:
                logging.info(f"Найден объект: ID={found_object.Id}, Имя='{found_object.Name}'")
            else:
                logging.warning(f"Объект с именем '{object_name}' в классе '{class_name}' не найден.")
        except (ValueError, NeosintezAPIError) as e:
            logging.error(f"Ошибка в Примере 1: {e}", exc_info=True)

        # --- Пример 2: Поиск всех объектов в классе с фильтром по родителю ---
        logging.info("\n--- Пример 2: Поиск всех объектов в классе с фильтром по родителю ---")
        try:
            class_name = "Объект капитальных вложений"
            parent_id = "46303b37-eefd-ee11-91a4-005056b6948b"

            all_objects = await search_service.query().with_class_name(class_name).with_parent_id(parent_id).find_all()

            logging.info(f"Найдено {len(all_objects)} объектов в классе '{class_name}' с родителем {parent_id}.")
            # Показываем первые 5 для краткости
            for i, p_line in enumerate(all_objects[:5]):
                logging.info(f"  {i + 1}. ID={p_line.Id}, Имя='{p_line.Name}'")

        except (ValueError, NeosintezAPIError) as e:
            logging.error(f"Ошибка в Примере 2: {e}", exc_info=True)

        # --- Пример 3: Поиск по имени класса и имени атрибута ---
        logging.info("\n--- Пример 3: Поиск по имени класса и имени атрибута ---")
        try:
            class_name = "Объект капитальных вложений"
            attribute_name = "МВЗ"
            attribute_value = "МВЗ015343"

            # Используем новый метод with_attribute_name для поиска по имени атрибута
            equipment_by_attr = (
                await search_service.query()
                .with_class_name(class_name)
                .with_attribute_name(attribute_name, attribute_value)
                .find_all()
            )

            logging.info(
                f"Найдено {len(equipment_by_attr)} объектов с атрибутом '{attribute_name}' = '{attribute_value}'."
            )
            for item in equipment_by_attr:
                logging.info(f"  - ID={item.Id}, Имя='{item.Name}'")

        except (ValueError, NeosintezAPIError) as e:
            logging.error(f"Ошибка в Примере 3: {e}", exc_info=True)

        # --- Пример 4: Поиск с использованием ID атрибута (если известен) ---
        logging.info("\n--- Пример 4: Поиск с использованием ID атрибута (если известен) ---")
        try:
            class_name = "Объект капитальных вложений"
            attribute_name = "МВЗ"
            attribute_value = "МВЗ015343"

            # 1. Сначала получаем ID атрибута для демонстрации прямого поиска по ID
            found_classes = await class_service.find_by_name(class_name)
            target_class = next((c for c in found_classes if c.Name.lower() == class_name.lower()), None)

            if target_class:
                attributes = await class_service.get_attributes(str(target_class.Id))
                target_attribute = next((a for a in attributes if a.Name == attribute_name), None)

                if target_attribute:
                    attribute_id = str(target_attribute.Id)
                    logging.info(f"Найден ID для атрибута '{attribute_name}': {attribute_id}")

                    # 2. Выполняем поиск по ID атрибута
                    equipment_by_attr_id = (
                        await search_service.query()
                        .with_class_name(class_name)
                        .with_attribute(attribute_id, attribute_value)
                        .find_all()
                    )

                    logging.info(
                        f"Найдено {len(equipment_by_attr_id)} объектов с атрибутом ID '{attribute_id}' = '{attribute_value}'."
                    )
                    for item in equipment_by_attr_id:
                        logging.info(f"  - ID={item.Id}, Имя='{item.Name}'")
                else:
                    logging.warning(f"Атрибут '{attribute_name}' не найден в классе '{class_name}'.")
            else:
                logging.warning(f"Класс '{class_name}' не найден.")

        except (ValueError, NeosintezAPIError) as e:
            logging.error(f"Ошибка в Примере 4: {e}", exc_info=True)

        # --- Пример 5: Поиск объектов с существующим атрибутом (любое значение) ---
        logging.info("\n--- Пример 5: Поиск объектов с существующим атрибутом МВЗ (любое значение) ---")
        try:
            class_name = "Объект капитальных вложений"
            attribute_name = "МВЗ"

            # Используем оператор EXISTS для поиска объектов, где атрибут просто существует
            # Значение может быть пустой строкой, поскольку для EXISTS важен только факт существования
            objects_with_mvz = (
                await search_service.query()
                .with_class_name(class_name)
                .with_attribute_name(attribute_name, "", SearchOperatorType.EXISTS)
                .find_all()
            )

            logging.info(
                f"Найдено {len(objects_with_mvz)} объектов класса '{class_name}' с существующим атрибутом '{attribute_name}'."
            )

            # Показываем первые 10 объектов с их значениями МВЗ для демонстрации
            for i, obj in enumerate(objects_with_mvz[:10]):
                logging.info(f"  {i + 1}. ID={obj.Id}, Имя='{obj.Name}'")
                # Если доступны атрибуты, показываем значение МВЗ
                if hasattr(obj, "Attributes") and obj.Attributes:
                    mvz_attr = obj.Attributes.get(attribute_name)
                    if mvz_attr is not None:
                        logging.info(f"     МВЗ: {mvz_attr}")

            if len(objects_with_mvz) > 10:
                logging.info(f"  ... и ещё {len(objects_with_mvz) - 10} объектов.")

        except (ValueError, NeosintezAPIError) as e:
            logging.error(f"Ошибка в Примере 5: {e}", exc_info=True)

        # --- Пример 6: Статистический анализ объектов с атрибутом МВЗ ---
        logging.info("\n--- Пример 6: Статистический анализ объектов с атрибутом МВЗ ---")
        try:
            class_name = "Объект капитальных вложений"
            attribute_name = "МВЗ"

            # 1. Запрос всех объектов класса без условий
            logging.info(f"Получаем все объекты класса '{class_name}'...")
            all_objects = await search_service.query().with_class_name(class_name).find_all()
            total_count = len(all_objects)
            logging.info(f"Всего объектов в классе: {total_count}")

            # 2. Запрос объектов где МВЗ существует
            logging.info(f"Получаем объекты с существующим атрибутом '{attribute_name}'...")
            objects_with_mvz = (
                await search_service.query()
                .with_class_name(class_name)
                .with_attribute_name(attribute_name, "", SearchOperatorType.EXISTS)
                .find_all()
            )
            with_mvz_count = len(objects_with_mvz)
            logging.info(f"Объектов с заполненным МВЗ: {with_mvz_count}")

            # 3. Запрос объектов где МВЗ НЕ существует
            logging.info(f"Получаем объекты без атрибута '{attribute_name}'...")
            objects_without_mvz = (
                await search_service.query()
                .with_class_name(class_name)
                .with_attribute_name(attribute_name, "", SearchOperatorType.NOT_EXISTS)
                .find_all()
            )
            without_mvz_count = len(objects_without_mvz)
            logging.info(f"Объектов без МВЗ: {without_mvz_count}")

            # 4. Проверка и вывод статистики
            calculated_total = with_mvz_count + without_mvz_count
            logging.info("\n=== СТАТИСТИКА ===")
            logging.info(f"Всего объектов:           {total_count}")
            logging.info(f"С заполненным МВЗ:        {with_mvz_count} ({with_mvz_count / total_count * 100:.1f}%)")
            logging.info(
                f"Без МВЗ:                  {without_mvz_count} ({without_mvz_count / total_count * 100:.1f}%)"
            )
            logging.info(f"Сумма (с МВЗ + без МВЗ):  {calculated_total}")

            # Проверка корректности данных
            if calculated_total == total_count:
                logging.info("✅ Статистика корректна: сумма совпадает с общим количеством")
            else:
                logging.warning(f"⚠️  Несоответствие данных: {calculated_total} != {total_count}")
                logging.warning("Возможно, есть объекты с частично заполненными атрибутами или особые случаи")

            # Показываем несколько примеров объектов без МВЗ
            if without_mvz_count > 0:
                logging.info(f"\nПримеры объектов без атрибута '{attribute_name}':")
                for i, obj in enumerate(objects_without_mvz[:5]):
                    logging.info(f"  {i + 1}. ID={obj.Id}, Имя='{obj.Name}'")

        except (ValueError, NeosintezAPIError) as e:
            logging.error(f"Ошибка в Примере 6: {e}", exc_info=True)


if __name__ == "__main__":
    # Для Windows, где может быть ошибка с ProactorEventLoop
    if os.name == "nt":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
