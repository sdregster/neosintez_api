"""
Пример загрузки файла (контента) в Неосинтез через ContentService.

Файл для загрузки: 'КС-2 №28 от 19.11.2024 к КС3-000008847 от 19.11.2024.xlsx'
"""

import asyncio
import logging
from pathlib import Path

from neosintez_api.core.client import NeosintezClient
from neosintez_api.services.content_service import ContentService


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("example_content_upload")

EXAMPLE_FILE = Path("КС-2 №28 от 19.11.2024 к КС3-000008847 от 19.11.2024.xlsx")


async def main() -> None:
    """
    Загружает файл в Неосинтез и выводит результат (ContentValue).
    """
    if not EXAMPLE_FILE.exists():
        logger.error(f"Файл для загрузки не найден: {EXAMPLE_FILE.resolve()}")
        return

    async with NeosintezClient() as client:
        content_service = ContentService(client)
        logger.info(f"Загрузка файла: {EXAMPLE_FILE.name}")
        try:
            content_value = await content_service.upload_content(EXAMPLE_FILE)
            logger.info("Загрузка завершена успешно!")
            print("Результат загрузки (dict):")
            for key in ("Id", "Name", "MediaType", "Extension", "Size", "Version", "Hash", "TempToken"):
                print(f"{key}: {content_value.get(key)}")
        except Exception as e:
            logger.error(f"Ошибка при загрузке файла: {e}")


if __name__ == "__main__":
    asyncio.run(main())
