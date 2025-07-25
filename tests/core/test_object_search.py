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
async def test_find_objects_by_class(
    real_client: NeosintezClient,
    test_class_id_with_children: str,
    test_parent_id_with_children: str,
):
    """
    Тест поиска объектов по ID класса и по ID родителя.
    """
    service = ObjectSearchService(real_client)
    # 1. Поиск по классу с указанием родителя
    objects = await service.find_objects_by_class(
        class_id=test_class_id_with_children,
        parent_id=test_parent_id_with_children,
    )
    assert isinstance(objects, list)
    assert len(objects) >= 41, "Должно быть найдено не менее 41 объекта с родителем"
    assert all(isinstance(obj, NeoObject) for obj in objects), "Все элементы в списке должны быть объектами NeoObject"
    print(f"Найдено {len(objects)} объектов с родителем.")

    # 2. Поиск по классу без указания родителя
    all_objects = await service.find_objects_by_class(class_id=test_class_id_with_children)
    assert isinstance(all_objects, list)
    assert len(all_objects) >= 860, "Должно быть найдено не менее 860 объектов без указания родителя"
    assert all(isinstance(obj, NeoObject) for obj in all_objects), (
        "Все элементы в списке должны быть объектами NeoObject"
    )
    print(f"Найдено {len(all_objects)} объектов без родителя.")
