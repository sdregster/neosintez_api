"""
Ресурсный класс для работы с контентом (файлами) в API Неосинтез.
"""

import logging
from pathlib import Path
from typing import Optional, Union

import aiohttp

from neosintez_api.core.resources.base import BaseResource


logger = logging.getLogger("neosintez_api.resources.content")


class ContentResource(BaseResource):
    """
    Ресурсный класс для работы с контентом (файлами) в API Неосинтез.
    """

    async def upload(self, file_path: Union[str, Path], filename: Optional[str] = None) -> dict:
        """
        Загружает файл в API Неосинтез через multipart/form-data.

        Args:
            file_path: Путь к файлу для загрузки
            filename: Имя файла (если нужно переопределить)

        Returns:
            dict: Данные о загруженном контенте

        Raises:
            Exception: В случае ошибки загрузки
        """
        endpoint = "api/content"
        file_path = Path(file_path)
        if not file_path.exists() or not file_path.is_file():
            raise FileNotFoundError(f"Файл не найден: {file_path}")
        send_filename = filename or file_path.name

        # Получаем сессию и заголовки
        session = self.client.session
        headers = await self.client._get_headers()
        # Удаляем Content-Type, aiohttp сам выставит boundary для multipart
        headers.pop("Content-Type", None)

        logger.debug(f"Загрузка файла '{file_path}' как '{send_filename}' на эндпоинт {endpoint}")
        data = aiohttp.FormData()
        data.add_field(
            name="file",
            value=file_path.open("rb"),
            filename=send_filename,
            content_type="application/octet-stream",
        )

        async with session.post(endpoint, data=data, headers=headers, ssl=self.client.settings.verify_ssl) as response:
            logger.debug(f"Ответ сервера: {response.status}")
            if response.status >= 400:
                text = await response.text()
                logger.error(f"Ошибка загрузки файла: {response.status} - {text}")
                raise Exception(f"Ошибка загрузки файла: {response.status} - {text}")
            resp_json = await response.json()
            logger.debug(f"Ответ JSON: {resp_json}")
            return resp_json
