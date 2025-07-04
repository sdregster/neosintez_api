import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from neosintez_api.models import Attribute
from neosintez_api.services.resolvers import AttributeResolver


@pytest.fixture
def mock_client():
    """Фикстура для создания мока NeosintezClient."""
    client = MagicMock()
    client.objects = AsyncMock()
    return client


@pytest.mark.asyncio
async def test_resolve_link_attribute_as_object_success(mock_client):
    """
    Тестирует успешное разрешение ссылочного атрибута в объект.
    """
    # 1. Настройка моков
    resolver = AttributeResolver(mock_client)
    attr_id = uuid.uuid4()
    linked_object_id = uuid.uuid4()
    linked_object_name = "Да"

    mock_attr_meta = Attribute(
        Id=attr_id,
        Name="Тестовая ссылка",
        Type=8,
        Constraints=[
            {"Type": 1, "EntityId": uuid.uuid4()},  # Class constraint
            {"Type": 3, "ObjectRootId": uuid.uuid4()},  # Root object constraint
        ],
    )

    # Мокаем результат поиска объекта по имени, возвращаем объект с атрибутами
    mock_search_result = MagicMock()
    mock_search_result.Id = linked_object_id
    mock_search_result.Name = linked_object_name
    resolver.search_service.find_objects_by_class = AsyncMock(return_value=[mock_search_result])

    # 2. Вызов тестируемого метода
    result = await resolver.resolve_link_attribute_as_object(attr_meta=mock_attr_meta, attr_value="Да")

    # 3. Проверка результата
    expected = {"Id": str(linked_object_id), "Name": linked_object_name}
    assert result == expected
    resolver.search_service.find_objects_by_class.assert_awaited_once()


@pytest.mark.asyncio
async def test_resolve_link_attribute_not_found(mock_client):
    """
    Тестирует случай, когда ссылочный объект не найден.
    Должно быть вызвано исключение ValueError.
    """
    # 1. Настройка моков
    resolver = AttributeResolver(mock_client)
    mock_attr_meta = Attribute(
        Id=uuid.uuid4(), Name="Тестовая ссылка", Type=8, Constraints=[{"Type": 1, "EntityId": uuid.uuid4()}]
    )
    resolver.search_service.find_objects_by_class = AsyncMock(return_value=[])  # Возвращаем пустой список

    # 2. Вызов и проверка исключения
    with pytest.raises(ValueError) as excinfo:
        await resolver.resolve_link_attribute_as_object(attr_meta=mock_attr_meta, attr_value="Несуществующее значение")

    assert "Не удалось найти связанный объект" in str(excinfo.value)
