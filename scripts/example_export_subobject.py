"""
Пример экспорта данных из Неосинтеза нативным способом.

Демонстрирует экспорт отчета через встроенный механизм экспорта Неосинтеза.
Использует тот же механизм, что и веб-интерфейс при экспорте отчетов.
Просто копирует исходную нагрузку из curl, подставляя только GUID объекта.
"""

import asyncio
import logging
import os
import re
from pathlib import Path
from typing import Optional

import aiohttp
from dotenv import load_dotenv

from neosintez_api import NeosintezAPIError, NeosintezClient
from neosintez_api.config import NeosintezConfig


# Настройка логирования для вывода информации в консоль
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


# Статичные значения из исходного curl запроса
REPORT_GUID = "c9d0e59b-da7b-f011-91ed-005056b6948b"

# Исходная нагрузка из curl (--data-raw)
# Заменяем только GUID объекта: 3cf85fb6-7c9d-11f0-9262-005056b6c24b -> {object_guid}
ORIGINAL_DATA_RAW = (
    "stiweb_component=Viewer&stiweb_action=ExportReport&stiweb_parameters="
    "eyJ2aWV3ZXJJZCI6InZpZXdlciIsInJvdXRlcyI6eyJjb250cm9sbGVyIjoiUmVwb3J0cyIsImFjdGlvbiI6IlZpZXdlciIsImlkIjoiYzlkMGU1OWItZGE3Yi1mMDExLTkxZWQtMDA1MDU2YjY5NDhiIn0sImZvcm1WYWx1ZXMiOnt9LCJjbGllbnRHdWlkIjoiNWUyNDQ5MGRmOWQ0NDljYjkyMmIzMGNlNGQ5NTM3MTgiLCJkcmlsbERvd25HdWlkIjpudWxsLCJkYXNoYm9hcmREcmlsbERvd25HdWlkIjpudWxsLCJjYWNoZU1vZGUiOiJPYmplY3RDYWNoZSIsImNhY2hlVGltZW91dCI6MTAsImNhY2hlSXRlbVByaW9yaXR5IjoiRGVmYXVsdCIsInBhZ2VOdW1iZXIiOjAsIm9yaWdpbmFsUGFnZU51bWJlciI6MCwicmVwb3J0VHlwZSI6IlJlcG9ydCIsInpvb20iOjEwMCwidmlld01vZGUiOiJTaW5nbGVQYWdlIiwic2hvd0Jvb2ttYXJrcyI6dHJ1ZSwib3BlbkxpbmtzV2luZG93IjoiX2JsYW5rIiwiY2hhcnRSZW5kZXJUeXBlIjoiQW5pbWF0ZWRWZWN0b3IiLCJyZXBvcnREaXNwbGF5TW9kZSI6IkRpdiIsImRyaWxsRG93blBhcmFtZXRlcnMiOltdLCJlZGl0YWJsZVBhcmFtZXRlcnMiOm51bGwsInVzZVJlbGF0aXZlVXJscyI6dHJ1ZSwicGFzc1F1ZXJ5UGFyYW1ldGVyc0ZvclJlc291cmNlcyI6dHJ1ZSwicGFzc1F1ZXJ5UGFyYW1ldGVyc1RvUmVwb3J0Ijp0cnVlLCJ2ZXJzaW9uIjoiMjAyMy4zLjQiLCJyZXBvcnREZXNpZ25lck1vZGUiOmZhbHNlLCJpbWFnZXNRdWFsaXR5IjoiTm9ybWFsIiwicGFyYW1ldGVyc1BhbmVsU29ydERhdGFJdGVtcyI6dHJ1ZSwiY29tYmluZVJlcG9ydFBhZ2VzIjpmYWxzZSwiYWxsb3dBdXRvVXBkYXRlQ29va2llcyI6ZmFsc2UsImV4cG9ydEZvcm1hdCI6IkV4Y2VsMjAwNyIsImV4cG9ydFNldHRpbmdzIjp7IlBhZ2VSYW5nZSI6IkFsbCIsIkV4Y2VsVHlwZSI6IkV4Y2VsMjAwNyIsIkltYWdlUmVzb2x1dGlvbiI6IjEwMCIsIkltYWdlUXVhbGl0eSI6IjAuNzUiLCJFeHBvcnRPYmplY3RGb3JtYXR0aW5nIjpmYWxzZSwiVXNlT25lUGFnZUhlYWRlckFuZEZvb3RlciI6ZmFsc2UsIkV4cG9ydEVhY2hQYWdlVG9TaGVldCI6dHJ1ZSwiRXhwb3J0UGFnZUJyZWFrcyI6ZmFsc2UsIkRhdGFFeHBvcnRNb2RlIjoiQWxsQmFuZHMiLCJSZXN0cmljdEVkaXRpbmciOiJObyJ9fQ%3D%3D"
    "&__RequestVerificationToken="
)


