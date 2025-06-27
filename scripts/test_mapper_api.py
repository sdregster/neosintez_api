"""
Тестовый скрипт для демонстрации работы DynamicModelFactory.
"""

import asyncio
import traceback

from neosintez_api.client import NeosintezClient
from neosintez_api.config import NeosintezSettings
from neosintez_api.services import DynamicModelFactory
from neosintez_api.utils import generate_field_name


async def main():
    """
    Основной сценарий:
    1. Определяем пользовательские данные.
    2. Создаем и настраиваем фабрику.
    3. Используем фабрику для получения "чертежа" объекта.
    4. Выводим результат.
    """
    user_defined_data = {
        "Класс": "Стройка",
        "Имя объекта": "Тестовая стройка из публичного API",
        "МВЗ": "МВЗ_PUBLIC_777",
        "ID стройки Адепт": 54321,
    }

    # Инициализируем фабрику с возможными названиями ключевых полей
    factory = DynamicModelFactory(
        name_aliases=["Имя объекта", "Наименование", "Name"],
        class_name_aliases=["Класс", "Имя класса", "className"],
    )

    settings = NeosintezSettings()
    client = NeosintezClient(settings)

    try:
        # Используем фабрику для получения "чертежа" объекта
        blueprint = await factory.create_from_user_data(user_defined_data, client)

        print("\n--- Итог ---")
        print(f"Класс для создания в Неосинтез: '{blueprint.class_name}'")
        print(f"Имя объекта для создания: '{blueprint.object_name}'")
        print("\nГотовая Pydantic-модель с атрибутами:")
        print(blueprint.attributes_model.model_dump_json(by_alias=True, indent=4))

        print("\nПроверка доступа к полю 'МВЗ':")
        mvz_field_name = generate_field_name("МВЗ")
        print(
            f"  - blueprint.attributes_model.{mvz_field_name} = {getattr(blueprint.attributes_model, mvz_field_name)}"
        )

    except Exception as e:
        print(f"\nОшибка при выполнении: {e}")
        traceback.print_exc()
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
