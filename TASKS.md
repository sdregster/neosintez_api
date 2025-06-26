# Задачи по разработке обёртки Neosintez API

## Выполненные задачи
- [x] Создание базовой структуры проекта
- [x] ЗАДАЧА 1: Рефакторинг и разбор монолита
- [x] ЗАДАЧА 2: Унификация атрибутов

## Текущие задачи

### ЗАДАЧА 3: Сервис-слой CRUD
- **цель**: Реализовать сервисный слой для работы с объектами через Pydantic-модели
- **статус**: Частично реализовано
- **файлы для изменения**:
  - neosintez_api/services/object_service.py
  - neosintez_api/services/__init__.py
  - scripts/test_crud_service.py
- **выполненные шаги**:
  1. [x] Создан базовый каркас сервисного слоя
  2. [x] Реализованы методы `create`, `read` для работы с моделями
  3. [x] Добавлен скрипт тестирования сервисного слоя
- **оставшиеся шаги**:
  1. [ ] **Этап 1: Критические исправления**
     - [ ] Исправить формирование `attr_by_name` в методе `create()` (services/object_service.py, строка ~90):
       ```python
       # Заменить это
       attr_by_name = {}
       for attr in class_attributes:
           if isinstance(attr, dict) and "Name" in attr:
               attr_by_name[attr["Name"]] = attr
           else:
               logger.warning(f"Пропущен атрибут с неверным форматом: {attr}")

       # На это
       attr_by_name = {
           (a["Name"] if isinstance(a, dict) else a.Name):
           (a if isinstance(a, dict) else a.model_dump())
           for a in class_attributes
       }
       ```
     - [ ] Разделить создание объекта и установку атрибутов (services/object_service.py, метод `create()`):
       ```python
       # Заменить встраивание атрибутов в запрос создания
       object_data = {
           "Name": object_name,
           "Entity": {"Id": class_id, "Name": class_name},
           # удалить "Attributes": {}
       }

       # На отдельные вызовы:
       object_id = await self.client.objects.create(parent_id, object_data)
       
       # Собрать список атрибутов для установки
       attributes_body = []
       for attr_name, value in model_data.items():
           # логика формирования атрибутов...
           if attr_name in attr_by_name:
               attributes_body.append(build_attribute_body(attr_by_name[attr_name], value))
       
       # Установить атрибуты отдельным вызовом, если они есть
       if attributes_body:
           await self.client.objects.set_attributes(object_id, attributes_body)
       ```
     - [ ] Исправить получение данных модели (services/object_service.py, метод `create()`):
       ```python
       # Заменить
       try:
           model_data = model.get_attribute_data()
       except AttributeError:
           model_data = model.model_dump(by_alias=True)

       # На просто
       model_data = model.model_dump(by_alias=True)
       ```
     - [ ] Обновить utils.py - `build_attribute_body()` для корректной обработки типов:
       ```python
       from datetime import datetime
       from enum import IntEnum

       class WioAttributeType(IntEnum):
           STRING = 1
           INTEGER = 2
           FLOAT = 3
           BOOLEAN = 4
           DATETIME = 5
           # добавить остальные типы из API

       def build_attribute_body(attr_meta, value):
           """
           Создает тело атрибута для API.
           
           Args:
               attr_meta: Метаданные атрибута
               value: Значение атрибута
           """
           attr_type = attr_meta["Type"] if isinstance(attr_meta, dict) else attr_meta.Type
           attr_id = attr_meta["Id"] if isinstance(attr_meta, dict) else attr_meta.Id
           
           # Преобразование типов
           if value is None:
               formatted_value = None
           elif attr_type == WioAttributeType.DATETIME and isinstance(value, datetime):
               formatted_value = value.isoformat()
           else:
               formatted_value = value
               
           return {
               "Id": attr_id,
               "Value": formatted_value
           }
       ```
     - [ ] Оптимизировать логирование:
       ```python
       # Заменить
       logger.info(f"Добавлен атрибут {field_name}={field_value}")
       
       # На
       if logger.isEnabledFor(logging.DEBUG):
           logger.debug(f"Добавлен атрибут {field_name}={field_value}")
           
       # Оставить INFO только для важных событий
       logger.info(f"Создание объекта '{object_name}' класса '{class_name}'")
       ```
  
  2. [ ] **Этап 2: Рефакторинг для устойчивого развития** 
     - [ ] Устранить дублирование клиентского кода:
       - Создать файл-заглушку `neosintez_api/client.py`:
         ```python
         import warnings
         warnings.warn("Импорт из neosintez_api.client устарел, используйте neosintez_api.core.client", DeprecationWarning)
         from .core.client import NeosintezClient
         # Реэкспорт других нужных классов
         ```
       - Обновить импорты во всех файлах, использующих старый клиент
     
     - [ ] Вынести логику маппинга атрибутов в отдельный класс `services/mappers/object_mapper.py`:
       ```python
       """
       Маппер для преобразования между Pydantic-моделями и API-представлением объектов.
       """
       
       import logging
       from typing import Dict, List, Any, Type, TypeVar
       from pydantic import BaseModel
       
       from ...utils import build_attribute_body

       T = TypeVar('T', bound=BaseModel)
       logger = logging.getLogger("neosintez_api.services.mappers.object_mapper")

       class ObjectMapper:
           @staticmethod
           async def model_to_attributes(model: BaseModel, attr_meta_by_name: Dict[str, Any]) -> List[Dict[str, Any]]:
               """
               Преобразует модель в список атрибутов для API.
               """
               attributes = []
               model_data = model.model_dump(by_alias=True)
               
               for attr_name, value in model_data.items():
                   if attr_name == "Name" or value is None:
                       continue
                   
                   if attr_name in attr_meta_by_name:
                       attributes.append(build_attribute_body(attr_meta_by_name[attr_name], value))
                   
               return attributes
           
           @staticmethod
           def api_to_model(model_class: Type[T], object_data: Dict[str, Any]) -> T:
               """
               Преобразует данные API в модель.
               """
               model_data = {"Name": object_data.get("Name", "")}
               
               # Добавление атрибутов в модель
               # ...код преобразования атрибутов
               
               return model_class(**model_data)
       ```
     
     - [ ] Реализовать метод `update_attrs()` с дифференциальным обновлением:
       ```python
       async def update_attrs(self, object_id: Union[str, UUID], model: T) -> bool:
           """
           Обновляет атрибуты объекта из модели Pydantic.
           Отправляет только изменившиеся атрибуты.
           
           Args:
               object_id: ID объекта
               model: Новые данные объекта
               
           Returns:
               bool: True если обновление успешно
           """
           # 1) Получить текущие данные объекта
           current_obj = await self.client.objects.get_by_id(object_id)
           
           # 2) Получить атрибуты класса объекта
           class_id = current_obj.EntityId
           class_attributes = await self.client.classes.get_attributes(class_id)
           
           # 3) Создать словарь атрибутов по имени
           attr_by_name = {
               (a["Name"] if isinstance(a, dict) else a.Name):
               (a if isinstance(a, dict) else a.model_dump())
               for a in class_attributes
           }
           
           # 4) Получить текущие значения атрибутов
           current_attrs = {}
           if hasattr(current_obj, "Attributes") and current_obj.Attributes:
               for attr_id, attr_data in current_obj.Attributes.items():
                   if isinstance(attr_data, dict) and "Name" in attr_data:
                       current_attrs[attr_data["Name"]] = attr_data["Value"]
           
           # 5) Сравнить с новыми значениями и собрать изменившиеся
           model_data = model.model_dump(by_alias=True)
           changed_attrs = []
           
           for attr_name, value in model_data.items():
               if attr_name == "Name" or value is None:
                   continue
                   
               if attr_name not in current_attrs or current_attrs[attr_name] != value:
                   if attr_name in attr_by_name:
                       changed_attrs.append(build_attribute_body(attr_by_name[attr_name], value))
           
           # 6) Обновить изменившиеся атрибуты
           if changed_attrs:
               logger.info(f"Обновление {len(changed_attrs)} атрибутов объекта {object_id}")
               return await self._set_attributes(object_id, changed_attrs)
           
           logger.info("Нет изменившихся атрибутов для обновления")
           return True
       ```
     
     - [ ] Доработать тестовый скрипт `scripts/test_crud_service.py`:
       ```python
       # После успешного создания объекта и проверки read, добавить:
       
       # 3. Обновление атрибутов с использованием update_attrs
       logger.info("Обновление атрибутов объекта через update_attrs")
       
       # Создаем обновленный объект с измененными атрибутами
       updated_construction = TestConstruction(
           Name=read_construction.name,  # имя не меняем
           МВЗ="МВЗ-Обновленный",  # меняем значение
           **{
               "Объект капитальных вложений": "Обновленное название через update_attrs",
               "ID стройки Адепт": str(int(read_construction.adept_id) + 1),  # инкрементируем
               "ID Primavera": read_construction.primavera_id,  # не меняем
               "Номер заявки": f"https://gandiva.irkutskoil.ru/Request/Edit/99999",  # меняем
           }
       )
       
       # Вызываем метод update_attrs
       update_result = await object_service.update_attrs(object_id, updated_construction)
       logger.info(f"Результат обновления: {update_result}")
       
       # Читаем объект снова для проверки обновления
       updated_read = await object_service.read(object_id, TestConstruction)
       
       # Проверяем, что обновились только измененные атрибуты
       logger.info("Проверка обновленных атрибутов:")
       logger.info(f"МВЗ: {updated_read.mvz} (ожидалось 'МВЗ-Обновленный')")
       logger.info(f"Объект кап.вложений: {getattr(updated_read, 'capex_object', None)} (ожидалось 'Обновленное название через update_attrs')")
       logger.info(f"ID Адепт: {updated_read.adept_id} (ожидалось {int(read_construction.adept_id) + 1})")
       logger.info(f"ID Primavera: {updated_read.primavera_id} (должен остаться {read_construction.primavera_id})")
       logger.info(f"Номер заявки: {updated_read.request_number} (ожидалось '...99999')")
       ```

  3. [ ] Протестировать полный цикл create → read → update_attrs с обновленным кодом
     - Запустить скрипт `python scripts/test_crud_service.py`
     - Убедиться, что все этапы выполняются без ошибок
     - Проверить в логах правильные значения атрибутов на каждом этапе

