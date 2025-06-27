# Задачи по разработке обёртки Neosintez API

## Выполненные задачи
- [x] Создание базовой структуры проекта
- [x] ЗАДАЧА 1: Рефакторинг и разбор монолита
- [x] ЗАДАЧА 2: Унификация атрибутов
- [x] **ЗАДАЧА 3: Сервис-слой CRUD** ✅
- [x] **ЗАДАЧА 4: Тестирование** ✅
- [x] **ЗАДАЧА 5: Базовый импорт из Excel** ⚠️
- [x] **ЗАДАЧА 8: Интеграция иерархического импорта из Excel** ✅

## Текущие задачи

### ЗАДАЧА 8: Интеграция иерархического импорта из Excel в основной модуль ✅
- **цель**: Перенести уже работающий PoC иерархического импорта из скриптов в основной API библиотеки
- **приоритет**: **MEDIUM** - улучшает функциональность
- **файлы для изменения**:
  - ✅ neosintez_api/hierarchical_excel_import.py - новый модуль (на основе PoC)
  - ✅ scripts/test_hierarchical_import.py - тестовый скрипт
  - ✅ neosintez_api/cli/commands/import_excel.py - обновление CLI
  - ✅ data/test_simple_hierarchy.xlsx - простой тестовый файл
  - ✅ data/test_complex_hierarchy.xlsx - сложный тестовый файл
- **статус**: ✅ **ЗАВЕРШЕНО** - Функциональность полностью интегрирована в основную библиотеку

**Концепция иерархического импорта (уже реализована в PoC)**:
- Автоматическое определение структуры Excel файла
- Поиск колонок по ключевым словам: "Уровень", "Класс", "Имя объекта" и атрибуты
- Чтение строк как словарей с автоматическим сопоставлением атрибутов в Неосинтезе
- Группировка объектов по уровням (1, 2, 3, ...)
- Пачечное создание объектов уровень за уровнем от первого до максимального
- Формирование Pydantic-моделей на основе найденных классов и атрибутов

**Примеры Excel файлов для тестирования:**

1. **Простой файл** (как на скриншоте):
   ```
   | Уровень | Класс   | Имя объекта           | МВЗ       | ID Primavera |
   |---------|---------|----------------------|-----------|--------------|
   | 1       | Папка   | Просто папка         |           |              |
   | 2       | Папка   | Просто вложенная папка|           |              |
   | 3       | Стройка | Тестовая стройка     | МВЗ3123456| 555          |
   ```

2. **Сложный файл** (боевой "data/template.xlsx"):
   - Многоуровневая иерархия (до 5-6 уровней)
   - Различные классы объектов на каждом уровне
   - Множественные атрибуты для каждого класса

**Шаги реализации:**

1. **📋 Рефакторинг PoC (scripts → neosintez_api)**:
   - Скопировать класс `NeosintezExcelImporter` из `scripts/import_ks2_xlsx_template.py`
   - Создать файл `neosintez_api/hierarchical_excel_import.py`
   - Адаптировать импорты и зависимости под структуру основной библиотеки
   - Убрать код для CLI и оставить только класс импортера

2. **🔧 Интеграция с ObjectService**:
   - Заменить прямые вызовы `self.client.objects.create()` на `self.object_service.create()`
   - Использовать `ObjectService.create_with_attributes()` для установки атрибутов
   - Добавить поддержку Pydantic-моделей через `ObjectService`
   - Пример: `await self.object_service.create(pydantic_model, parent_id)`

3. **📦 Создание основного API**:
   - Класс `HierarchicalExcelImporter` с методами:
     ```python
     async def analyze_structure(excel_path) -> ExcelStructure
     async def import_from_excel(excel_path, parent_id) -> ImportResult
     async def preview_import(excel_path) -> ImportPreview
     ```
   - Результат должен содержать статистику по уровням и созданным объектам

4. **⚙️ CLI интеграция**:
   - Добавить команду: `neosintez import hierarchy data.xlsx --parent <guid>`
   - Обновить `neosintez_api/cli/commands/import_excel.py`
   - Добавить опции: `--preview` (показать что будет создано), `--dry-run`

5. **✅ Критерии готовности**:
   - Импорт простого файла: создает Папку → Вложенную папку → Стройку с атрибутами
   - Импорт сложного файла: создает всю иерархию по уровням
   - CLI команда работает: `neosintez import hierarchy test.xlsx --parent <guid>`
   - Все тесты из `scripts/test_crud_service.py` проходят с новым импортером

**Конкретные файлы для создания/изменения:**
- ✅ `neosintez_api/hierarchical_excel_import.py` - основной класс
- ✅ `scripts/test_hierarchical_import.py` - тестовый скрипт
- ✅ `neosintez_api/cli/commands/import_excel.py` - добавить команду hierarchy
- ✅ `data/test_simple_hierarchy.xlsx` - простой тестовый файл
- ✅ `data/test_complex_hierarchy.xlsx` - сложный тестовый файл

**Ожидаемый результат:**
```python
# Простое использование через API
from neosintez_api.hierarchical_excel_import import HierarchicalExcelImporter

importer = HierarchicalExcelImporter(client)
result = await importer.import_from_excel("data.xlsx", parent_id="12345")
print(f"Создано объектов: {result.total_created}")
print(f"По уровням: {result.created_by_level}")
```

```bash
# Использование через CLI
neosintez import hierarchy data.xlsx --parent 12345 --preview
neosintez import hierarchy data.xlsx --parent 12345
```

### ЗАДАЧА 9: Средние улучшения (Medium Priority)
- **цель**: Повысить качество разработки и удобство использования
- **приоритет**: **MEDIUM** - улучшает dev experience
- **файлы для изменения**:
  - scripts/ - обновить примеры кода
  - neosintez_api/logging.py - оптимизация логирования
  - tests/ - добавить тесты float precision
- **шаги**:
  1. **📝 Синхронизация примеров**: Обновить scripts/ под актуальный API
  2. **🔇 Оптимизация логов**: INFO → DEBUG для подробностей, оставить только важное в INFO
  3. **✅ Дополнительные тесты**: Float precision, edge cases для маппинга

### ЗАДАЧА 10: Улучшения разработки (Low Priority)
- **цель**: Улучшить CI/CD, документацию и процессы разработки
- **приоритет**: **LOW** - nice to have
- **файлы для изменения**:
  - .github/workflows/ - расширить CI
  - docs/ - создать документацию
  - pyproject.toml - версионирование
- **шаги**:
  1. **🤖 Расширить CI**: mypy --strict, coverage badge, pre-commit hooks
  2. **📚 Документация**: ADR, PlantUML диаграммы, архитектурные решения
  3. **📦 Версионирование**: SemVer, bumpversion, CHANGELOG.md

### ЗАДАЧА 11: Будущие улучшения
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
