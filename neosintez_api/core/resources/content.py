"""
Контент‑ресурс для API Неосинтез c корректным filename*=UTF‑8.
"""

import logging
import mimetypes
from pathlib import Path
from typing import Optional, Union

import aiohttp
from aiohttp import payload

from neosintez_api.core.resources.base import BaseResource


logger = logging.getLogger("neosintez_api.resources.content")


class ContentResource(BaseResource):
    async def upload(self, file_path: Union[str, Path], filename: Optional[str] = None) -> dict:
        """
        Загружает файл в API Неосинтез с корректным именем файла (без percent-encoding).

        Args:
            file_path: Путь к файлу для загрузки
            filename: Имя файла (если нужно переопределить)

        Returns:
            dict: Данные о загруженном контенте

        Raises:
            FileNotFoundError: Если файл не найден
            Exception: В случае ошибки загрузки
        """
        endpoint = "api/content"
        file_path = Path(file_path).resolve()

        logger.debug("Исходный путь к файлу: %s", file_path)
        logger.debug("Тип file_path: %s", type(file_path))

        if not file_path.is_file():
            logger.error("Файл не найден: %s", file_path)
            raise FileNotFoundError(file_path)

        send_filename = filename or file_path.name
        logger.debug("Имя файла для отправки (send_filename): %s", send_filename)
        logger.debug("Тип send_filename: %s", type(send_filename))
        logger.debug("Кодировка send_filename (bytes): %s", send_filename.encode("utf-8", errors="replace"))

        content_type, _ = mimetypes.guess_type(send_filename)
        content_type = content_type or "application/octet-stream"
        logger.debug("Определённый Content-Type: %s", content_type)

        session = self.client.session
        headers = await self.client._get_headers()
        logger.debug("Заголовки до удаления Content-Type: %s", headers)
        headers.pop("Content-Type", None)  # boundary → aiohttp
        logger.debug("Заголовки после удаления Content-Type: %s", headers)

        # ---------- собираем multipart вручную ----------
        mw = aiohttp.MultipartWriter("form-data")

        part_headers = {
            "Content-Disposition": f'form-data; name="file"; filename="{send_filename}"',
            "Content-Type": content_type,
        }
        logger.debug("part_headers: %s", part_headers)

        part = payload.BufferedReaderPayload(
            file_path.open("rb"),
            headers=part_headers,
        )
        mw.append_payload(part)
        logger.debug("Добавлен part: %s", part)
        logger.debug("part.headers: %s", dict(part.headers))
        # -------------------------------------------------

        logger.info("POST %s (filename='%s')", endpoint, send_filename)

        async with session.post(endpoint, data=mw, headers=headers, ssl=self.client.settings.verify_ssl) as r:
            logger.info("Статус ответа: %s", r.status)
            logger.debug("Заголовки ответа: %s", dict(r.headers))
            if r.status >= 400:
                text = await r.text()
                logger.error("Ошибка загрузки: %s – %s", r.status, text)
                raise Exception(f"upload error {r.status}: {text}")
            result = await r.json()
            logger.info("Ответ JSON: %s", result)
            return result
