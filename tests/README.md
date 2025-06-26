# Тесты neosintez_api

Комплексная система тестирования для обеспечения качества кода neosintez_api.

## Структура тестов

```
tests/
├── conftest.py              # Общие фикстуры и конфигурация
├── test_type_mapping.py     # Unit тесты маппинга типов данных
├── test_cache.py           # Unit тесты системы кэширования
├── test_validation.py      # Тесты валидации Pydantic моделей
├── test_integration.py     # Интеграционные тесты CRUD
└── README.md              # Эта документация
```

## Категории тестов

### Unit тесты
- **test_type_mapping.py**: Тестирование функций маппинга Python типов на WioAttributeType
- **test_cache.py**: Тестирование TTL кэша и декоратора @cached
- **test_validation.py**: Тестирование валидации Pydantic моделей

### Интеграционные тесты
- **test_integration.py**: Полные сценарии CRUD с мок-сервером

## Запуск тестов

### Локально
```bash
# Все тесты
python scripts/run_tests.py

# Только unit тесты
python scripts/run_tests.py --type unit

# Только интеграционные тесты
python scripts/run_tests.py --type integration

# С покрытием кода
python scripts/run_tests.py --type coverage --verbose
```

### Вручную через pytest
```bash
# Все тесты
pytest tests/

# Конкретный файл
pytest tests/test_type_mapping.py -v

# С покрытием
pytest tests/ --cov=neosintez_api --cov-report=html
```

## CI/CD

Тесты автоматически запускаются через GitHub Actions:
- При push в main/develop
- При создании Pull Request
- Matrix testing на Python 3.8, 3.9, 3.10, 3.11

## Покрытие кода

Цель: >80% покрытия кода тестами.

Отчеты создаются в:
- Консоль: `--cov-report=term-missing`
- HTML: `htmlcov/index.html`
- XML для CI: `coverage.xml`

## Фикстуры

Основные фикстуры в `conftest.py`:
- `mock_client`: Мок-клиент API
- `object_service`: Сервис для работы с объектами
- `ttl_cache`: TTL кэш для тестирования
- `sample_class_attributes`: Примеры атрибутов класса
- `sample_object_data`: Примеры данных объекта

## Маркеры

Доступные маркеры pytest:
- `@pytest.mark.asyncio`: Асинхронные тесты
- `@pytest.mark.integration`: Интеграционные тесты
- `@pytest.mark.unit`: Unit тесты
- `@pytest.mark.slow`: Медленные тесты

## Требования

Зависимости для тестирования указаны в `requirements-dev.txt`:
- pytest
- pytest-asyncio
- pytest-cov
- pytest-mock

## Конфигурация

Настройки pytest в `pytest.ini`:
- Минимальное покрытие: 80%
- Строгие маркеры и конфигурация
- Автоматический режим asyncio
- Фильтрация предупреждений 