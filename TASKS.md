# Задачи по улучшению usability Neosintez API

## Цель проекта
Создать **интуитивно понятный высокоуровневый API** поверх существующей архитектуры, который превращает сложные многоэтапные операции в простые однострочные вызовы и при этом сохраняет всю функциональность и гибкость текущего решения.

---

## Выполненные задачи
*(пусто — начинаем новый этап)*

---

## Текущие задачи

### ЗАДАЧА 1: Рефакторинг — Очистка и консолидация
- **цель**: Устранить дублирование кода и упростить структуру проекта.
- **приоритет**: **HIGHEST**.
- **файлы для изменения**:
  - `neosintez_api/cli/commands/class_.py` (удалить)
  - `neosintez_api/cli/commands/object.py` (удалить)
  - `neosintez_api/exceptions.py` (удалить после слияния)
  - `neosintez_api/core/exceptions.py` (консолидировать сюда)
  - `neosintez_api/resources/` → `neosintez_api/core/resources/`
  - `neosintez_api/model_utils.py` (удалить после слияния)
  - `neosintez_api/utils.py` (консолидировать сюда)
- **шаги**:
  1. Упростить CLI — оставить только `import_excel`.
  2. Объединить исключения в `core/exceptions.py`.
  3. Переместить ресурсы и удалить старую папку.
  4. Перенести полезные функции из `model_utils.py` в `utils.py`.
- **критерии успеха**:
  - Нет дублирующихся модулей.
  - Лишние команды CLI удалены.
  - Структура стала более плоской.

---

### ЗАДАЧА 2: Рефакторинг — Выделение DTO‑слоя
- **цель**: Явно отделить слой DTO, переместив ключевую модель `ObjectDTO` в отдельный модуль.
- **приоритет**: **HIGH**.
- **файлы для изменения**:
  - `neosintez_api/dto/models.py` (создать)
  - `neosintez_api/services/factories/dto_factory.py` (создать, вместо `model_factory.py`)
  - Обновить все импорты `ObjectDTO`.
- **шаги**:
  1. Создать папку `neosintez_api/dto/`.
  2. Определить базовые Pydantic‑DTO: `ObjectDTO`, `AttributeDTO` и др.
  3. Переместить логику сборки в `ObjectDTOFactory`:
     ```python
     class ObjectDTOFactory:
         def from_dict(self, raw: dict) -> ObjectDTO:
             model_cls = self._resolve_model_class(raw.get("Класс") or raw.get("class") )
             return model_cls(**raw)

         async def from_api(self, id: UUID) -> ObjectDTO:
             data = await self._load_data(id)
             return self.from_dict(data)
     ```
  4. Удалить `ObjectBlueprint`, заменить на `ObjectDTO`.
- **критерии успеха**:
  - Все модели данных находятся в `dto`‑слое.
  - Фабрики используют новые сигнатуры без `class_name`.
  - Код компилируется и тесты проходят.

---

### ЗАДАЧА 3: Создание фасада `NeosintezManager` (Build + CRUD)
- **цель**: Предоставить высокоуровневый интерфейс для сборки DTO и выполнения CRUD‑операций.
- **приоритет**: **HIGH**.
- **файлы для изменения/добавления**:
  - `neosintez_api/manager.py`
  - `neosintez_api/__init__.py` (экспорт `NeosintezManager`)
  - `scripts/example_manager_build_and_crud.py`
- **ключевые методы**:
  ```python
  async with NeosintezManager() as m:
      dto = await m.build(data=user_dict)
      created = await m.create(dto, parent_id=...)
      dto = await m.get(created.id)
      await m.update(dto)
      await m.delete(dto.id)
  ```

---

### ЗАДАЧА 4: Автоматическая конвертация типов
- **цель**: Поддержать все `WioAttributeType` с автоматическим маппингом на Python‑типы.
- **приоритет**: **HIGH**.
- **файлы**:
  - `neosintez_api/core/type_converter.py` (новый)
  - `neosintez_api/utils.py` (расширить)
  - `scripts/example_all_types.py`.

---

### ЗАДАЧА 5: Упрощение примеров и документации
- **цель**: Переписать все `example_*` скрипты, используя `NeosintezManager`.
- **приоритет**: **MEDIUM**.

---

## Будущие шаги

1. **Ввести `pyproject.toml`** для унификации зависимостей, `mypy`, `ruff`.
2. **Создать слой `infra/`** для API‑клиента, изолируя его от core.
3. **Повысить покрытие тестами** (mock API через `respx`).

---

## Принципы реализации

1. **Обратная совместимость** — low‑level API остаётся.
2. **Принцип минимального удивления** — одна точка входа.
3. **Автоматизация** — метаданные, типы, алиасы.
4. **Простота** — «один способ сделать».
5. **Производительность** — кэш, batch‑операции.

---