### ЗАДАЧА 4: Тестирование
- **цель**: Обеспечить качество кода через автоматизированные тесты
- **файлы для изменения**:
  - tests/test_type_mapping.py
  - tests/test_cache.py
  - tests/test_validation.py
  - tests/test_integration.py
  - .github/workflows/pytest.yml
- **шаги**:
  1. Создать unit-тесты для маппинга типов, кэша TTL и валидации
  2. Настроить мок-сервер для интеграционных тестов
  3. Создать сценарий тестирования create → read → update_attrs
  4. Настроить GitHub Actions для автоматического запуска тестов

### ЗАДАЧА 5: Импорт из Excel
- **цель**: Создать механизм импорта данных из Excel в Неосинтез через Pydantic-модели
- **файлы для изменения**:
  - neosintez_api/excel_import.py
  - scripts/test_excel_import.py
  - requirements.txt
- **шаги**:
  1. Добавить зависимости pandas и openpyxl
  2. Реализовать чтение Excel и преобразование в Pydantic-модели
  3. Обеспечить параллельное создание объектов с ограничением нагрузки
  4. Добавить формирование отчета о результатах импорта

## Будущие задачи

### ЗАДАЧА 6: CLI и пользовательские удобства
- **цель**: Создать удобный интерфейс командной строки для работы с API
- **файлы для изменения**:
  - neosintez_api/__main__.py
  - scripts/cli_examples.py
  - README.md
