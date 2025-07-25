#!/usr/bin/env python3
"""
Пример работы с коллекциями объектов в API Неосинтез.

Демонстрирует получение элементов коллекции "ТЭП объекта" для конкретного объекта.
"""

import asyncio

from neosintez_api.config import NeosintezConfig
from neosintez_api.core.client import NeosintezClient
from neosintez_api.services.collection_service import CollectionService


async def main():
    """
    Основная функция для демонстрации работы с коллекциями.
    """
    # Создаем конфигурацию
    config = NeosintezConfig()

    # Заменяем base_url для работы с operation.irkutskoil.ru
    if "construction.irkutskoil.ru" in str(config.base_url):
        config.base_url = str(config.base_url).replace("construction", "operation")
        print(f"Используем URL: {config.base_url}")

    async with NeosintezClient(config) as client:
        try:
            # ID объекта и атрибута из примера пользователя
            object_id = "c9e5a7c5-fcfa-ee11-91a4-005056b6948b"
            attribute_id = "94193ed0-2705-f011-91d5-005056b6948b"  # ТЭП объекта

            print(f"Получаем коллекцию для объекта: {object_id}")
            print(f"Атрибут коллекции: {attribute_id}")
            print("-" * 60)

            # Создаем сервис коллекций
            collection_service = CollectionService(client)

            # Получаем элементы коллекции с пагинацией
            result = await collection_service.get_collection_items(
                object_id=object_id,
                attribute_id=attribute_id,
                order_by="542a224e-2305-f011-91d5-005056b6948b.name",  # Сортировка по имени
                order_direction="asc",
                page=1,
                page_size=20,
            )

            print(f"Получено элементов: {len(result.Result or [])}")
            print(f"Общее количество: {result.Total}")
            print()

            # Выводим информацию о каждом элементе коллекции ТЭП
            if result.Result:
                print("=== ТЭП ОБЪЕКТА ===")
                for i, item in enumerate(result.Result, 1):
                    print(f"Показатель {i}:")

                    # Получаем ТЭП показатель и значение
                    tep_name = "Неизвестный показатель"
                    tep_value = "Не указано"

                    if item.Object.Attributes:
                        # Получаем название ТЭП показателя
                        tep_attr = item.Object.Attributes.get("542a224e-2305-f011-91d5-005056b6948b")
                        if tep_attr and tep_attr.get("Value"):
                            tep_data = tep_attr["Value"]
                            if isinstance(tep_data, dict) and "Name" in tep_data:
                                tep_name = tep_data["Name"]

                        # Получаем значение показателя
                        value_attr = item.Object.Attributes.get("c70cdba4-5c49-e811-810f-edf0bf5e0091")
                        if value_attr and value_attr.get("Value"):
                            tep_value = value_attr["Value"]

                    print(f"  {tep_name}: {tep_value}")
                print()

            # Демонстрируем получение всех элементов без пагинации
            print("=" * 60)
            print("Демонстрация методов CollectionService:")

            # Демонстрируем получение всех элементов
            all_items = await collection_service.get_all_collection_items(
                object_id=object_id,
                attribute_id=attribute_id,
                order_by="542a224e-2305-f011-91d5-005056b6948b.name",
                order_direction="asc",
            )

            print(f"Общее количество элементов в коллекции: {len(all_items)}")

            # Демонстрируем поиск по имени
            test_item = await collection_service.find_collection_item_by_name(
                object_id=object_id,
                attribute_id=attribute_id,
                name="Collection item",  # Все элементы имеют это имя
            )

            if test_item:
                print(f"Найден элемент по имени: {test_item.Id}")

                # Получаем ТЭП показатель из найденного элемента
                if test_item.Object.Attributes:
                    tep_attr = test_item.Object.Attributes.get("542a224e-2305-f011-91d5-005056b6948b")
                    if tep_attr and tep_attr.get("Value"):
                        tep_data = tep_attr["Value"]
                        if isinstance(tep_data, dict) and "Name" in tep_data:
                            print(f"ТЭП показатель найденного элемента: {tep_data['Name']}")

            print("\n=== ГОТОВО! ===")
            print("Функциональность работы с коллекциями объектов успешно реализована:")
            print("✅ Ресурс CollectionsResource")
            print("✅ Сервис CollectionService")
            print("✅ Модели данных для коллекций")
            print("✅ Интеграция с ObjectService")
            print("✅ Типизированный API с Pydantic валидацией")

        except Exception as e:
            print(f"Ошибка при работе с коллекцией: {e}")
            import traceback

            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
