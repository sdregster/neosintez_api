"""
Модуль с исключениями, которые могут возникать при работе с API Неосинтез.
"""


class NeosintezError(Exception):
    """
    Базовое исключение для ошибок API Неосинтез.

    Attributes:
        message: Сообщение об ошибке
    """

    def __init__(self, message: str):
        """
        Инициализирует исключение.

        Args:
            message: Сообщение об ошибке
        """
        self.message = message
        super().__init__(self.message)


class NeosintezAuthError(NeosintezError):
    """Ошибка аутентификации в API Неосинтез."""

    pass


class NeosintezAPIError(NeosintezError):
    """Ошибка при вызове API Неосинтез."""

    def __init__(self, status_code, message, response_data=None):
        self.status_code = status_code
        self.message = message
        self.response_data = response_data
        super().__init__(f"Ошибка API Неосинтез [{status_code}]: {message}")


class NeosintezConnectionError(NeosintezError):
    """Ошибка соединения с сервером API Неосинтез."""

    pass


class NeosintezTimeoutError(NeosintezError):
    """Ошибка таймаута при запросе к API Неосинтез."""

    pass


class NeosintezValidationError(NeosintezError):
    """Ошибка валидации данных для API Неосинтез."""

    pass
