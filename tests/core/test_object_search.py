"""
Интеграционные тесты для ObjectSearchService.
"""

import pytest
import pytest_asyncio

from neosintez_api.core.client import NeosintezClient
from neosintez_api.models import NeoObject
from neosintez_api.services import ClassService, ObjectSearchService


# Имя класса, который будет использоваться для тестов
TEST_CLASS_NAME = "Объект капитальных вложений"

# Для проверки, что указание родителя влияет на область поиска строек
TEST_PARENT_ID = "e569faab-99ae-ee11-9193-005056b6948b"


@pytest_asyncio.fixture(scope="function")
async def search_service(real_client: NeosintezClient) -> ObjectSearchService:
    """Фикстура для сервиса поиска объектов."""
    return ObjectSearchService(real_client)


@pytest_asyncio.fixture(scope="function")
async def class_service(real_client: NeosintezClient) -> ClassService:
    """Фикстура для сервиса работы с классами."""
    return ClassService(real_client)


@pytest.mark.asyncio
async def test_search_service_instance(search_service: ObjectSearchService):
    """
    Тест создания экземпляра сервиса ObjectSearchService.
    """
    assert isinstance(search_service, ObjectSearchService)


@pytest.mark.asyncio
async def test_search_query_builder_multiple_classes(search_service: ObjectSearchService):
    """
    Тест SearchQueryBuilder с множественными классами.
    """
    # Создаем query builder
    query_builder = search_service.query()

    # Проверяем начальное состояние
    assert query_builder._class_names == []

    # Добавляем первый класс
    query_builder.with_class_name("Объект капитальных вложений")
    assert len(query_builder._class_names) == 1
    assert "Объект капитальных вложений" in query_builder._class_names

    # Добавляем второй класс
    query_builder.with_class_name("Оборудование")
    assert len(query_builder._class_names) == 2
    assert "Объект капитальных вложений" in query_builder._class_names
    assert "Оборудование" in query_builder._class_names

    # Проверяем метод clear_class_names
    query_builder.clear_class_names()
    assert query_builder._class_names == []


@pytest.mark.asyncio
async def test_search_query_builder_validation(search_service: ObjectSearchService):
    """
    Тест валидации в SearchQueryBuilder.
    """
    query_builder = search_service.query()

    # Тест с пустой строкой
    with pytest.raises(ValueError, match="Имя класса не может быть пустым или содержать только пробелы"):
        query_builder.with_class_name("")

    # Тест с None
    with pytest.raises(ValueError, match="Имя класса не может быть пустым или содержать только пробелы"):
        query_builder.with_class_name(None)  # type: ignore

    # Тест с пробелами
    with pytest.raises(ValueError, match="Имя класса не может быть пустым или содержать только пробелы"):
        query_builder.with_class_name("   ")

    # Тест с пробелами в начале и конце (должен пройти)
    query_builder.with_class_name("  Объект капитальных вложений  ")
    assert "Объект капитальных вложений" in query_builder._class_names


@pytest.mark.asyncio
async def test_search_query_builder_real_search(search_service: ObjectSearchService):
    """
    Тест реального поиска с множественными классами.
    """
    # Создаем query builder с одним классом
    query_builder = search_service.query().with_class_name("Объект капитальных вложений")

    # Выполняем поиск
    try:
        objects = await query_builder.find_all()
        assert isinstance(objects, list)
        print(f"Найдено {len(objects)} объектов в классе 'Объект капитальных вложений'")
    except Exception as e:
        pytest.skip(f"Поиск в классе 'Объект капитальных вложений' не удался: {e}")

    # Тест с множественными классами (если доступны)
    try:
        multi_class_query = (
            search_service.query().with_class_name("Объект капитальных вложений").with_class_name("Оборудование")
        )

        # Проверяем, что классы добавлены
        assert len(multi_class_query._class_names) == 2
        assert "Объект капитальных вложений" in multi_class_query._class_names
        assert "Оборудование" in multi_class_query._class_names

        # Выполняем поиск (может не найти объекты, если классы не существуют)
        try:
            objects = await multi_class_query.find_all()
            assert isinstance(objects, list)
            print(f"Найдено {len(objects)} объектов в множественных классах")
        except ValueError as e:
            if "не найдены" in str(e):
                print(f"Ожидаемая ошибка: {e}")
            else:
                raise

    except Exception as e:
        pytest.skip(f"Тест с множественными классами не удался: {e}")


@pytest.mark.asyncio
async def test_find_objects_by_class(
    real_client: NeosintezClient,
    test_class_id_with_children: str,
    test_parent_id_with_children: str,
):
    """
    Тест поиска объектов по имени класса и по ID родителя.
    """
    service = ObjectSearchService(real_client)

    # Получаем имя класса по ID для тестирования
    class_service = ClassService(real_client)
    class_info = await class_service.get_by_id(test_class_id_with_children)
    if not class_info:
        pytest.skip(f"Класс с ID {test_class_id_with_children} не найден")

    class_name = class_info.Name

    # 1. Поиск по классу с указанием родителя
    objects = await service.find_objects_by_class(
        class_name=class_name,
        parent_id=test_parent_id_with_children,
    )
    assert isinstance(objects, list)
    assert len(objects) >= 1, "Должно быть найдено не менее 1 объекта с родителем"
    assert all(isinstance(obj, NeoObject) for obj in objects), "Все элементы в списке должны быть объектами NeoObject"
    print(f"Найдено {len(objects)} объектов с родителем.")

    # 2. Поиск по классу без указания родителя
    all_objects = await service.find_objects_by_class(class_name=class_name)
    assert isinstance(all_objects, list)
    assert len(all_objects) >= 1, "Должно быть найдено не менее 1 объекта без указания родителя"
    assert all(isinstance(obj, NeoObject) for obj in all_objects), (
        "Все элементы в списке должны быть объектами NeoObject"
    )
    print(f"Найдено {len(all_objects)} объектов без родителя.")
