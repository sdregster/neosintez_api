# Neosintez API Python Client 

🚀 **Современная Python обёртка для работы с API Неосинтез** с поддержкой динамических моделей, умного поиска и автоматизированного импорта данных.

## ✨ Ключевые возможности

### 🔥 **Динамические Pydantic модели**
- Автоматическое создание типизированных моделей на лету из пользовательских данных
- Валидация данных и автоматический маппинг атрибутов
- Поддержка любых классов Неосинтеза без предварительного описания

### 🔍 **Fluent Search API** 
- Удобный текучий (fluent) интерфейс для поиска объектов
- Поиск по именам классов и атрибутов (без знания UUID)
- Поиск по точным значениям атрибутов с различными операторами
- Автоматическое разрешение имен в идентификаторы

### 📊 **Иерархический импорт из Excel**
- Импорт сложных иерархических структур одной командой
- Автоматическое создание родительских объектов при необходимости  
- Валидация данных перед импортом с детальными отчетами об ошибках
- Поддержка различных типов атрибутов и связей между объектами

### 🛠️ **Полный CRUD функционал**
- Создание, чтение, обновление и удаление объектов
- Работа с атрибутами любых типов
- Управление иерархией объектов

## 🎯 Примеры использования

### **Fluent Search API** - поиск объектов
```python
# 🔍 Поиск объекта по имени и классу
found_object = await client.search.query() \
    .with_name("Газопровод с метанолопроводом от узла задвижек до скв. № 24") \
    .with_class_name("Объект капитальных вложений") \
    .find_one()

# 🔍 Поиск всех объектов в классе с фильтром по родителю  
all_objects = await client.search.query() \
    .with_class_name("Объект капитальных вложений") \
    .with_parent_id("46303b37-eefd-ee11-91a4-005056b6948b") \
    .find_all()

# 🔍 Поиск по значению атрибута (умный поиск по имени атрибута!)
equipment = await client.search.query() \
    .with_class_name("Объект капитальных вложений") \
    .with_attribute_name("МВЗ", "МВЗ015343") \
    .find_all()
```

### **Динамические модели** - CRUD без предварительного описания схем
```python
# 🏗️ Создание объекта из простого словаря
user_data = {
    "Класс": "Стройка",
    "Имя объекта": "Тестовая стройка из кода",
    "МВЗ": "МВЗ_PUBLIC_API",
    "ID стройки Адепт": 12345,
}

# ✨ Автоматическое создание Pydantic модели и blueprint
blueprint = await factory.create_from_user_data(user_data, client)

# 🚀 Полный CRUD цикл с типизацией и валидацией
created_object = await object_service.create(
    model=blueprint.model_instance,
    class_id=blueprint.class_id,
    parent_id=settings.test_folder_id,
)

# 📖 Чтение с автоматической десериализацией в Pydantic модель
read_object = await object_service.read(created_object.id, blueprint.model_class)

# ✏️ Обновление через типизированные поля
read_object.name = "Обновленная стройка"
await object_service.update(read_object, attributes_meta=blueprint.attributes_meta)
```

### **Иерархический импорт** - массовая загрузка из Excel
```python
# 📊 Импорт сложной иерархии одной командой
importer = ExcelImporter(client)
await importer.import_hierarchical_data(
    file_path="data/complex_hierarchy.xlsx",
    class_mapping={
        "Объекты капвложений": "Объект капитальных вложений",
        "Оборудование": "Оборудование",
    },
    root_parent_id="46303b37-eefd-ee11-91a4-005056b6948b"
)
```

## 📁 Полные примеры

| Пример | Описание | Файл |
|--------|----------|------|
| 🔍 **Умный поиск** | Fluent Search API с поиском по атрибутам | [`scripts/example_fluent_search.py`](scripts/example_fluent_search.py) |
| 🏗️ **Динамические модели** | Создание Pydantic моделей на лету | [`scripts/example_dynamic_model_crud.py`](scripts/example_dynamic_model_crud.py) |
| 📊 **Иерархический импорт** | Массовая загрузка из Excel с иерархией | [`scripts/example_hierarchical_import.py`](scripts/example_hierarchical_import.py) |
| 🎨 **Декларативные модели** | Работа с предопределенными моделями | [`scripts/example_declarative_model_crud.py`](scripts/example_declarative_model_crud.py) |
| 📖 **Чтение объектов** | Получение объектов по ID | [`scripts/example_read_object_by_id.py`](scripts/example_read_object_by_id.py) |

## 🚀 Быстрый старт

**Рекомендуемый подход для новых проектов:**

1. **Опишите данные** в обычном словаре Python
2. **Используйте `DynamicModelFactory`** для автоматического создания Pydantic-моделей
3. **Используйте `ObjectService`** для выполнения CRUD операций
4. **Используйте Fluent Search API** для поиска объектов

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
    async with NeosintezClient(settings) as client:
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

        # 2. Создаем "чертеж" (blueprint) и Pydantic-модель "на лету"
        blueprint = await factory.create_from_user_data(user_data, client)

        # 3. CREATE: Создаем объект
        created_object = await object_service.create(
            model=blueprint.model_instance,
            class_id=blueprint.class_id,
            parent_id=settings.test_folder_id,
        )
        print(f"✅ Объект создан: {created_object.id}")

        # 4. READ: Читаем созданный объект
        read_object = await object_service.read(created_object.id, blueprint.model_class)
        print(f"📖 Объект прочитан: {read_object.name}")

        # 5. UPDATE: Обновляем атрибуты
        read_object.name = "Обновленная стройка"
        await object_service.update(read_object, attributes_meta=blueprint.attributes_meta)
        print("✏️ Объект обновлен")

        # 6. DELETE: Удаляем объект
        await object_service.delete(created_object.id)
        print("🗑️ Объект удален")

if __name__ == "__main__":
    asyncio.run(main())
```

## 🏗️ Архитектура

Библиотека построена по модульному принципу:

- **`core/`** - Базовая функциональность API клиента
- **`services/`** - Высокоуровневые сервисы для работы с объектами
- **`models.py`** - Pydantic модели для валидации данных  
- **`cli/`** - Консольные команды для импорта
- **`scripts/`** - Примеры использования

Этот подход избавляет от необходимости заранее определять Pydantic-модели и вручную сопоставлять атрибуты, делая работу с API максимально простой и эффективной! 🎯