- **шаги**:
  1. Реализовать CLI-интерфейс для основных операций
  2. Добавить режим dry-run для проверки без внесения изменений
  3. Интегрировать прогресс-бар для отслеживания выполнения
  4. Обновить документацию с примерами использования

### ЗАДАЧА 7: Будущие улучшения
- **цель**: Расширить функциональность библиотеки и упростить архитектуру
- **файлы для изменения**:
  - neosintez_api/plugins/fastapi_plugin.py
  - neosintez_api/services/bulk_operations.py
  - neosintez_api/core/retry.py
  - neosintez_api/services/model_generator.py
- **шаги**:
  1. Реорганизовать структуру проекта для четкого разделения ответственности
     ```
     neosintez_api/
     ├── core/             # Ядро SDK
     │   ├── client.py     # Единый клиент API
     │   ├── resources/    # Ресурсы для работы с API
     │   └── models/       # API модели
     ├── models/           # Доменные модели
     ├── services/         # Сервисный слой
     │   ├── object_service.py
     │   └── mappers/      # Маппинги моделей
     └── utils/            # Общие утилиты
     ```
  2. Создать FastAPI-плагин для генерации CRUD
  3. Добавить поддержку массового обновления объектов
  4. Реализовать механизм retry с exponential backoff
  5. Разработать функционал авто-генерации Pydantic-моделей
