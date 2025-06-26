
# Пошаговый план развития обёртки `neosintez_api`

> **Версия:** 0.2 (26 июня 2025)  
> **Автор:** ChatGPT

---

## 1. Цель проекта

Спрятать низкоуровневое REST‑API Неосинтеза за «pythonic» интерфейсом, чтобы разработчик оперировал **Pydantic‑моделями**, а не JSON‑структурами, и мог:

1. Создавать объекты (`create`).
2. Читать/конвертировать объекты в модели (`read`).
3. Массово импортировать данные из Excel.
4. Легко расширять слой для других источников (CSV, БД, Web).

---

## 2. Текущая точка

| Компонент | Состояние | Проблемы |
|-----------|-----------|----------|
| PoC‑скрипт `create → read` | ✅ Работает | Логика «размазана» по одному файлу |
| REST‑клиент `NeosintezClient` | ⚠ Минимум методов | Использует приватный `._request`, слабая типизация |
| Кэш `ENTITY_CACHE` | ✅ В памяти | Нет TTL / обновления |
| Swagger (`swagger.json`) | ✅ Полный | Методы не сгенерированы |
| Тесты | ❌ | Отсутствуют |
| Массовый импорт из Excel | ❌ | Не реализован |

---

## 3. Целевая архитектура (3 слоя)

```
Pydantic Model  →  Service Layer  →  Core SDK  →  REST API (Neosintez)
```

| Слой | Папка | Основные классы |
|------|-------|-----------------|
| **Domain** | `models/` | `Pump(BaseModel)`, `Folder(BaseModel)` |
| **Service** | `neosintez_api/services/` | `ObjectService`, `MetadataCache` |
| **Core SDK** | `neosintez_api/core/` | `NeosintezClient`, DTO‑модели, Enums |

---

## 4. Детальный план работ

### Шаг 1. Рефакторинг и разбор монолита (🕐 ~1 день)

| Действие | Файл/папка | Результат |
|----------|------------|-----------|
| 1.1 Создать пакет `neosintez_api/core` | `__init__.py`, `client.py`, `enums.py`, `exceptions.py` | Выделяем тонкий SDK |
| 1.2 Сгенерировать dataclasses из swagger (или `datamodel-codegen`) | `core/generated/` | Типизированные DTO |
| 1.3 Переместить логику кеша в `services/cache.py` | — | Единая точка доступа |

### Шаг 2. Унификация атрибутов (🕐 ~0.5 дня)

1. Таблица маппинга **Python‑тип → WioAttributeType** в `enums.py`.
2. Функция `build_attribute_body(meta, value)`:
   * валидация соответствия типов;
   * конвертация дат (`datetime → "YYYY‑MM‑DDTHH:MM:SSZ"`);
   * поддержка `Field(alias=…)`.

### Шаг 3. Сервис‑слой CRUD (🕐 ~1.5 дня)

| Метод | Подробности |
|-------|-------------|
| `create(model, parent_id)` | 1 REST вызов – POST `/objects` + 1 PUT `/objects/{id}/attributes` |
| `update_attrs(obj_id, model)` | Сравниваем текущие и новые значения, шлём diff |
| `read(model_cls, obj_id)` | Достаём, мапим атрибуты ↔ поля |

### Шаг 4. Тестирование (🕐 ~1 день)

* **Unit**: маппинг типов, кэш TTL, валидация.
* **Integration**: мок‑сервер respx/WireMock; сценарий *create → read* должен вернуть идентичную модель.
* GitHub Actions workflow `pytest -q`.

### Шаг 5. Импорт из Excel (🕐 ~1.5 дня)

1. `pip install pandas openpyxl`.
2. `excel_import.py`:
   ```python
   for row in df.itertuples():
       model = SomeModel(**row._asdict())
       await ObjectService.create(model, parent_id)
   ```
3. Применяем `asyncio.Semaphore(5)` для параллельности.
4. Пишем отчёт `.xlsx` (успех/ошибка, созданный `Id`).

### Шаг 6. CLI и удобства (🕐 ~0.5 дня)

* `python -m neosintez_api.import_excel file.xlsx --model SomeModel --parent <GUID>`.
* Флаг `--dry-run` — только валидация без API‑запросов.
* `tqdm` progress‑bar.

### Шаг 7. Будущие улучшения (опционально)

* FastAPI‑плагин генерации CRUD.
* Bulk‑update существующих объектов.
* Retry + back‑off на 429/503.
* Авто‑генерация Pydantic‑класса по Id сущности.

---

## 5. Дорожная карта (Gantt‑набросок)

| Неделя | 1 | 2 | 3 |
|-------|---|---|---|
| 🌱 Рефакторинг ядра | ███ | | |
| ⚙️ Атрибуты + Сервис |  | ███ | |
| ✅ Тесты |  | ██ | |
| 📥 Excel Import |  |  | ███ |
| 🚀 CLI & релиз 0.1 |  |  | ▒▒ |

---

## 6. Требуемые deliverables

* `neosintez_api/core/*.py` – SDK.
* `neosintez_api/services/*.py` – Cache & ObjectService.
* `examples/quick_start.py` – минимальный пример.
* `tests/` – полный coverage > 80 %.
* `excel_import.py` + `README.md`.

---

## 7. Полезные ссылки

* Swagger UI локально: `python -m aiohttp_swagger3 swagger.json`.
* Datamodel‑codegen: <https://github.com/koxudaxi/datamodel-code-generator>
* respx mock server: <https://github.com/lundberg/respx>

---

### Удачной работы! 🚀
