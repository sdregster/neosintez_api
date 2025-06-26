"""
Клиент для работы с API Неосинтез.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Type, TypeVar, Union, Tuple

import aiohttp
import warnings

from .config import NeosintezSettings
from .exceptions import (
    NeosintezAPIError,
    NeosintezAuthError,
    NeosintezConnectionError,
    NeosintezTimeoutError,
)
from .utils import parse_error_response, retry, CustomJSONEncoder

from .resources import (
    ObjectsResource,
    AttributesResource,
    ClassesResource,
)

# Настройка логгера
logger = logging.getLogger("neosintez_api")
logger.setLevel(logging.DEBUG)  # Устанавливаем уровень логирования на DEBUG

T = TypeVar("T")

warnings.warn("Импорт из neosintez_api.client устарел, используйте neosintez_api.core.client", DeprecationWarning)
from .core.client import NeosintezClient

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

        # Инициализация ресурсов
        self.objects = ObjectsResource(self)
        self.attributes = AttributesResource(self)
        self.classes = ClassesResource(self)

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

        # Используем относительный путь
        url = endpoint.lstrip("/")

        json_data = None
        if data is not None:
            if isinstance(data, (dict, list)):
                json_data = data
            elif hasattr(data, "model_dump"):
                json_data = data.model_dump()
            # Fallback для других типов данных
            else:
                json_data = data

        try:
            logger.debug(f"Отправка запроса {method} {url}")
            
            # Используем dumps с CustomJSONEncoder для сериализации UUID и других специальных типов
            json_str = None
            if json_data is not None:
                json_str = json.dumps(json_data, cls=CustomJSONEncoder)
                logger.debug(f"JSON данные запроса: {json_str}")
            
            async with self.session.request(
                method, url, params=params, 
                data=json_str if json_str else None,
                headers=request_headers
            ) as response:
                if response.status < 400:
                    if response.status == 204:  # No Content
                        return {}

                    content_type = response.headers.get("Content-Type", "")
                    if "application/json" in content_type:
                        result = await response.json()

                        # Если указана модель для валидации, используем её
                        if response_model is not None:
                            return response_model.model_validate(result)
                        return result
                    else:
                        return {"content": await response.text()}
                else:
                    error_info = await parse_error_response(response)
                    status_code = response.status
                    message = error_info.get("message", "Unknown error")
                    data = error_info.get("data", None)

                    logger.error(
                        f"Ошибка API: {status_code} - {message}",
                        extra={"response_data": data},
                    )

                    raise NeosintezAPIError(status_code, message, data)

        except aiohttp.ClientConnectionError as e:
            logger.error(f"Ошибка соединения: {str(e)}")
            raise NeosintezConnectionError(f"Ошибка соединения: {str(e)}")
        except aiohttp.ClientResponseError as e:
            logger.error(f"Ошибка ответа: {str(e)}")
            raise NeosintezAPIError(e.status, f"Ошибка ответа: {str(e)}")
        except asyncio.TimeoutError as e:
            logger.error(f"Таймаут запроса: {str(e)}")
            raise NeosintezTimeoutError(f"Таймаут запроса: {str(e)}")
        except Exception as e:
            logger.error(f"Неожиданная ошибка: {str(e)}")
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
        Выполняет HTTP-запрос к API Neosintez и возвращает код статуса и тело ответа без обработки ошибок.
        Этот метод используется для исследования API.

        Args:
            method: HTTP-метод (GET, POST, PUT, DELETE)
            endpoint: Конечная точка API
            params: URL-параметры запроса
            data: Данные запроса
            headers: Дополнительные заголовки

        Returns:
            Tuple[int, Any]: Код статуса и данные ответа

        Raises:
            NeosintezAuthError: При ошибке аутентификации
            NeosintezConnectionError: При ошибке соединения
        """
        if not self._session or self._session.closed:
            await self.auth()

        request_headers = await self._get_headers()
        if headers:
            request_headers.update(headers)

        if data is not None and not isinstance(data, (str, bytes)):
            data = json.dumps(data)

        logger.debug(f"Отправка запроса {method} {endpoint}")

        try:
            async with self.session.request(
                method,
                endpoint,
                params=params,
                data=data,
                headers=request_headers,
                ssl=self.settings.verify_ssl,
            ) as response:
                logger.debug(f"Получен ответ с кодом: {response.status}")

                # Пытаемся получить ответ как JSON
                try:
                    result = await response.json(content_type=None)
                except json.JSONDecodeError:
                    # Если не удалось, получаем текст
                    result = await response.text()

                return response.status, result

        except aiohttp.ClientConnectionError as e:
            logger.error(f"Ошибка соединения: {str(e)}")
            raise NeosintezConnectionError(f"Ошибка соединения: {str(e)}")
        except aiohttp.ClientResponseError as e:
            logger.error(f"Ошибка ответа: {str(e)}")
            return e.status, {"error": str(e)}
        except asyncio.TimeoutError as e:
            logger.error(f"Таймаут запроса: {str(e)}")
            raise NeosintezTimeoutError(f"Таймаут запроса: {str(e)}")
        except Exception as e:
            logger.error(f"Неожиданная ошибка: {str(e)}")
            raise
