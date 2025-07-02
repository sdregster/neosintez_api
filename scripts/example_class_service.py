"""
Демонстрация работы нового ClassService.

Скрипт показывает, как использовать сервисный слой для получения информации
о классах и их атрибутах.
"""

import asyncio
import logging
import traceback

from neosintez_api import NeosintezClient
from neosintez_api.config import NeosintezConfig
from neosintez_api.services import ClassService


# Включаем логирование, чтобы видеть информационные сообщения от сервиса
logging.basicConfig(level=logging.INFO)
logging.getLogger("neosintez_api").setLevel(logging.DEBUG)


async def main():
    """
    Основной сценарий:
    1. Найти класс по имени.
    2. Получить его детальную информацию по ID.
    3. Получить и вывести все его атрибуты.
    """
    settings = NeosintezConfig()
    client = NeosintezClient(settings)
    class_service = ClassService(client)

    # Имя класса для поиска
    class_name_to_find = "Стройка"

    try:
        # 1. Находим класс по имени
        print(f"--- 1. Поиск класса по имени: '{class_name_to_find}' ---")
        found_classes = await class_service.find_by_name(class_name_to_find)
        if not found_classes:
            raise ValueError(f"Класс, содержащий в имени '{class_name_to_find}', не найден.")

        # Берем первый найденный класс
        target_class_info = found_classes[0]
        class_id = str(target_class_info.Id)
        print(f"✅ Класс найден: '{target_class_info.Name}' (ID: {class_id})")

        # 2. Получаем полную информацию о классе по ID
        print(f"\n--- 2. Получение полной информации о классе ID: {class_id} ---")
        detailed_class = await class_service.get_by_id(class_id)
        if not detailed_class:
            raise ValueError(f"Не удалось получить детальную информацию для класса {class_id}")

        print(f"✅ Информация получена: {detailed_class.model_dump_json(indent=2)}")

        # 3. Получаем атрибуты класса
        print(f"\n--- 3. Получение атрибутов для класса '{detailed_class.Name}' ---")
        attributes = await class_service.get_attributes(class_id)
        if not attributes:
            print("ℹ️ У данного класса нет собственных атрибутов.")
        else:
            print(f"✅ Найдено {len(attributes)} атрибутов:")
            for attr in attributes:
                print(f"  - Имя: {attr.Name}, Тип: {attr.Type}, ID: {attr.Id}")

    except Exception as e:
        print(f"\n❌ Произошла ошибка: {e}")
        traceback.print_exc()

    finally:
        await client.close()
        print("\nСоединение с клиентом закрыто.")


if __name__ == "__main__":
    asyncio.run(main())
