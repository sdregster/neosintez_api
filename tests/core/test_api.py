"""Тестирование API Неосинтеза"""

import pytest

from neosintez_api.core.client import NeosintezClient


@pytest.mark.asyncio
async def test_client_authentication():
    """
    Тестирует успешную аутентификацию клиента.
    """
    client = NeosintezClient()

    async with client:
        token = await client.auth()
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0
        assert client.token == token
