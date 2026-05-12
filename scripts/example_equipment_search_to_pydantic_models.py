#!/usr/bin/env python3
"""
Пример поиска оборудования на портале operation и преобразования результатов
в массив Pydantic моделей.

Демонстрирует:
1. Подключение к порталу operation
2. Поиск объектов класса "Оборудование основное_" с фильтрами
3. Преобразование всех найденных объектов в типизированные Pydantic модели
4. Вывод детальной информации о результатах
"""

import asyncio
import traceback

from neosintez_api.config import NeosintezConfig
from neosintez_api.core.client import NeosintezClient
from neosintez_api.services import ObjectToModelFactory


async def main():
    """
    Основная функция для поиска оборудования и преобразования в Pydantic модели.
    
    Выполняет поиск объектов класса "Оборудование основное_" у указанного родителя
    с фильтром по атрибуту "Категория НЕОСИНТЕЗ" = "Оборудование",
    затем преобразует все найденные объекты в типизированные Pydantic модели.
    """
    # ID родительского объекта для поиска
    parent_id = "9611227f-e285-11ee-91e0-005056b6c24b"
    
    print("--- Поиск оборудования и преобразование в Pydantic модели ---")
    print(f"Родительский объект: {parent_id}")
    print("Класс: Оборудование основное_")
    print("Фильтр: Категория НЕОСИНТЕЗ = 'Оборудование'")
    print("-" * 80)
    
    # Создаем конфигурацию
    config = NeosintezConfig()
    
    # Заменяем base_url для работы с operation.irkutskoil.ru
    if "construction.irkutskoil.ru" in str(config.base_url):
        config.base_url = str(config.base_url).replace("construction", "operation")
        print(f"Используем URL: {config.base_url}")
    
    async with NeosintezClient(config) as client:
        try:
            # --- Этап 1: Поиск объектов ---
            print("▶️ Этап 1: Поиск объектов оборудования...")
            
            # Выполняем поиск с помощью fluent API
            equipment_objects = (
                await client.search.query()
                .with_class_name("Оборудование основное_")
                .with_parent_id(parent_id)
                .with_attribute_name("Категория НЕОСИНТЕЗ", "Оборудование")
                .find_all()
            )
            
            print(f"✅ Найдено объектов: {len(equipment_objects)}")
            
            if not equipment_objects:
                print("⚠️  Объекты не найдены. Проверьте параметры поиска.")
                return
            
            # --- Этап 2: Преобразование в Pydantic модели ---
            print("\n▶️ Этап 2: Преобразование объектов в Pydantic модели...")
            
            # Создаем фабрику для преобразования объектов в модели
            object_to_model_factory = ObjectToModelFactory(client)
            
            # Список для хранения созданных моделей
            pydantic_models = []
            
            # Преобразуем каждый найденный объект в Pydantic модель
            for i, obj in enumerate(equipment_objects, 1):
                print(f"  Обрабатываем объект {i}/{len(equipment_objects)}: {obj.Name}")
                
                # Создаем Pydantic модель из объекта
                blueprint = await object_to_model_factory.create_from_object_id(str(obj.Id))
                
                # Добавляем в список результатов
                pydantic_models.append(blueprint)
                
                print(f"    ✅ Создана модель: {blueprint.model_class.__name__}")
            
            print(f"✅ Успешно преобразовано моделей: {len(pydantic_models)}")
            
            # --- Этап 3: Вывод результатов ---
            print("\n▶️ Этап 3: Вывод результатов...")
            print("=" * 80)
            
            for i, blueprint in enumerate(pydantic_models, 1):
                print(f"\n--- Модель {i}/{len(pydantic_models)} ---")
                print(f"Класс модели: {blueprint.model_class.__name__}")
                print(f"Имя объекта: {blueprint.model_instance.name}")
                print(f"ID объекта: {blueprint.model_instance.id}")
                print(f"ID класса: {blueprint.model_instance.class_id}")
                
                # Выводим JSON представление модели
                print("\nJSON представление:")
                print(blueprint.model_instance.model_dump_json(by_alias=True, indent=2))
                
                if i < len(pydantic_models):
                    print("-" * 40)
            
            print("\n" + "=" * 80)
            print("🎉 Обработка завершена успешно!")
            print("📊 Статистика:")
            print(f"   - Найдено объектов: {len(equipment_objects)}")
            print(f"   - Преобразовано моделей: {len(pydantic_models)}")
            print("   - Успешность: 100%")
            
        except Exception as e:
            print(f"\n❌ Ошибка при выполнении: {e}")
            print("\n--- Полный Traceback ---")
            traceback.print_exc()
            
            # Пробрасываем исключение для "громкого падения"
            raise


if __name__ == "__main__":
    asyncio.run(main())
