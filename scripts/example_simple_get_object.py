"""
Простой пример получения объекта по GUID без создания моделей.

Демонстрирует два способа получения сырых данных объекта:
1. Через client.objects.get_by_id() - удобный способ через ресурс
2. Через client.get() - самый прямой способ через клиент
"""

import asyncio
import json

from neosintez_api.config import NeosintezConfig
from neosintez_api.core.client import NeosintezClient


async def main():
    """
    Основной сценарий: получение объекта по GUID без создания моделей.
    """
    # ID объекта для тестирования
    test_object_id = "4bc00b38-2dfc-11ef-91ff-005056b6c24b"

    print(f"--- Получение объекта по GUID: {test_object_id} ---\n")

    settings = NeosintezConfig()
    client = NeosintezClient(settings)

    try:
        # Авторизация
        await client.auth()
        print("✅ Авторизация успешна\n")

        # --- Способ 1: Через objects.get_by_id() ---
        print("▶️ Способ 1: Через client.objects.get_by_id()")
        object_data_1 = await client.objects.get_by_id(test_object_id)
        print(f"✅ Объект получен")
        print(f"   ID: {object_data_1.get('Id')}")
        print(f"   Название: {object_data_1.get('Name')}")
        print(f"   EntityId: {object_data_1.get('EntityId')}")
        print(f"   Количество атрибутов: {len(object_data_1.get('Attributes', []))}")
        print()

        # --- Способ 2: Через client.get() напрямую ---
        print("▶️ Способ 2: Через client.get() напрямую")
        object_data_2 = await client.get(f"api/objects/{test_object_id}")
        print(f"✅ Объект получен")
        print(f"   ID: {object_data_2.get('Id')}")
        print(f"   Название: {object_data_2.get('Name')}")
        print(f"   EntityId: {object_data_2.get('EntityId')}")
        print(f"   Количество атрибутов: {len(object_data_2.get('Attributes', []))}")
        print()

        # --- Вывод полных данных (опционально) ---
        print("--- Полные данные объекта (JSON) ---")
        print(json.dumps(object_data_1, indent=2, ensure_ascii=False))

    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback

        print("\n--- Полный Traceback ---")
        print(traceback.format_exc())

    finally:
        await client.close()
        print("\nСоединение закрыто.")


if __name__ == "__main__":
    asyncio.run(main())

