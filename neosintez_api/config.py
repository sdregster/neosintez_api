"""
Конфигурационные параметры для работы с API Неосинтез.
"""

from functools import lru_cache
from typing import Optional

from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings


class NeosintezConfig(BaseSettings):
    """
    Настройки для подключения к API Неосинтез.
    Читаются из переменных окружения или .env файла.

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
        test_folder_id_2: ID второй тестовой папки для создания объектов в тестах
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
    test_folder_id_2: Optional[str] = None

    # Настройки кэша метаданных
    metadata_cache_ttl: int = 1800  # 30 минут в секундах
    metadata_cache_max_size: int = 500  # Максимум записей в кэше

    # Настройки retry механизма
    retry_max_attempts: int = 3  # Максимум попыток
    retry_multiplier: float = 1.0  # Множитель для exponential backoff
    retry_min_wait: float = 1.0  # Минимальная задержка в секундах
    retry_max_wait: float = 60.0  # Максимальная задержка в секундах
    retry_jitter: bool = True  # Добавлять случайный джиттер

    class Config:
        """Конфигурация настроек."""

        env_prefix = "NEOSINTEZ_"
        case_sensitive = False
        validate_by_name = True
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> NeosintezConfig:
    """
    Возвращает экземпляр настроек, используя кеширование.
    """
    return NeosintezConfig()