async def get_csrf_token(client: NeosintezClient, object_guid: str) -> str:
    """
    Получает CSRF токен из cookie сессии клиента.

    Args:
        client: Клиент API Неосинтеза
        object_guid: GUID объекта для экспорта (не используется, но оставлен для совместимости)

    Returns:
        str: CSRF токен из cookie

    Raises:
        NeosintezAPIError: Если не удалось получить токен
    """
    # Получаем страницу отчета для установки cookie с CSRF токеном
    report_url = f"/reports/viewer/{REPORT_GUID}?Sys_Context_Object={object_guid}"
    session = client.session
    headers = await client._get_headers()
    headers["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"

    async with session.get(report_url, headers=headers, ssl=client.settings.verify_ssl) as response:
        if response.status != 200:
            text = await response.text()
            raise NeosintezAPIError(
                status_code=response.status,
                message=f"Не удалось получить страницу отчета: {response.status}",
                response_data=text,
            )

        # Ищем токен в заголовках Set-Cookie или в HTML
        csrf_token = None

        # Пытаемся найти в заголовках Set-Cookie
        set_cookie_header = response.headers.get("Set-Cookie", "")
        match = re.search(r'\.AspNetCore\.Antiforgery\.\w+=([^;]+)', set_cookie_header)
        if match:
            csrf_token = match.group(1)
            logger.info("Найден CSRF токен в Set-Cookie заголовке")

        # Если не нашли, ищем в HTML форме
        if not csrf_token:
            html = await response.text()
            match = re.search(r'name="__RequestVerificationToken"\s+value="([^"]+)"', html)
            if match:
                csrf_token = match.group(1)
                logger.info("Найден CSRF токен в HTML форме")

        # Если всё ещё не нашли, пытаемся извлечь из cookie jar сессии
        if not csrf_token:
            for cookie in session.cookie_jar:
                cookie_str = str(cookie)
                if "Antiforgery" in cookie_str:
                    match = re.search(r'\.AspNetCore\.Antiforgery\.\w+=([^;]+)', cookie_str)
                    if match:
                        csrf_token = match.group(1)
                        logger.info("Найден CSRF токен в cookie jar сессии")
                        break

        if not csrf_token:
            raise NeosintezAPIError(
                status_code=500,
                message="Не удалось найти CSRF токен",
                response_data=None,
            )

        logger.info("CSRF токен получен успешно")
        return csrf_token


async def export_report(
    client: NeosintezClient,
    object_guid: str,
    output_file: Optional[str] = None,
) -> bytes:
    """
    Экспортирует отчет из Неосинтеза для указанного объекта.

    Args:
        client: Клиент API Неосинтеза
        object_guid: GUID объекта для экспорта
        output_file: Путь к файлу для сохранения результата (опционально)

    Returns:
        bytes: Экспортированные данные (Excel файл)

    Raises:
        NeosintezAPIError: В случае ошибки экспорта
    """
    logger.info("Начинаем экспорт отчета для объекта: %s", object_guid)

    # Получаем CSRF токен
    csrf_token = await get_csrf_token(client, object_guid)

    # Формируем данные запроса: берем исходную нагрузку и подставляем CSRF токен
    data_raw = ORIGINAL_DATA_RAW + csrf_token

    # URL для экспорта (подставляем только GUID объекта)
    export_endpoint = f"/reports/viewer/{REPORT_GUID}/event?Sys_Context_Object={object_guid}"

    # Подготавливаем заголовки как в исходном curl
    session = client.session
    headers = await client._get_headers()
    headers["Accept"] = "*/*"
    headers["Content-Type"] = "application/x-www-form-urlencoded"
    headers["Referer"] = f"{client.settings.base_url}reports/viewer/{REPORT_GUID}?Sys_Context_Object={object_guid}"
    headers["Origin"] = str(client.settings.base_url).rstrip("/")

    logger.info("Выполняем POST запрос для экспорта: %s", export_endpoint)

    # Отправляем данные как строку (как в curl --data-raw)
    async with session.post(
        export_endpoint,
        data=data_raw,
        headers=headers,
        ssl=client.settings.verify_ssl,
    ) as response:
        logger.info("Статус ответа: %s", response.status)
        logger.debug("Заголовки ответа: %s", dict(response.headers))

        if response.status >= 400:
            text = await response.text()
            logger.error("Ошибка экспорта: %s – %s", response.status, text[:500])
            raise NeosintezAPIError(
                status_code=response.status,
                message=f"Ошибка экспорта: {response.status}",
                response_data=text[:500],
            )

        # Получаем данные (Excel файл)
        export_data = await response.read()
        logger.info("Получено данных: %d байт", len(export_data))

        # Сохраняем в файл, если указан
        if output_file:
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(export_data)
            logger.info("Данные сохранены в файл: %s", output_path)

        return export_data


async def main():
    """
    Главная функция для демонстрации экспорта отчета.
    """
    load_dotenv()

    # Создаем конфигурацию и переопределяем портал на operation при необходимости
    config = NeosintezConfig()
    if "construction.irkutskoil.ru" in str(config.base_url):
        config.base_url = str(config.base_url).replace("construction", "operation")
        logger.info("Используем URL: %s", config.base_url)

    # GUID объекта для экспорта (параметризован для переиспользования)
    # object_guid = "3cf85fb6-7c9d-11f0-9262-005056b6c24b"
    object_guid = "3cf85fce-7c9d-11f0-9262-005056b6c24b"

    # Подключение к API Неосинтез с переданной конфигурацией
    async with NeosintezClient(config) as client:
        # Экспортируем отчет
        output_file = f"exported_report_{object_guid}.xlsx"
        export_data = await export_report(client, object_guid, output_file)
        logger.info("Экспорт завершен успешно. Размер файла: %d байт", len(export_data))


if __name__ == "__main__":
    # Для Windows, где может быть ошибка с ProactorEventLoop
    if os.name == "nt":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
