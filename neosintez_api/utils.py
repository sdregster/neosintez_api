"""
Утилиты для работы с API Неосинтез.
"""

import asyncio
import json
import logging
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, TypeVar

import aiohttp

from .exceptions import (
    NeosintezConnectionError,
    NeosintezTimeoutError,
)

# Настройка логирования
logger = logging.getLogger("neosintez_api")

T = TypeVar("T")


async def retry_async(
    func: Callable[..., T],
    attempts: int = 3,
    delay: int = 1,
    exceptions: List[type] = None,
) -> T:
    """
    Декоратор для повторного выполнения асинхронной функции при возникновении ошибки.

    Args:
        func: Асинхронная функция для выполнения
        attempts: Количество попыток
        delay: Задержка между попытками в секундах
        exceptions: Список исключений, на которые нужно реагировать повторными попытками

    Returns:
        Результат выполнения функции

    Raises:
        Exception: Если все попытки завершились с ошибкой
    """
    if exceptions is None:
        exceptions = [NeosintezConnectionError, NeosintezTimeoutError]

    last_exception = None

    for attempt in range(1, attempts + 1):
        try:
            return await func()
        except tuple(exceptions) as e:
            last_exception = e
            if attempt < attempts:
                logger.warning(
                    f"Попытка {attempt} из {attempts} не удалась. "
                    f"Ошибка: {str(e)}. Повтор через {delay} сек..."
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    f"Все {attempts} попыток не удались. Последняя ошибка: {str(e)}"
                )
                raise
        except Exception as e:
            logger.error(f"Неожиданная ошибка: {str(e)}")
            raise

    # Этот код не должен выполняться, но добавлен для типизации
    assert last_exception is not None
    raise last_exception


def retry(
    attempts: int = 3,
    delay: int = 1,
    exceptions: Optional[List[type]] = None,
) -> Callable:
    """
    Декоратор для повторных попыток выполнения асинхронной функции.

    Args:
        attempts: Количество попыток
        delay: Задержка между попытками в секундах
        exceptions: Список исключений, на которые нужно реагировать повторными попытками

    Returns:
        Декорированная функция
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            return await retry_async(
                lambda: func(*args, **kwargs),
                attempts=attempts,
                delay=delay,
                exceptions=exceptions,
            )

        return wrapper

    return decorator


def normalize_dict_keys(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Нормализует ключи словаря, приводя их к camelCase формату.

    Args:
        data: Исходный словарь

    Returns:
        Dict[str, Any]: Словарь с нормализованными ключами
    """
    if not isinstance(data, dict):
        return data

    result = {}
    for key, value in data.items():
        # Приводим ключ к camelCase
        camel_key = key[0].lower() + key[1:] if key else key

        # Рекурсивно обрабатываем вложенные словари
        if isinstance(value, dict):
            result[camel_key] = normalize_dict_keys(value)
        elif isinstance(value, list):
            result[camel_key] = [
                normalize_dict_keys(i) if isinstance(i, dict) else i for i in value
            ]
        else:
            result[camel_key] = value

    return result


async def parse_error_response(response: aiohttp.ClientResponse) -> Dict[str, Any]:
    """
    Парсит ответ с ошибкой от API и возвращает информацию об ошибке.

    Args:
        response: Объект ответа aiohttp

    Returns:
        Dict[str, Any]: Словарь с информацией об ошибке
    """
    status_code = response.status

    try:
        response_text = await response.text()
        message = response_text
        response_data = None

        # Пытаемся распарсить JSON из тела ответа
        try:
            response_data = json.loads(response_text)
            if isinstance(response_data, dict):
                # Пытаемся извлечь сообщение об ошибке
                if "error" in response_data:
                    message = response_data["error"]
                elif "message" in response_data:
                    message = response_data["message"]
                elif "Message" in response_data:
                    message = response_data["Message"]
        except json.JSONDecodeError:
            pass

        return {"status_code": status_code, "message": message, "data": response_data}
    except Exception as e:
        logger.error(f"Ошибка при парсинге ответа с ошибкой: {str(e)}")
        return {
            "status_code": status_code,
            "message": f"Ошибка при парсинге ответа: {str(e)}",
            "data": None,
        }


def chunk_list(items: List[Any], size: int) -> List[List[Any]]:
    """
    Разделяет список на части указанного размера.

    Args:
        items: Список для разделения
        size: Размер каждой части

    Returns:
        List[List[Any]]: Список частей исходного списка
    """
    return [items[i : i + size] for i in range(0, len(items), size)]
