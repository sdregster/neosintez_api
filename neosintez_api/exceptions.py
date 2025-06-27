"""
Модуль с пользовательскими исключениями для API Неосинтез.
"""

from typing import Any


class ApiError(Exception):
    """
    Базовый класс для всех исключений API Неосинтез.
    """

    def __init__(self, message: str, details: Any = None):
        """
        Инициализирует исключение.

        Args:
            message: Сообщение об ошибке
            details: Дополнительные детали ошибки
        """
        self.message = message
        self.details = details
        super().__init__(message)


class AuthenticationError(ApiError):
    """
    Исключение для ошибок аутентификации.
    """

    pass


class NotFoundError(ApiError):
    """
    Исключение для случаев, когда ресурс не найден.
    """

    pass


class ValidationError(ApiError):
    """
    Исключение для ошибок валидации данных.
    """

    pass


class RequestError(ApiError):
    """
    Исключение для ошибок запроса к API.
    """

    pass


class ModelValidationError(ApiError):
    """
    Исключение для ошибок валидации Pydantic-моделей.
    """

    pass


class NeosintezAuthError(ApiError):
    """Ошибка аутентификации в API Неосинтез."""

    pass


class NeosintezAPIError(ApiError):
    """Ошибка при вызове API Неосинтез."""

    def __init__(self, status_code: int, message: str, details: Any = None):
        self.status_code = status_code
        self.message = message
        self.details = details
        super().__init__(f"Ошибка API Неосинтез [{status_code}]: {message}", details)


class NeosintezConnectionError(ApiError):
    """Ошибка соединения с сервером API Неосинтез."""

    pass


class NeosintezTimeoutError(ApiError):
    """Ошибка таймаута при запросе к API Неосинтез."""

    pass


class NeosintezValidationError(ApiError):
    """Ошибка валидации данных для API Неосинтез."""

    pass
