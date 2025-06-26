"""
Клиент для работы с API Неосинтез.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Type, TypeVar, Union, Tuple

import aiohttp
from pydantic import BaseModel

from .exceptions import (
    NeosintezAPIError,
    NeosintezAuthError,
    NeosintezConnectionError,
    NeosintezTimeoutError,
)
from ..config import NeosintezSettings
from ..utils import parse_error_response, retry

# Настройка логгера
logger = logging.getLogger("neosintez_api")
logger.setLevel(logging.DEBUG)  # Устанавливаем уровень логирования на DEBUG

T = TypeVar("T")


class NeosintezClient:
    """
    Асинхронный клиент для работы с API Неосинтез.

    Attributes:
        settings: Настройки подключения к API
        token: Токен доступа
    """

    def __init__(self, settings: NeosintezSettings):
        """
        Инициализация клиента API Неосинтез.

        Args:
            settings: Настройки подключения к API
        """
        self.settings = settings
        self.token: Optional[str] = None
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self) -> "NeosintezClient":
        """
        Асинхронный контекстный менеджер для инициализации сессии.

        Returns:
            NeosintezClient: Экземпляр клиента
        """
        if not self._session:
            await self._create_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """
        Асинхронный контекстный менеджер для закрытия сессии.
        """
        await self.close()

    async def _create_session(self) -> None:
        """
        Создает новую HTTP-сессию.
        """
        timeout = aiohttp.ClientTimeout(total=self.settings.timeout)
        self._session = aiohttp.ClientSession(
            base_url=str(self.settings.base_url),
            timeout=timeout,
            connector=aiohttp.TCPConnector(
                limit=self.settings.max_connections,
                ttl_dns_cache=300,
            ),
        )

    async def close(self) -> None:
        """
        Закрывает HTTP-сессию.
        """
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    @property
    def session(self) -> aiohttp.ClientSession:
        """
        Получает или создает HTTP-сессию.

        Returns:
            aiohttp.ClientSession: Текущая HTTP-сессия

        Raises:
            RuntimeError: Если клиент не инициализирован через контекстный менеджер
        """
        if self._session is None or self._session.closed:
            raise RuntimeError(
                "HTTP сессия не инициализирована. "
                "Используйте 'async with' контекст или вызовите await client.auth()"
            )
        return self._session

    @retry(attempts=3, delay=1)
    async def auth(self) -> str:
        """
        Выполняет аутентификацию и получает токен доступа.

        Returns:
            str: Токен доступа

        Raises:
            NeosintezAuthError: При ошибке аутентификации
            NeosintezConnectionError: При ошибке соединения
        """
        if not self._session or self._session.closed:
            await self._create_session()

        # При использовании self.session нужно использовать относительный URL,
        # так как base_url уже задан при создании сессии
        url = "connect/token"
        logger.debug(f"URL для авторизации: {self.settings.base_url}{url}")

        # Используем только необходимые заголовки
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        # Формируем данные как строку, а не как словарь
        data = f"grant_type=password&username={self.settings.username}&password={self.settings.password}&client_id={self.settings.client_id}&client_secret={self.settings.client_secret}"

        # Логируем данные для отладки (без пароля)
        debug_data = f"grant_type=password&username={self.settings.username}&password=---&client_id={self.settings.client_id}&client_secret=---"
        logger.debug(f"Данные для авторизации: {debug_data}")

        try:
            # Используем self.session напрямую
            logger.debug(
                f"Отправка запроса на авторизацию на URL: {self.settings.base_url}{url}"
            )
            async with self.session.post(url, data=data, headers=headers) as response:
                logger.debug(f"Получен ответ с кодом: {response.status}")
                logger.debug(f"Заголовки ответа: {response.headers}")

                if response.status == 200:
                    # Получаем текст ответа и парсим его как JSON
                    response_text = await response.text()
                    logger.debug(f"Текст ответа: {response_text[:100]}...")

                    try:
                        token_data = json.loads(response_text)
                        self.token = token_data["access_token"]
                        logger.debug("Аутентификация успешна")
                        return self.token
                    except (json.JSONDecodeError, KeyError) as e:
                        logger.error(f"Ошибка при парсинге ответа: {str(e)}")
                        logger.error(f"Текст ответа: {response_text[:200]}...")
                        raise NeosintezAuthError(
                            f"Ошибка при парсинге ответа: {str(e)}"
                        )
                else:
                    response_text = await response.text()
                    logger.error(
                        f"Ошибка аутентификации: {response.status} - {response_text}"
                    )
                    raise NeosintezAuthError(
                        f"Не удалось авторизоваться. {response.status} - {response_text}"
                    )
        except aiohttp.ClientConnectionError as e:
            logger.error(f"Ошибка соединения при аутентификации: {str(e)}")
            raise NeosintezConnectionError(f"Ошибка соединения: {str(e)}")
        except aiohttp.ClientResponseError as e:
            logger.error(f"Ошибка ответа при аутентификации: {str(e)}")
            raise NeosintezAuthError(f"Ошибка аутентификации: {str(e)}")
        except aiohttp.ClientError as e:
            logger.error(f"Ошибка клиента при аутентификации: {str(e)}")
            raise NeosintezAuthError(f"Ошибка аутентификации: {str(e)}")
        except Exception as e:
            logger.error(f"Неожиданная ошибка при аутентификации: {str(e)}")
            logger.error(f"Тип ошибки: {type(e)}")
            import traceback

            logger.error(f"Трассировка: {traceback.format_exc()}")
            raise

    async def _get_headers(self) -> Dict[str, str]:
        """
        Формирует заголовки для запросов к API.

        Returns:
            Dict[str, str]: Заголовки запроса

        Raises:
            NeosintezAuthError: Если токен не получен
        """
        if not self.token:
            await self.auth()

        return {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json-patch+json",
        }

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
        Выполняет HTTP-запрос к API Неосинтез.

        Args:
            method: HTTP-метод (GET, POST, PUT, DELETE)
            endpoint: Конечная точка API
            params: URL-параметры запроса
            data: Данные запроса
            headers: Дополнительные заголовки
            response_model: Pydantic-модель для валидации ответа

        Returns:
            Union[T, Dict[str, Any], List[Dict[str, Any]]]: Ответ API

        Raises:
            NeosintezAPIError: В случае ошибки API
            NeosintezConnectionError: При ошибке соединения
            NeosintezTimeoutError: При таймауте запроса
        """
        if not self._session or self._session.closed:
            await self.auth()

        request_headers = await self._get_headers()
        if headers:
            request_headers.update(headers)

        # Если данные - это экземпляр Pydantic модели, то преобразуем его в словарь
        if isinstance(data, BaseModel):
            data = data.model_dump(exclude_none=True)

        # Преобразуем данные в JSON, если они не None
        json_data = json.dumps(data) if data is not None else None

        logger.debug(f"Запрос {method} {self.settings.base_url}{endpoint}")
        if params:
            logger.debug(f"Параметры запроса: {params}")
        if data:
            logger.debug(
                f"Данные запроса: {json_data[:200]}..." if json_data else "None"
            )

        try:
            async with self.session.request(
                method=method,
                url=endpoint,
                params=params,
                data=json_data,
                headers=request_headers,
                ssl=self.settings.verify_ssl,
            ) as response:
                logger.debug(f"Получен ответ с кодом: {response.status}")

                # Обрабатываем успешный ответ
                if 200 <= response.status < 300:
                    try:
                        # Пытаемся получить JSON из ответа
                        response_json = await response.json()

                        # Если указана модель ответа, то валидируем JSON
                        if response_model:
                            if isinstance(response_json, list):
                                return [
                                    response_model.model_validate(item)
                                    for item in response_json
                                ]
                            else:
                                return response_model.model_validate(response_json)

                        # Иначе возвращаем JSON как есть
                        return response_json
                    except json.JSONDecodeError:
                        # Если ответ не JSON, то возвращаем текст ответа
                        text_response = await response.text()
                        logger.debug(
                            f"Ответ не является JSON: {text_response[:200]}..."
                        )
                        return text_response

                # Обрабатываем ошибочный ответ
                error_info = await parse_error_response(response)
                raise NeosintezAPIError(
                    status_code=error_info["status_code"],
                    message=error_info["message"],
                    response_data=error_info["data"],
                )

        except aiohttp.ClientConnectionError as e:
            logger.error(f"Ошибка соединения: {str(e)}")
            raise NeosintezConnectionError(f"Ошибка соединения: {str(e)}")
        except aiohttp.ClientResponseError as e:
            logger.error(f"Ошибка ответа: {str(e)}")
            raise NeosintezAPIError(
                status_code=e.status, message=str(e), response_data=None
            )
        except aiohttp.ClientError as e:
            logger.error(f"Ошибка клиента: {str(e)}")
            raise NeosintezAPIError(status_code=500, message=str(e), response_data=None)
        except asyncio.TimeoutError as e:
            logger.error(f"Таймаут запроса: {str(e)}")
            raise NeosintezTimeoutError(f"Таймаут запроса: {str(e)}")
        except Exception as e:
            logger.error(f"Неожиданная ошибка: {str(e)}")
            import traceback

            logger.error(f"Трассировка: {traceback.format_exc()}")
            raise

    @retry(attempts=2, delay=1)
    async def _request_raw(
        self,
        method: str,
        endpoint: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Tuple[int, Any]:
        """
        Выполняет HTTP-запрос к API Неосинтез и возвращает статус и тело ответа без обработки.

        Args:
            method: HTTP-метод (GET, POST, PUT, DELETE)
            endpoint: Конечная точка API
            params: URL-параметры запроса
            data: Данные запроса
            headers: Дополнительные заголовки

        Returns:
            Tuple[int, Any]: Статус ответа и тело ответа

        Raises:
            NeosintezConnectionError: При ошибке соединения
            NeosintezTimeoutError: При таймауте запроса
        """
        if not self._session or self._session.closed:
            await self.auth()

        request_headers = await self._get_headers()
        if headers:
            request_headers.update(headers)

        # Если данные - это экземпляр Pydantic модели, то преобразуем его в словарь
        if isinstance(data, BaseModel):
            data = data.model_dump(exclude_none=True)

        # Преобразуем данные в JSON, если они не None
        json_data = json.dumps(data) if data is not None else None

        try:
            async with self.session.request(
                method=method,
                url=endpoint,
                params=params,
                data=json_data,
                headers=request_headers,
                ssl=self.settings.verify_ssl,
            ) as response:
                status = response.status

                try:
                    content = await response.json()
                except json.JSONDecodeError:
                    content = await response.text()

                return status, content

        except aiohttp.ClientConnectionError as e:
            logger.error(f"Ошибка соединения: {str(e)}")
            raise NeosintezConnectionError(f"Ошибка соединения: {str(e)}")
        except asyncio.TimeoutError as e:
            logger.error(f"Таймаут запроса: {str(e)}")
            raise NeosintezTimeoutError(f"Таймаут запроса: {str(e)}")
        except Exception as e:
            logger.error(f"Неожиданная ошибка: {str(e)}")
            import traceback

            logger.error(f"Трассировка: {traceback.format_exc()}")
            raise

    async def get(
        self,
        endpoint: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        response_model: Optional[Type[T]] = None,
    ) -> Union[T, Dict[str, Any], List[Dict[str, Any]]]:
        """
        Выполняет GET-запрос к API Неосинтез.

        Args:
            endpoint: Конечная точка API
            params: URL-параметры запроса
            headers: Дополнительные заголовки
            response_model: Pydantic-модель для валидации ответа

        Returns:
            Union[T, Dict[str, Any], List[Dict[str, Any]]]: Ответ API
        """
        return await self._request(
            method="GET",
            endpoint=endpoint,
            params=params,
            headers=headers,
            response_model=response_model,
        )

    async def post(
        self,
        endpoint: str,
        *,
        data: Optional[Any] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        response_model: Optional[Type[T]] = None,
    ) -> Union[T, Dict[str, Any], List[Dict[str, Any]]]:
        """
        Выполняет POST-запрос к API Неосинтез.

        Args:
            endpoint: Конечная точка API
            data: Данные запроса
            params: URL-параметры запроса
            headers: Дополнительные заголовки
            response_model: Pydantic-модель для валидации ответа

        Returns:
            Union[T, Dict[str, Any], List[Dict[str, Any]]]: Ответ API
        """
        return await self._request(
            method="POST",
            endpoint=endpoint,
            data=data,
            params=params,
            headers=headers,
            response_model=response_model,
        )

    async def put(
        self,
        endpoint: str,
        *,
        data: Optional[Any] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        response_model: Optional[Type[T]] = None,
    ) -> Union[T, Dict[str, Any], List[Dict[str, Any]]]:
        """
        Выполняет PUT-запрос к API Неосинтез.

        Args:
            endpoint: Конечная точка API
            data: Данные запроса
            params: URL-параметры запроса
            headers: Дополнительные заголовки
            response_model: Pydantic-модель для валидации ответа

        Returns:
            Union[T, Dict[str, Any], List[Dict[str, Any]]]: Ответ API
        """
        return await self._request(
            method="PUT",
            endpoint=endpoint,
            data=data,
            params=params,
            headers=headers,
            response_model=response_model,
        )

    async def delete(
        self,
        endpoint: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        response_model: Optional[Type[T]] = None,
    ) -> Union[T, Dict[str, Any], List[Dict[str, Any]]]:
        """
        Выполняет DELETE-запрос к API Неосинтез.

        Args:
            endpoint: Конечная точка API
            params: URL-параметры запроса
            headers: Дополнительные заголовки
            response_model: Pydantic-модель для валидации ответа

        Returns:
            Union[T, Dict[str, Any], List[Dict[str, Any]]]: Ответ API
        """
        return await self._request(
            method="DELETE",
            endpoint=endpoint,
            params=params,
            headers=headers,
            response_model=response_model,
        )
