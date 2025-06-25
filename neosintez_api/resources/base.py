"""
Базовый ресурсный класс для API Неосинтез.
"""

from typing import Any, Dict, List, Optional, Type, TypeVar, Union

T = TypeVar("T")


class BaseResource:
    """
    Базовый класс для всех ресурсных менеджеров API Неосинтез.

    Attributes:
        client: Родительский клиент API
    """

    def __init__(self, client):
        """
        Инициализирует ресурс с родительским клиентом.

        Args:
            client: Экземпляр NeosintezClient
        """

        self._client = client

    @property
    def client(self):
        """
        Возвращает родительский клиент API.

        Returns:
            NeosintezClient: Клиент API
        """
        return self._client

    async def _request(
        self,
        method: str,
        endpoint: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
        response_model: Optional[Type[T]] = None,
    ) -> Union[T, Dict[str, Any], List[Dict[str, Any]]]:
        """
        Выполняет API запрос через родительский клиент.

        Args:
            method: HTTP метод
            endpoint: URL эндпоинта
            params: URL параметры
            data: Данные для отправки
            headers: HTTP заголовки
            response_model: Модель для валидации ответа

        Returns:
            Union[T, Dict[str, Any], List[Dict[str, Any]]]: Ответ API
        """
        return await self.client._request(
            method=method,
            endpoint=endpoint,
            params=params,
            data=data,
            headers=headers,
            response_model=response_model,
        )
