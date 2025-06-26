"""
Модуль retry для обработки ошибок API с exponential backoff.

Обеспечивает автоматическое повторение неудачных запросов
с интеллигентным backoff для 429 (Too Many Requests) и 5xx ошибок.
"""

import logging
from functools import wraps
from typing import Callable, List, Optional, Type, TypeVar

import httpx
from tenacity import (
    AsyncRetrying,
    RetryError,
    before_sleep_log,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    wait_random_exponential,
)


logger = logging.getLogger(__name__)

T = TypeVar("T")


class RetryableError(Exception):
    """Базовый класс для ошибок, подлежащих повторению."""

    pass


class RateLimitError(RetryableError):
    """Ошибка превышения лимита запросов (429)."""

    pass


class ServerError(RetryableError):
    """Ошибка сервера (5xx)."""

    pass


class RetryConfig:
    """Конфигурация retry механизма."""

    def __init__(
        self,
        max_attempts: int = 3,
        multiplier: float = 1.0,
        min_wait: float = 1.0,
        max_wait: float = 60.0,
        jitter: bool = True,
        retryable_status_codes: Optional[List[int]] = None,
        retryable_exceptions: Optional[List[Type[Exception]]] = None,
    ):
        """
        Инициализирует конфигурацию retry.

        Args:
            max_attempts: Максимальное количество попыток
            multiplier: Множитель для exponential backoff
            min_wait: Минимальная задержка в секундах
            max_wait: Максимальная задержка в секундах
            jitter: Добавлять ли случайный джиттер
            retryable_status_codes: HTTP коды, при которых нужен retry
            retryable_exceptions: Исключения, при которых нужен retry
        """
        self.max_attempts = max_attempts
        self.multiplier = multiplier
        self.min_wait = min_wait
        self.max_wait = max_wait
        self.jitter = jitter

        # По умолчанию повторяем для 429 и 5xx
        self.retryable_status_codes = retryable_status_codes or [429, 500, 502, 503, 504]

        # По умолчанию повторяем для сетевых ошибок и наших retry ошибок
        self.retryable_exceptions = retryable_exceptions or [
            httpx.ConnectError,
            httpx.ReadTimeout,
            httpx.WriteTimeout,
            httpx.PoolTimeout,
            httpx.NetworkError,
            RateLimitError,
            ServerError,
        ]


def _is_retryable_http_error(exception: Exception) -> bool:
    """
    Проверяет, является ли HTTP ошибка подходящей для retry.

    Args:
        exception: Исключение для проверки

    Returns:
        bool: True если ошибка подходит для retry
    """
    if isinstance(exception, httpx.HTTPStatusError):
        # 429 - Too Many Requests
        if exception.response.status_code == 429:
            return True
        # 5xx - Server errors
        if 500 <= exception.response.status_code < 600:
            return True
    return False


def _convert_http_error(func: Callable) -> Callable:
    """
    Декоратор для преобразования HTTP ошибок в retry-совместимые исключения.

    Args:
        func: Функция для декорирования

    Returns:
        Callable: Обёрнутая функция
    """

    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except httpx.HTTPStatusError as e:
            # Преобразуем HTTP ошибки в наши retry исключения
            if e.response.status_code == 429:
                # Извлекаем Retry-After header если есть
                retry_after = e.response.headers.get("Retry-After")
                message = "Rate limit exceeded (429)"
                if retry_after:
                    message += f", Retry-After: {retry_after}"
                logger.warning(message)
                raise RateLimitError(message) from e
            elif 500 <= e.response.status_code < 600:
                message = f"Server error {e.response.status_code}: {e.response.text}"
                logger.warning(message)
                raise ServerError(message) from e
            else:
                # Для остальных HTTP ошибок не делаем retry
                raise
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout, httpx.PoolTimeout, httpx.NetworkError) as e:
            # Сетевые ошибки логируем и пробрасываем дальше для retry
            logger.warning(f"Network error: {e}")
            raise

    return wrapper


