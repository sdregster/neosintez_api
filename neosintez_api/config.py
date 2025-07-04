"""
Конфигурационные параметры для работы с API Неосинтез.
"""

from typing import Optional

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    base_url: AnyHttpUrl = Field("https://construction.irkutskoil.ru/", alias="NEOSINTEZ_BASE_URL")
    username: str = Field("InkTool", alias="NEOSINTEZ_USERNAME")
    password: str = Field("---", alias="NEOSINTEZ_PASSWORD")
    client_id: str
    client_secret: str
    max_connections: int = 100
    timeout: int = 60
    verify_ssl: bool = Field(True, alias="NEOSINTEZ_VERIFY_SSL")
    test_folder_id: Optional[str] = None
    test_folder_id_2: Optional[str] = None
    trash_folder_id: Optional[str] = None
    request_timeout: int = Field(60, alias="NEOSINTEZ_REQUEST_TIMEOUT")

    # Настройки кэша метаданных
    metadata_cache_ttl: int = 1800  # 30 минут в секундах
    metadata_cache_max_size: int = 500  # Максимум записей в кэше

    # Настройки retry механизма
    retry_max_attempts: int = 3  # Максимум попыток
    retry_multiplier: float = 1.0  # Множитель для exponential backoff
    retry_min_wait: float = 1.0  # Минимальная задержка в секундах
    retry_max_wait: float = 60.0  # Максимальная задержка в секундах
    retry_jitter: bool = True  # Добавлять случайный джиттер

    model_config = SettingsConfigDict(
        env_prefix="NEOSINTEZ_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


class PerformanceSettings:
    """НОВЫЕ настройки производительности для оптимизированного импорта"""

    # Настройки параллельности создания объектов
    MAX_CONCURRENT_OBJECT_CREATION = 3  # Консервативное значение для стабильности

    # Настройки параллельности установки атрибутов
    MAX_CONCURRENT_ATTRIBUTE_SETTING = 8  # Больше для batch операций

    # Настройки кэширования
    ENABLE_CLASS_METADATA_CACHING = True
    CLASS_CACHE_SIZE = 100  # Максимум классов в кэше

    # Настройки мониторинга
    LOG_PERFORMANCE_STATS = True
    PERFORMANCE_BASELINE_TIME = 0.43  # Секунд на объект до оптимизаций

    # Пороги для рекомендаций
    SLOW_OBJECT_CREATION_THRESHOLD = 0.15  # Секунд на объект

    @classmethod
    def get_optimized_settings(cls, object_count: int) -> dict:
        """
        Возвращает оптимизированные настройки на основе количества объектов.

        Args:
            object_count: Количество объектов для создания

        Returns:
            dict: Словарь с настройками производительности
        """
        if object_count < 100:
            # Для небольших импортов увеличиваем параллельность
            return {
                "max_concurrent_create": 5,
                "max_concurrent_attrs": 10,
            }
        elif object_count < 500:
            # Средние импорты - балансируем нагрузку
            return {
                "max_concurrent_create": 3,
                "max_concurrent_attrs": 8,
            }
        else:
            # Большие импорты - осторожно с нагрузкой на сервер
            return {
                "max_concurrent_create": 2,
                "max_concurrent_attrs": 6,
            }


settings = NeosintezConfig()
