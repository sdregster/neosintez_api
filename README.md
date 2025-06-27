Сервисный слой предоставляет максимально простой и абстрактный интерфейс для работы с объектами в Неосинтез, инкапсулируя всю сложность API.

**Рекомендуемый подход:**
1.  **Опишите данные** в обычном словаре Python.
2.  **Используйте `DynamicModelFactory`** для автоматического определения класса, создания Pydantic-модели и подготовки "чертежа" (`blueprint`) для работы с объектом.
3.  **Используйте `ObjectService`** с полученным `blueprint` для выполнения полного цикла операций: создания (`create`), чтения (`read`), обновления (`update`) и удаления (`delete`).

Этот подход избавляет от необходимости заранее определять Pydantic-модели и вручную сопоставлять атрибуты.

#### Пример полного CRUD-цикла

```python
import asyncio
from neosintez_api import (
    NeosintezConfig, 
    NeosintezClient, 
    DynamicModelFactory, 
    ObjectService
)

async def main():
    # 0. Инициализация
    settings = NeosintezConfig()
    client = NeosintezClient(settings)
    factory = DynamicModelFactory(
        name_aliases=["Имя объекта", "Наименование"],
        class_name_aliases=["Класс", "Имя класса"],
    )
    object_service = ObjectService(client)
    
    # 1. Определяем пользовательские данные
    user_data = {
        "Класс": "Стройка",
        "Имя объекта": "Тестовая стройка из кода",
        "МВЗ": "МВЗ_PUBLIC_API",
        "ID стройки Адепт": 12345,
    }

    created_object_id = None
    try:
        # 2. Создаем "чертеж" (blueprint) и Pydantic-модель "на лету"
        blueprint = await factory.create_from_user_data(user_data, client)

        # 3. CREATE: Создаем объект
        created_object = await object_service.create(
            model=blueprint.model_instance,
            class_id=blueprint.class_id,
            parent_id=settings.test_folder_id,
        )
        created_object_id = created_object.id
        print(f"Объект создан: {created_object_id}")

        # 4. READ: Читаем созданный объект
        read_object = await object_service.read(created_object_id, blueprint.model_class)
        assert read_object.name == "Тестовая стройка из кода"
        print("Объект успешно прочитан.")

        # 5. UPDATE: Обновляем атрибуты
        read_object.name = "Обновленная стройка"
        read_object.mvz = "МВЗ_NEW"
        await object_service.update(read_object, attributes_meta=blueprint.attributes_meta)
        print("Объект обновлен.")

        # 6. Проверяем обновление
        reread_object = await object_service.read(created_object_id, blueprint.model_class)
        assert reread_object.name == "Обновленная стройка"
        assert reread_object.parent_id == settings.test_folder_id # parent_id не менялся
        print("Обновление проверено.")

    finally:
        # 7. DELETE: Удаляем объект
        if created_object_id:
            await object_service.delete(created_object_id)
            print(f"Объект {created_object_id} удален.")
        
        await client.close()

if __name__ == "__main__":
    asyncio.run(main())
```

## Примеры

Более детальные примеры использования библиотеки, включая `example_dynamic_factory.py` и `example_crud_cycle.py`, находятся в папке `scripts/`.
