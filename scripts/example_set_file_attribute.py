"""
Пример загрузки файла в Неосинтез через ContentService и установки файлового атрибута объекту.

Файл для загрузки: C:\\python\neosintez_api\\object_a4e111df-a062-ee11-9184-005056b6948b.xlsx
GUID атрибута: c9ae17cd-e01a-e811-810c-9ec54093bb77
GUID объекта: 758bcc75-03b7-f011-91f9-005056b6948b
"""

import asyncio
import logging
from pathlib import Path

from dotenv import load_dotenv

from neosintez_api.config import NeosintezConfig
from neosintez_api.core.client import NeosintezClient
from neosintez_api.core.enums import WioAttributeType
from neosintez_api.services.content_service import ContentService


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("example_set_file_attribute")

# Константы для конфигурации
FILE_PATH = Path(r"C:\python\neosintez_api\object_a4e111df-a062-ee11-9184-005056b6948b.xlsx")
ATTRIBUTE_ID = "c9ae17cd-e01a-e811-810c-9ec54093bb77"
OBJECT_ID = "758bcc75-03b7-f011-91f9-005056b6948b"


async def main() -> None:
    """
    Загружает файл в Неосинтез и устанавливает файловый атрибут объекту.
    """
    load_dotenv()

    # Создаем конфигурацию и переопределяем портал на operation при необходимости
    config = NeosintezConfig()
    if "construction.irkutskoil.ru" in str(config.base_url):
        config.base_url = str(config.base_url).replace("construction", "operation")
        logger.info("Используем URL: %s", config.base_url)

    if not FILE_PATH.exists():
        logger.error(f"Файл для загрузки не найден: {FILE_PATH.resolve()}")
        return

    # Подключение к API Неосинтез с переданной конфигурацией
    async with NeosintezClient(config) as client:
        content_service = ContentService(client)

        # Шаг 1: Загрузка файла
        logger.info(f"Загрузка файла: {FILE_PATH.name}")
        try:
            content_value = await content_service.upload_content(FILE_PATH)
            logger.info("Загрузка завершена успешно!")

            # Выводим информацию о загруженном контенте
            print("\n--- Результат загрузки файла ---")
            for key in ("Id", "Name", "MediaType", "Extension", "Size", "Version", "Hash", "TempToken"):
                print(f"{key}: {content_value.get(key)}")

            # Шаг 2: Получение метаданных атрибута для имени (опционально)
            attribute_name = "Доп. файл 3"  # Можно использовать имя из метаданных
            try:
                attr_meta = await client.attributes.get_by_id(ATTRIBUTE_ID)
                if attr_meta and hasattr(attr_meta, "Name"):
                    attribute_name = attr_meta.Name
                    logger.info(f"Имя атрибута получено из метаданных: {attribute_name}")
            except Exception as e:
                logger.warning(f"Не удалось получить метаданные атрибута: {e}. Используется имя по умолчанию.")

            # Шаг 3: Установка файлового атрибута
            logger.info(f"Установка файлового атрибута '{attribute_name}' для объекта {OBJECT_ID}")

            # Формируем данные атрибута с Type=7 (FILE)
            attribute_data = [
                {
                    "Id": ATTRIBUTE_ID,
                    "Name": attribute_name,
                    "Type": WioAttributeType.FILE.value,  # Type = 7 для файлового атрибута
                    "Value": content_value,  # Полный dict с метаданными загруженного файла
                    "Constraints": [],
                }
            ]

            # Устанавливаем атрибут через client.objects.set_attributes()
            success = await client.objects.set_attributes(OBJECT_ID, attribute_data)

            if success:
                logger.info(f"Файловый атрибут '{attribute_name}' успешно установлен для объекта {OBJECT_ID}")
                print("\n✅ Атрибут установлен успешно!")
            else:
                logger.error(f"Не удалось установить атрибут для объекта {OBJECT_ID}")
                print("\n❌ Ошибка при установке атрибута")

        except Exception as e:
            logger.error(f"Ошибка при выполнении операции: {e}", exc_info=True)
            print(f"\n❌ Критическая ошибка: {e}")


if __name__ == "__main__":
    asyncio.run(main())
