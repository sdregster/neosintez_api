"""
Сервисный слой для работы с контентом (файлами) через ContentResource.
Обеспечивает загрузку файлов и может быть расширен для других операций с контентом.
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Union


if TYPE_CHECKING:
    from neosintez_api.core.client import NeosintezClient

logger = logging.getLogger("neosintez_api.services.content_service")


class ContentService:
    """
    Сервис для работы с контентом (файлами) в Неосинтезе.
    Предоставляет высокоуровневые методы для загрузки и управления файлами.
    """

    def __init__(self, client: "NeosintezClient"):
        """
        Инициализирует сервис с клиентом API.

        Args:
            client: Экземпляр клиента для взаимодействия с API.
        """
        self.client = client

    async def upload_content(self, file_path: Union[str, Path], filename: Optional[str] = None) -> dict:
        """
        Загружает файл в API Неосинтез и возвращает метаданные загруженного контента.

        Args:
            file_path: Путь к файлу для загрузки
            filename: Имя файла (если нужно переопределить)

        Returns:
            dict: Данные о загруженном контенте

        Raises:
            Exception: В случае ошибки загрузки
        """
        logger.info(f"Загрузка файла '{file_path}' через ContentService...")
        return await self.client.content.upload(file_path, filename=filename)
