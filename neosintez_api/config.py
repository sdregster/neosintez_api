"""
Конфигурационные параметры для работы с API Неосинтез.
"""

from typing import Optional

from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings


class NeosintezSettings(BaseSettings):
    """
    Настройки подключения к API Неосинтез.

    Attributes:
        base_url: URL API Неосинтез
        username: Имя пользователя
        password: Пароль
        client_id: ID клиента
        client_secret: Секрет клиента
        max_connections: Максимальное количество одновременных соединений
        timeout: Таймаут запроса в секундах
        verify_ssl: Проверять SSL сертификаты
        test_folder_id: ID тестовой папки для создания объектов в тестах
    """

    base_url: AnyHttpUrl
    username: str
    password: str
    client_id: str
    client_secret: str
    max_connections: int = 100
    timeout: int = 60
    verify_ssl: bool = True
    test_folder_id: Optional[str] = None

    class Config:
        """Конфигурация настроек."""

        env_prefix = "NEOSINTEZ_"
        case_sensitive = False
        validate_by_name = True
        env_file = ".env"
        extra = "ignore"
