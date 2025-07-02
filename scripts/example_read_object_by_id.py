"""
Тестовый скрипт для демонстрации и отладки создания Pydantic-моделей
из существующих объектов в Неосинтезе по их ID.
"""

import asyncio
import traceback

from neosintez_api.config import NeosintezConfig
from neosintez_api.core.client import NeosintezClient
from neosintez_api.services import ObjectService, ObjectToModelFactory


async def main():
    """
    Основной сценарий:
    1. Поэтапное получение данных об объекте и его классе.
    2. Создание Pydantic-модели из объекта с помощью ObjectToModelFactory.
    3. Вывод детальной информации для отладки.
    4. Демонстрация совместимости с ObjectService.
    """
    # ID объекта для тестирования
    test_object_id = "8681c50f-ec53-f011-91e6-005056b6948b"

    print(f"--- Отладка получения объекта по ID: {test_object_id} ---\n")

    settings = NeosintezConfig()
    client = NeosintezClient(settings)

    try:
        # --- Этап 1: Создание Pydantic-модели ---
        # Мы вызываем фабрику, которая инкапсулирует всю логику
        # Если на каком-то из внутренних шагов (получение объекта, класса, атрибутов)
        # произойдет ошибка, фабрика должна выбросить исключение.
        print("▶️ Этап 1: Создание Pydantic-модели с помощью ObjectToModelFactory...")

        object_to_model_factory = ObjectToModelFactory(client)
        blueprint = await object_to_model_factory.create_from_object_id(test_object_id)

        print(f"✅ Успешно создана Pydantic-модель: '{blueprint.model_class.__name__}'")

        print("\n--- Итоговая модель ---")
        print(blueprint.model_instance.model_dump_json(by_alias=True, indent=2))

        # --- Этап 2: Демонстрация совместимости ---
        print("\n▶️ Этап 2: Проверка совместимости с ObjectService...")
        object_service = ObjectService(client)

        # Читаем объект, используя нашу динамически созданную модель
        reread_object = await object_service.read(test_object_id, blueprint.model_class)
        assert reread_object.name == blueprint.model_instance.name

        print("✅ Модель совместима, объект успешно перечитан с использованием новой модели.")
        print("\n🎉 Отладка и тестирование завершены успешно!")

    except Exception as e:
        print("\n❌ Ошибка при выполнении. Анализ проблемы:")
        # Используем traceback для получения детальной информации о месте ошибки
        tb_str = traceback.format_exc()

        if "Класс с ID" in str(e) and "не найден" in str(e):
            print("   - Проблема: Не удалось найти информацию о КЛАССЕ объекта.")
            print(f"   - Детали: {e}")
            print("   - Возможные причины:")
            print("     1. API-endpoint для получения класса по ID вернул 404 Not Found.")
            print("     2. У текущего пользователя нет прав на просмотр этого класса.")
        elif "Ошибка получения объекта" in str(e):
            print("   - Проблема: Не удалось получить данные самого ОБЪЕКТА.")
            print(f"   - Детали: {e}")
            print("   - Возможные причины:")
            print(f"     1. Объект с ID {test_object_id} не существует.")
            print("     2. У пользователя нет прав на просмотр объекта.")
        else:
            print("   - Проблема: Произошла непредвиденная ошибка.")
            print(f"   - Детали: {e}")

        print("\n--- Полный Traceback ---")
        print(tb_str)

    finally:
        await client.close()
        print("\nСоединение закрыто.")


if __name__ == "__main__":
    asyncio.run(main())
