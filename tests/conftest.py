"""
Конфигурация pytest и общие фикстуры для тестов.
"""

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest
import pytest_asyncio
from _pytest.fixtures import FixtureRequest

from neosintez_api.config import NeosintezConfig
from neosintez_api.core.client import NeosintezClient
from neosintez_api.services.cache import TTLCache
from neosintez_api.services.factories.model_factory import DynamicModelFactory
from neosintez_api.services.object_service import ObjectService


@pytest.fixture(scope="session")
def event_loop(request: FixtureRequest):
    """Создает event loop для async тестов на всю сессию."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def real_settings() -> NeosintezConfig:
    """Настоящие настройки API для интеграционных тестов."""
    return NeosintezConfig()


@pytest_asyncio.fixture(scope="function")
async def real_client(real_settings: NeosintezConfig) -> NeosintezClient:
    """
    Настоящий клиент API для интеграционных тестов.
    Создается один раз на сессию и закрывается в конце.
    """
    client = NeosintezClient(real_settings)
    yield client
    await client.close()


@pytest.fixture(scope="session")
def dynamic_model_factory() -> DynamicModelFactory:
    """Экземпляр фабрики моделей."""
    return DynamicModelFactory(
        name_aliases=["Имя объекта", "Наименование", "Name"],
        class_name_aliases=["Класс", "Имя класса", "className"],
    )


@pytest.fixture(scope="session")
def object_service(real_client: NeosintezClient) -> ObjectService:
    """Экземпляр ObjectService с настоящим клиентом."""
    return ObjectService(real_client)


@pytest.fixture
def mock_settings():
    """Мок настроек API."""
    return NeosintezConfig(
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


@pytest.fixture(scope="session")
def test_class_id_with_children() -> str:
    """Возвращает ID класса, у которого точно есть дочерние объекты."""
    return "3aa54908-2283-ec11-911c-005056b6948b"


@pytest.fixture(scope="session")
def test_parent_id_with_children() -> str:
    """Возвращает ID родительского объекта, у которого точно есть дочерние объекты."""
    return "b8a4f94b-c782-ec11-911c-005056b6948b"
