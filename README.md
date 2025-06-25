# API-клиент для Neosintez

Этот пакет предоставляет асинхронный Python-клиент для взаимодействия с API Neosintez.

## Установка

```shell
pip install -e .
```

## Настройка

Для работы API-клиента необходимо настроить параметры подключения. Это можно сделать через переменные окружения или через файл `.env`.

Пример файла `.env`:

```
NEOSINTEZ_BASE_URL=https://neosintez.example.com/
NEOSINTEZ_USERNAME=your_username
NEOSINTEZ_PASSWORD=your_password
NEOSINTEZ_CLIENT_ID=your_client_id
NEOSINTEZ_CLIENT_SECRET=your_client_secret
```

**Важно**: URL должен заканчиваться на слеш (`/`).

## Использование

### Базовый пример

```python
import asyncio
from dotenv import load_dotenv
from neosintez_api.client import NeosintezClient
from neosintez_api.config import load_settings

# Загрузка настроек из .env
load_dotenv()
settings = load_settings()

async def main():
    async with NeosintezClient(settings) as client:
        # Аутентификация
        token = await client.auth()
        print(f"Получен токен: {token[:10]}...")
        
        # Получение списка классов
        classes = await client.get_classes()
        print(f"Получено {len(classes)} классов")
        
        # Получение списка атрибутов
        attributes = await client.get_attributes()
        print(f"Получено {len(attributes)} атрибутов")

if __name__ == "__main__":
    asyncio.run(main())
```

### Поиск объектов

```python
from neosintez_api.models import SearchRequest, SearchFilter
from uuid import UUID

async def search_example(client, class_id):
    # Создаем запрос на поиск объектов указанного класса
    request = SearchRequest(Filters=[SearchFilter(Type=5, Value=str(class_id))])
    
    # Запрос с пагинацией
    response = await client.search(request, take=10, skip=0)
    print(f"Найдено всего: {response.Total} объектов")
    
    # Поиск всех объектов с автоматической пагинацией
    all_objects = await client.search_all(request)
    print(f"Найдено всего: {len(all_objects)} объектов")
```

### Получение пути к объекту

```python
async def get_path_example(client, item_id):
    path = await client.get_item_path(item_id)
    
    # Вывод пути в формате дерева
    path_str = " -> ".join([ancestor.Name for ancestor in path.AncestorsOrSelf])
    print(f"Путь: {path_str}")
```

### Обновление атрибутов объекта

```python
async def update_attributes_example(client, item_id):
    attributes = {
        "Имя_атрибута": "Значение",
        "Другой_атрибут": 123
    }
    
    success = await client.update_attributes(item_id, attributes)
    if success:
        print("Атрибуты успешно обновлены")
```

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