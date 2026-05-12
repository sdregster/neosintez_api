import asyncio
import logging
import os
from dotenv import load_dotenv
from uuid import UUID

from neosintez_api.core.client import NeosintezClient
from neosintez_api.core.enums import SearchQueryMode
from neosintez_api.models import SearchCondition, SearchRequest, SearchFilter
from neosintez_api.utils import chunk_list

# Настройка логирования
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ID атрибутов из задачи
SOURCE_ATTR_ID = "9b08f329-1707-e811-810c-9ec54093bb77"
TARGET_ATTR_ID = "da8fdc5f-2407-f111-9209-005056b6948b"

# Фильтры, предоставленные пользователем
USER_FILTERS = [
    {"Type": 5, "Value": "4ae2f84c-2682-eb11-9113-005056b6948b"},
    {"Type": 5, "Value": "d73b9192-06b9-eb11-9115-005056b6948b"},
    {"Type": 5, "Value": "bf9214f7-2e82-eb11-9113-005056b6948b"},
    {"Type": 5, "Value": "507a0276-3082-eb11-9113-005056b6948b"},
    {"Type": 5, "Value": "7e6e4b3b-2f82-eb11-9113-005056b6948b"},
    {"Type": 5, "Value": "0903e553-3082-eb11-9113-005056b6948b"},
    {"Type": 5, "Value": "ec577614-d0bd-eb11-9115-005056b6948b"},
    {"Type": 5, "Value": "7eeca8ed-2f82-eb11-9113-005056b6948b"},
    {"Type": 5, "Value": "555a3d6d-2f82-eb11-9113-005056b6948b"},
    {"Type": 5, "Value": "437cf2e2-4331-ec11-9117-005056b6948b"},
    {"Type": 5, "Value": "a1bfb596-2f82-eb11-9113-005056b6948b"},
    {"Type": 5, "Value": "6cc01bd7-2482-eb11-9113-005056b6948b"},
    {"Type": 5, "Value": "79809e76-2582-eb11-9113-005056b6948b"},
    {"Type": 5, "Value": "f683409c-26c7-eb11-9115-005056b6948b"},
    {"Type": 5, "Value": "980a96c8-2582-eb11-9113-005056b6948b"},
    {"Type": 5, "Value": "dad9b034-3082-eb11-9113-005056b6948b"},
    {"Type": 4, "Value": "b78d067e-1bf2-11ea-90f8-005056b6579f"},
    {"Type": 4, "Value": "9605e4b9-edb2-eb11-9115-005056b6948b"},
    {"Type": 4, "Value": "59c0c005-7a62-ee11-9184-005056b6948b"},
    {"Type": 4, "Value": "27155fd1-5eba-ee11-9196-005056b6948b"}
]

# Условия, предоставленные пользователем
USER_CONDITIONS = [
    {
        "Type": 1,
        "Direction": 0,
        "Operator": 7,  # EXISTS
        "Logic": 0,
        "Attribute": "9b08f329-1707-e811-810c-9ec54093bb77"
    },
    {
        "Type": 1,
        "Direction": 0,
        "Operator": 8,  # NOT EXISTS
        "Logic": 2,     # AND
        "Attribute": "da8fdc5f-2407-f111-9209-005056b6948b"
    }
]

async def update_objects_batch(client: NeosintezClient, objects_to_update: list):
    """Массовое обновление объектов."""
    if not objects_to_update:
        return

    logger.info(f"Начинаем batch-обновление {len(objects_to_update)} объектов...")
    
    # Подготавливаем данные для batch-установки атрибутов
    # Формат: [{"object_id": "uuid", "attributes": [{"Id": "attr_id", "Value": "val"}]}, ...]
    batch_data = []
    for obj in objects_to_update:
        obj_id = obj.Id
        obj_attrs = obj.Attributes or {}
        
        if SOURCE_ATTR_ID in obj_attrs:
            source_val = obj_attrs[SOURCE_ATTR_ID].get("Value")
            if source_val is not None:
                batch_data.append({
                    "object_id": str(obj_id),
                    "attributes": [{"Id": TARGET_ATTR_ID, "Value": source_val, "Type": 6}]
                })

    if not batch_data:
        logger.info("Нет данных для обновления.")
        return

    # Разбиваем на чанки для стабильности, если объектов ОЧЕНЬ много
    chunks = chunk_list(batch_data, 500)
    for i, chunk in enumerate(chunks):
        logger.info(f"Обработка чанка {i+1}/{len(chunks)} ({len(chunk)} объектов)...")
        errors = await client.objects.set_attributes_batch(chunk, max_concurrent=20)
        if errors:
            logger.warning(f"При обновлении чанка возникло {len(errors)} ошибок.")
        
        # Небольшая пауза между чанками
        await asyncio.sleep(1.0)

async def main():
    # Загружаем настройки
    load_dotenv()
    
   # Принудительно задаём стенд, перебивая значения из .env
    os.environ["NEOSINTEZ_BASE_URL"] = "https://operation.irkutskoil.ru"
    # Также бывает старый ключ
    os.environ["NEOSINTEZ_URL"] = "https://operation.irkutskoil.ru"
    
    from neosintez_api.config import NeosintezConfig
    config = NeosintezConfig()
    
    async with NeosintezClient(config) as client:
        # Аутентификация
        try:
            await client.auth()
            logger.info("Успешная аутентификация.")
        except Exception as e:
            logger.error(f"Ошибка аутентификации: {e}")
            return

        # Формируем итоговый запрос
        filters = [SearchFilter(Type=f["Type"], Value=f["Value"]) for f in USER_FILTERS]
        conditions = [
            SearchCondition(
                Type=c["Type"],
                Direction=c["Direction"],
                Operator=c["Operator"],
                Logic=c["Logic"],
                Attribute=UUID(c["Attribute"])
            ) for c in USER_CONDITIONS
        ]

        request = SearchRequest(
            Filters=filters,
            Conditions=conditions,
            Mode=SearchQueryMode.ACTUAL_ONLY
        )

        logger.info("Начинаем поиск и обновление объектов (постранично)...")
        
        limit = 500
        skip = 0
        total_processed = 0
        
        try:
            # Получаем первую страницу для определения общего количества
            first_response = await client.objects.search(request, take=limit, skip=skip)
            total_items = first_response.Total
            logger.info(f"Найдено объектов всего: {total_items}")
            
            if total_items == 0:
                logger.info("Объектов для обновления не найдено.")
                return

            while skip < total_items:
                # Если это не первая итерация, запрашиваем следующую страницу
                if skip > 0:
                    response = await client.objects.search(request, take=limit, skip=skip)
                    results = response.Result
                else:
                    results = first_response.Result
                
                found_objects = [res.obj for res in results]
                
                if found_objects:
                    logger.info(f"Обработка порции объектов {skip} - {skip + len(found_objects)}...")
                    await update_objects_batch(client, found_objects)
                    total_processed += len(found_objects)
                    logger.info(f"Успешно обработано: {total_processed}/{total_items}")
                
                skip += limit
                # Небольшая пауза между запросами страниц для стабильности пула сервера
                await asyncio.sleep(0.1)
                
            logger.info("Вся обработка успешно завершена.")
                
        except Exception as e:
            logger.exception(f"Произошла ошибка при выполнении задачи: {e}")

if __name__ == "__main__":
    if os.name == "nt":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