def with_retry(config: Optional[RetryConfig] = None) -> Callable:
    """
    Декоратор для добавления retry логики к асинхронным функциям.

    Args:
        config: Конфигурация retry, если None - используется по умолчанию

    Returns:
        Callable: Декоратор функции
    """
    if config is None:
        config = RetryConfig()

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            # Применяем преобразование HTTP ошибок
            converted_func = _convert_http_error(func)

            # Настраиваем wait стратегию
            if config.jitter:
                wait_strategy = wait_random_exponential(multiplier=config.multiplier, max=config.max_wait)
            else:
                wait_strategy = wait_exponential(multiplier=config.multiplier, min=config.min_wait, max=config.max_wait)

            # Настраиваем retry условия
            retry_condition = retry_if_exception_type(tuple(config.retryable_exceptions))

            # Создаём AsyncRetrying объект
            retryer = AsyncRetrying(
                stop=stop_after_attempt(config.max_attempts),
                wait=wait_strategy,
                retry=retry_condition,
                before_sleep=before_sleep_log(logger, logging.WARNING),
                reraise=True,
            )

            # Выполняем с retry
            try:
                async for attempt in retryer:
                    with attempt:
                        result = await converted_func(*args, **kwargs)
                        logger.debug(f"Request succeeded on attempt {attempt.retry_state.attempt_number}")
                        return result
            except RetryError as e:
                # Все попытки исчерпаны
                logger.error(f"All {config.max_attempts} retry attempts failed")
                # Пробрасываем последнее исключение
                if e.last_attempt.failed:
                    raise e.last_attempt.exception() from e
                raise

        return wrapper

    return decorator


class RetryableHTTPClient:
    """
    HTTP клиент с встроенным retry механизмом.

    Автоматически повторяет запросы при ошибках 429/5xx и сетевых проблемах.
    """

    def __init__(self, client: httpx.AsyncClient, config: Optional[RetryConfig] = None):
        """
        Инициализирует retry клиент.

        Args:
            client: Базовый httpx.AsyncClient
            config: Конфигурация retry
        """
        self.client = client
        self.config = config or RetryConfig()

    @with_retry()
    async def get(self, url: str, **kwargs) -> httpx.Response:
        """GET запрос с retry."""
        response = await self.client.get(url, **kwargs)
        response.raise_for_status()
        return response

    @with_retry()
    async def post(self, url: str, **kwargs) -> httpx.Response:
        """POST запрос с retry."""
        response = await self.client.post(url, **kwargs)
        response.raise_for_status()
        return response

    @with_retry()
    async def put(self, url: str, **kwargs) -> httpx.Response:
        """PUT запрос с retry."""
        response = await self.client.put(url, **kwargs)
        response.raise_for_status()
        return response

    @with_retry()
    async def patch(self, url: str, **kwargs) -> httpx.Response:
        """PATCH запрос с retry."""
        response = await self.client.patch(url, **kwargs)
        response.raise_for_status()
        return response

    @with_retry()
    async def delete(self, url: str, **kwargs) -> httpx.Response:
        """DELETE запрос с retry."""
        response = await self.client.delete(url, **kwargs)
        response.raise_for_status()
        return response

    async def request(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Универсальный метод запроса с retry."""
        retry_wrapper = with_retry(self.config)

        @retry_wrapper
        async def _request():
            response = await self.client.request(method, url, **kwargs)
            response.raise_for_status()
            return response

        return await _request()


def create_retry_config_from_settings(
    max_attempts: int = 3,
    multiplier: float = 1.0,
    min_wait: float = 1.0,
    max_wait: float = 60.0,
    jitter: bool = True,
) -> RetryConfig:
    """
    Создаёт конфигурацию retry из настроек приложения.

    Args:
        max_attempts: Максимум попыток
        multiplier: Множитель backoff
        min_wait: Минимальная задержка
        max_wait: Максимальная задержка
        jitter: Использовать джиттер

    Returns:
        RetryConfig: Конфигурация retry
    """
    return RetryConfig(
        max_attempts=max_attempts,
        multiplier=multiplier,
        min_wait=min_wait,
        max_wait=max_wait,
        jitter=jitter,
    )
