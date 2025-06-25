"""
Конфигурация для API Неосинтез.
"""

import os
from typing import Optional
from pydantic import BaseModel, Field, HttpUrl, field_validator


class NeosintezSettings(BaseModel):
    """
    Настройки для подключения к API Неосинтез.

    Attributes:
        base_url: Базовый URL API Неосинтез
        username: Имя пользователя для аутентификации
        password: Пароль пользователя
        client_id: Идентификатор клиента
        client_secret: Секрет клиента
        timeout: Таймаут запросов (в секундах)
        max_connections: Максимальное количество одновременных соединений
        retry_attempts: Количество повторных попыток при ошибке
        retry_delay: Задержка между повторными попытками (в секундах)
        verify_ssl: Проверять ли SSL-сертификат
    """

    base_url: HttpUrl
    username: str
    password: str
    client_id: str
    client_secret: str
    timeout: int = Field(default=300, gt=0)
    max_connections: int = Field(default=20, gt=0)
    retry_attempts: int = Field(default=3, ge=0)
    retry_delay: int = Field(default=1, ge=0)
    verify_ssl: bool = Field(default=True)

    @field_validator("base_url")
    @classmethod
    def ensure_trailing_slash(cls, v):
        """Убедиться, что URL заканчивается на слеш."""
        v_str = str(v)
        if not v_str.endswith("/"):
            return f"{v_str}/"
        return v


def load_settings(
    base_url: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
    client_id: Optional[str] = None,
    client_secret: Optional[str] = None,
    env_prefix: str = "NEOSINTEZ_",
) -> NeosintezSettings:
    """
    Загружает настройки из переменных окружения и/или переданных параметров.

    Args:
        base_url: Базовый URL API Неосинтез. По умолчанию берется из NEOSINTEZ_BASE_URL.
        username: Имя пользователя. По умолчанию берется из NEOSINTEZ_USERNAME.
        password: Пароль пользователя. По умолчанию берется из NEOSINTEZ_PASSWORD.
        client_id: Идентификатор клиента. По умолчанию берется из NEOSINTEZ_CLIENT_ID.
        client_secret: Секрет клиента. По умолчанию берется из NEOSINTEZ_CLIENT_SECRET.
        env_prefix: Префикс для переменных окружения.

    Returns:
        NeosintezSettings: Объект с настройками подключения к API Неосинтез.

    Raises:
        ValueError: Если не указаны обязательные параметры.
    """
    settings_dict = {
        "base_url": base_url or os.getenv(f"{env_prefix}BASE_URL"),
        "username": username or os.getenv(f"{env_prefix}USERNAME"),
        "password": password or os.getenv(f"{env_prefix}PASSWORD"),
        "client_id": client_id or os.getenv(f"{env_prefix}CLIENT_ID"),
        "client_secret": client_secret or os.getenv(f"{env_prefix}CLIENT_SECRET"),
        "timeout": int(os.getenv(f"{env_prefix}TIMEOUT", "300")),
        "max_connections": int(os.getenv(f"{env_prefix}MAX_CONNECTIONS", "20")),
        "retry_attempts": int(os.getenv(f"{env_prefix}RETRY_ATTEMPTS", "3")),
        "retry_delay": int(os.getenv(f"{env_prefix}RETRY_DELAY", "1")),
        "verify_ssl": os.getenv(f"{env_prefix}VERIFY_SSL", "true").lower() == "true",
    }

    # Удаляем None значения
    settings_dict = {k: v for k, v in settings_dict.items() if v is not None}

    return NeosintezSettings.model_validate(settings_dict)
