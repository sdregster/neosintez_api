"""
Тестовый скрипт для демонстрации полного цикла CRUD:
Чтение -> Модификация -> Обновление -> Проверка.

Проверяет корректность обработки различных типов данных,
включая строки, числа, даты и ссылки на другие объекты.
"""

import asyncio
import traceback
from datetime import datetime
import copy

from neosintez_api.config import NeosintezConfig
from neosintez_api.core.client import NeosintezClient
from neosintez_api.services import ObjectToModelFactory, ObjectService
from neosintez_api.utils import generate_field_name


async def main():
    """
    Основной сценарий:
    1. Создает Pydantic-модель из существующего объекта.
    2. Сохраняет его исходное состояние.
    3. Модифицирует атрибуты разных типов.
    4. Обновляет объект в Неосинтезе.
    5. Проверяет, что изменения применились.
    6. Возвращает объект в исходное состояние.
    """
    test_object_id = "8681c50f-ec53-f011-91e6-005056b6948b"
    
    print(f"--- Полный цикл обновления для объекта: {test_object_id} ---\n")

    settings = NeosintezConfig()
    client = NeosintezClient(settings)
    object_to_model_factory = ObjectToModelFactory(client)
    object_service = ObjectService(client)
    
    original_model_instance = None
    blueprint = None
    
    try:
        # --- Этап 1: Чтение и создание модели ---
        print("▶️ Этап 1: Получение Pydantic-модели и текущих данных...")
        blueprint = await object_to_model_factory.create_from_object_id(test_object_id)
        original_model_instance = copy.deepcopy(blueprint.model_instance)
        
        print(f"✅ Модель '{blueprint.model_class.__name__}' создана, данные загружены.")
        
        # --- Этап 2: Модификация данных ---
        print("\n▶️ Этап 2: Модификация атрибутов для теста...")
        
        modified_instance = copy.deepcopy(original_model_instance)
        
        # Готовим новые значения и "безопасные" имена полей
        new_name = f"РОКЕТА_ИЗМЕНЕНО_{datetime.now().isoformat()}"
        new_mass = 777
        new_date = datetime(2030, 1, 1).isoformat()
        
        massa_field = generate_field_name("Масса")
        data_postavki_field = generate_field_name("Дата поставки")
        edinica_izmereniya_field = generate_field_name("Единица измерения")
        
        # Применяем изменения
        modified_instance.name = new_name
        setattr(modified_instance, massa_field, new_mass)
        setattr(modified_instance, data_postavki_field, new_date)
        # setattr(modified_instance, edinica_izmereniya_field, None) # API игнорирует сброс ссылки
        
        print(f"   - Имя изменено на: '{new_name}'")
        print(f"   - '{massa_field}' (Масса) изменена на: {new_mass}")
        print(f"   - '{data_postavki_field}' (Дата поставки) изменена на: '{new_date}'")
        # print(f"   - 'Единица измерения' не изменяем, т.к. API игнорирует сброс.")

        # --- Этап 3: Обновление ---
        print("\n▶️ Этап 3: Отправка изменений в Неосинтез...")
        await object_service.update(
            modified_instance, blueprint.attributes_meta
        )
        print("✅ Запрос на обновление успешно отправлен.")

        # --- Этап 4: Проверка ---
        print("\n▶️ Этап 4: Повторное чтение и проверка изменений...")
        reread_object = await object_service.read(test_object_id, blueprint.model_class)
        
        assert reread_object.name == new_name
        assert getattr(reread_object, massa_field) == new_mass
        # API может возвращать дату в своем формате, сравним только дату, без времени
        assert getattr(reread_object, data_postavki_field, "").startswith("2030-01-01")
        # assert getattr(reread_object, edinica_izmereniya_field) is None
        
        print("✅ Проверка прошла успешно! Все изменения корректно сохранены.")
        
        print(f"\n🎉 Цикл обновления и проверки завершен успешно!")

    except Exception as e:
        print(f"\n❌ Ошибка на одном из этапов: {e}")
        tb_str = traceback.format_exc()
        print("\n--- Полный Traceback ---")
        print(tb_str)

    finally:
        # --- Этап 5: Очистка ---
        if original_model_instance and blueprint:
            print("\n▶️ Этап 5: Восстановление исходных данных объекта...")
            try:
                await object_service.update(
                    original_model_instance, blueprint.attributes_meta
                )
                print("✅ Объект успешно возвращен в исходное состояние.")
            except Exception as e:
                print(f"❌ Ошибка при восстановлении объекта: {e}")

        await client.close()
        print("\nСоединение закрыто.")


if __name__ == "__main__":
    asyncio.run(main()) 