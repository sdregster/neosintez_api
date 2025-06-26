"""
Конфигурация pytest и общие фикстуры для тестов.
"""

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from neosintez_api.config import NeosintezSettings
from neosintez_api.core.client import NeosintezClient
from neosintez_api.services.cache import TTLCache
from neosintez_api.services.object_service import ObjectService


@pytest.fixture
def event_loop():
    """Создает event loop для async тестов."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_settings():
    """Мок настроек API."""
    return NeosintezSettings(
        base_url="https://test.neosintez.ru",
        username="test_user",
        password="test_password",
        verify_ssl=False,
    )


@pytest.fixture
def mock_client(mock_settings):
    """Мок клиента API."""
    client = Mock(spec=NeosintezClient)
    client.settings = mock_settings

    # Мокируем ресурсы
    client.classes = AsyncMock()
    client.objects = AsyncMock()

    return client


@pytest.fixture
def object_service(mock_client):
    """Экземпляр ObjectService с мок-клиентом."""
    return ObjectService(mock_client)


@pytest.fixture
def ttl_cache():
    """Экземпляр TTL кэша для тестирования."""
    return TTLCache(default_ttl=60, max_size=100)


@pytest.fixture
def sample_class_attributes():
    """Пример атрибутов класса для тестирования."""
    return [
        {
            "Id": "626370d8-ad8f-ec11-911d-005056b6948b",
            "Name": "МВЗ",
            "Type": 2,  # String
            "Required": True,
            "Multiple": False,
        },
        {
            "Id": "f980619f-b547-ee11-917e-005056b6948b",
            "Name": "ID стройки Адепт",
            "Type": 1,  # Integer
            "Required": False,
            "Multiple": False,
        },
    ]


@pytest.fixture
def sample_object_data():
    """Пример данных объекта для тестирования."""
    return {
        "Id": "12345678-1234-1234-1234-123456789abc",
        "Name": "Тестовый объект",
        "EntityId": "3aa54908-2283-ec11-911c-005056b6948b",
        "Attributes": {
            "626370d8-ad8f-ec11-911d-005056b6948b": {"Value": "МВЗ434177", "Type": 2},
            "f980619f-b547-ee11-917e-005056b6948b": {"Value": 876, "Type": 1},
        },
    }
