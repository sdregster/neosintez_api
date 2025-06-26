# Neosintez API

Библиотека для работы с API Неосинтез через Python.

## Установка

```bash
pip install neosintez-api
```

## Настройка

Для работы с API необходимо создать файл `.env` в корне проекта со следующими переменными:

```
NEOSINTEZ_BASE_URL=https://your-neosintez-instance.com/
NEOSINTEZ_USERNAME=your_username
NEOSINTEZ_PASSWORD=your_password
NEOSINTEZ_CLIENT_ID=your_client_id
NEOSINTEZ_CLIENT_SECRET=your_client_secret
NEOSINTEZ_TEST_FOLDER_ID=your_test_folder_id  # Опционально, для тестов
```

## Использование

### Базовое использование

```python
import asyncio
from neosintez_api import NeosintezClient, NeosintezSettings

async def main():
    # Загрузка настроек из .env
    settings = NeosintezSettings()
    
    # Создание клиента
    client = NeosintezClient(settings)
    
    # Получение классов
    classes = await client.classes.get_all()
    print(f"Получено {len(classes)} классов")
    
    # Получение объектов
    objects = await client.objects.get_children("parent-id")
    print(f"Получено {len(objects)} объектов")

if __name__ == "__main__":
    asyncio.run(main())
```

### Работа с моделями Pydantic

Библиотека предоставляет удобные инструменты для работы с объектами через модели Pydantic.

#### Декоратор `neosintez_model`

Декоратор `neosintez_model` добавляет в модель Pydantic метаданные и методы для работы с API Неосинтез:

```python
from pydantic import BaseModel, Field
from neosintez_api import neosintez_model

@neosintez_model(class_name="Папка МВЗ")
class FolderModel(BaseModel):
    """Модель для папки МВЗ"""
    Name: str
    mvz: Optional[str] = Field(None, alias="МВЗ")
    adept_id: Optional[str] = Field(None, alias="ID стройки Адепт")
```

Декоратор добавляет следующие методы:

- `get_object_name()` - получение имени объекта из модели
- `get_attribute_data()` - получение данных модели с алиасами в качестве ключей
- `get_field_to_attribute_mapping()` - получение маппинга полей модели на атрибуты Неосинтеза

#### Создание моделей из атрибутов класса

Функция `create_model_from_class_attributes` позволяет создавать модели Pydantic на основе атрибутов класса из Неосинтеза:

```python
from neosintez_api import create_model_from_class_attributes

# Получение атрибутов класса
classes = await client.classes.get_classes_by_name("Папка МВЗ")
class_id = classes[0]["id"]
class_attributes = await client.classes.get_attributes(class_id)

# Создание модели из атрибутов класса
DynamicModel = create_model_from_class_attributes(
    "Папка МВЗ", 
    class_attributes
)

# Создание экземпляра модели
instance = DynamicModel(
    Name="Тестовая папка",
    мвз="12345"  # Поля создаются с именами в нижнем регистре
)
```

### Сервисный слой для работы с объектами

Класс `ObjectService` предоставляет удобный интерфейс для работы с объектами через модели Pydantic:

```python
from neosintez_api import ObjectService

# Создание сервиса объектов
object_service = ObjectService(client)

# Создание объекта из модели
folder = FolderModel(
    Name="Тестовая папка МВЗ",
    mvz="12345",
    adept_id="ADEPT-001"
)
folder_id = await object_service.create(folder, parent_id)

# Чтение объекта в модель
read_folder = await object_service.read(folder_id, FolderModel)

# Обновление атрибутов
read_folder.mvz = "54321"
updated = await object_service.update_attrs(folder_id, read_folder)
```

## Примеры

Примеры использования библиотеки находятся в папке `scripts/`.

## Типичные проблемы и их решения

### 1. Ошибка "AssertionError: assert not url.absolute"

Эта ошибка возникает, если в методах клиента используются абсолютные URL вместе с `base_url` при создании сессии. В таком случае проверьте:

- URL в `.env` должен заканчиваться на слеш (`/`)
- В методах, использующих сессию, должны использоваться относительные пути (без базового URL)

### 2. Ошибки аутентификации

Проверьте корректность учетных данных:
- Имя пользователя
- Пароль
- Client ID
- Client Secret

### 3. ValidationError при загрузке настроек

Убедитесь, что все необходимые параметры указаны в `.env` файле или переменных окружения. 