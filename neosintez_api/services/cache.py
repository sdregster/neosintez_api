"""
Сервис кэширования данных API Неосинтез.

Позволяет кэшировать результаты запросов к API для уменьшения нагрузки
и повышения производительности приложения.
"""

import time
from typing import Any, Callable, Dict, Generic, Optional, TypeVar


T = TypeVar("T")


class TTLCache(Generic[T]):
    """
    Простой кэш с временем жизни (Time-To-Live).

    Attributes:
        default_ttl: Время жизни записей кэша по умолчанию (в секундах)
        max_size: Максимальный размер кэша
    """

    def __init__(self, default_ttl: int = 300, max_size: int = 1000):
        """
        Инициализирует кэш с указанными параметрами.

        Args:
            default_ttl: Время жизни записей по умолчанию (в секундах)
            max_size: Максимальное количество записей в кэше
        """
        self._cache: Dict[str, Dict[str, Any]] = {}
        self.default_ttl = default_ttl
        self.max_size = max_size

    def get(self, key: str) -> Optional[T]:
        """
        Получает значение из кэша по ключу.

        Args:
            key: Ключ для поиска в кэше

        Returns:
            Optional[T]: Значение из кэша или None, если ключ не найден или запись устарела
        """
        if key not in self._cache:
            return None

        entry = self._cache[key]
        now = time.time()

        # Проверка срока действия
        if entry["expiry"] < now:
            # Удаляем устаревшую запись
            del self._cache[key]
            return None

        return entry["value"]

    def set(self, key: str, value: T, ttl: Optional[int] = None) -> None:
        """
        Устанавливает значение в кэш с указанным временем жизни.

        Args:
            key: Ключ для сохранения в кэше
            value: Значение для сохранения
            ttl: Время жизни записи (в секундах). Если None, используется default_ttl.
        """
        # Если кэш достиг максимального размера, удаляем самую старую запись
        if len(self._cache) >= self.max_size:
            self._remove_oldest_entry()

        expiry = time.time() + (ttl if ttl is not None else self.default_ttl)
        self._cache[key] = {"value": value, "expiry": expiry, "created": time.time()}

    def clear(self) -> None:
        """Очищает весь кэш."""
        self._cache.clear()

    def remove(self, key: str) -> None:
        """
        Удаляет запись из кэша по ключу.

        Args:
            key: Ключ для удаления
        """
        if key in self._cache:
            del self._cache[key]

    def _remove_oldest_entry(self) -> None:
        """Удаляет самую старую запись из кэша."""
        if not self._cache:
            return

        oldest_key = min(
            self._cache.keys(), key=lambda k: self._cache[k].get("created", 0)
        )
        del self._cache[oldest_key]

    def size(self) -> int:
        """
        Возвращает текущий размер кэша.

        Returns:
            int: Количество записей в кэше
        """
        return len(self._cache)


def cached(ttl: Optional[int] = None):
    """
    Декоратор для кэширования результатов методов класса.

    Args:
        ttl: Время жизни кэша (в секундах). Если None, используется default_ttl кэша.

    Returns:
        Callable: Декоратор функции
    """

    def decorator(func: Callable) -> Callable:
        """
        Декоратор функции.

        Args:
            func: Декорируемая функция

        Returns:
            Callable: Обёртка функции
        """

        async def wrapper(self, *args, **kwargs) -> Any:
            """
            Обёртка функции с кэшированием.

            Args:
                self: Экземпляр класса
                args: Позиционные аргументы функции
                kwargs: Именованные аргументы функции

            Returns:
                Any: Результат выполнения функции
            """
            # Проверяем, есть ли у объекта кэш
            if not hasattr(self, "_cache") or self._cache is None:
                # Если кэша нет, выполняем функцию без кэширования
                return await func(self, *args, **kwargs)

            # Формируем ключ кэша из имени функции и аргументов
            key_parts = [func.__name__]
            key_parts.extend([str(arg) for arg in args])
            key_parts.extend([f"{k}={v}" for k, v in sorted(kwargs.items())])
            cache_key = ":".join(key_parts)

            # Проверяем кэш
            result = self._cache.get(cache_key)
            if result is not None:
                return result

            # Если в кэше нет, выполняем функцию
            result = await func(self, *args, **kwargs)

            # Сохраняем результат в кэше
            self._cache.set(cache_key, result, ttl)

            return result

        return wrapper

    return decorator
