import asyncio
import logging
import os
from dotenv import load_dotenv

from neosintez_api.core.client import NeosintezClient
from neosintez_api.core.enums import SearchConditionType, SearchOperatorType, SearchLogicType, SearchDirectionType, SearchQueryMode
from neosintez_api.models import SearchCondition, SearchRequest
from neosintez_api.services import ClassService, ObjectSearchService

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ID атрибутов из задачи
SOURCE_ATTR_ID = "9b08f329-1707-e811-810c-9ec54093bb77"
TARGET_ATTR_ID = "da8fdc5f-2407-f111-9209-005056b6948b"

# Классы для обработки
TARGET_CLASSES = [
    "Датчики_", 
    "ЗРА_", 
    "Кабеленесущие конструкции_", 
    "Капитальное здание_", 
    "Оборудование вспомогательное_", 
    "Оборудование емкостное_", 
    "Оборудование основное_",  
    "Оборудование электрической части_", 
    "СДТ_",  
    "Строение_", 
    "Трубопроводы_", 
    "Элемент несущий_", 
    "Элементы АС_", 
    "элементы ГП_", 
    "Элементы ОВиК_", 
    "Элементы электрической части_"
]

# Узлы (ЯНГКМ, Усть-Кут, МНГКМ, ИНМ)
TARGET_ANCESTOR_IDS = [
    "b78d067e-1bf2-11ea-90f8-005056b6579f",
    "9605e4b9-edb2-eb11-9115-005056b6948b",
    "59c0c005-7a62-ee11-9184-005056b6948b",
    "27155fd1-5eba-ee11-9196-005056b6948b"
]

async def process_objects_in_ancestor(client: NeosintezClient, ancestor_id: str):
    logger.info(f"Начинаем обработку узла: {ancestor_id}")
    search_service = ObjectSearchService(client)
    class_service = ClassService(client)
    
    success_count = 0
    error_count = 0
    skip_count = 0

    # Обрабатываем каждый класс отдельно
    for cls_name in TARGET_CLASSES:
        logger.info(f"  -> Ищем объекты класса '{cls_name}' в узле {ancestor_id}...")
        
        try:
            # Проверяем, существует ли класс
            found_classes = await class_service.find_by_name(cls_name)
            exact_matches = [c for c in found_classes if c.Name.lower() == cls_name.lower()]
            if not exact_matches:
                logger.warning(f"  Класс '{cls_name}' не найден в системе, пропускаем.")
                continue

            query = search_service.query()
            query.with_class_name(cls_name)
            
            # Добавляем условие поиска по предку
            ancestor_condition = SearchCondition(
                Type=SearchConditionType.ANCESTORS,
                Value=ancestor_id,
                Operator=SearchOperatorType.EQUALS,
                Logic=SearchLogicType.NONE,
                Direction=SearchDirectionType.NONE
            )
            query._conditions.append(ancestor_condition)

            # ОПТИМИЗАЦИЯ: запрашиваем только те объекты, у которых УЖЕ есть исходное "Наименование"
            query.with_attribute(SOURCE_ATTR_ID, "", SearchOperatorType.EXISTS)

            # Подготавливаем поисковый запрос
            final_filters = await query._prepare_filters()
            final_conditions = await query._prepare_conditions()
            request = SearchRequest(
                Filters=final_filters,
                Conditions=final_conditions,
                Mode=SearchQueryMode.ACTUAL_ONLY,
            )

            # ПАГИНАЦИЯ ВРУЧНУЮ (по 50 объектов), чтобы не положить сервер и не выжрать память
            take = 100
            skip = 0
            while True:
                response = await client.objects.search(request, take=take, skip=skip)
                page_objects = [res.obj for res in response.Result]
                
                if not page_objects:
                    break
                    
                logger.info(f"    Получена страница {skip//take + 1} (skip={skip}). Объектов на странице: {len(page_objects)}")
                
                for obj in page_objects:
                    try:
                        obj_attrs = obj.Attributes or {}
                        
                        if SOURCE_ATTR_ID in obj_attrs:
                            source_val = obj_attrs[SOURCE_ATTR_ID].get("Value")
                            target_val = obj_attrs.get(TARGET_ATTR_ID, {}).get("Value")

                            # Обновляем только если есть что обновлять и оно отличается
                            if source_val is not None:
                                if str(target_val) == str(source_val):
                                    skip_count += 1
                                else:
                                    update_data = [{"Id": TARGET_ATTR_ID, "Value": source_val, "Type": 6}]
                                    await client.objects.set_attributes(obj.Id, update_data)
                                    success_count += 1
                                    logger.debug(f"Обновлен объект: {obj.Name} ({obj.Id})")
                            else:
                                skip_count += 1
                        else:
                            skip_count += 1
                            
                    except Exception as e:
                        logger.error(f"Ошибка обновления объекта {obj.Id} ({obj.Name}): {e}")
                        error_count += 1
                        
                    # ПАУЗА после каждого объекта (0.5 сек.) -> 2 запроса в секунду максимум
                    # await asyncio.sleep(0.1)
                    
                skip += take
                
                # ПАУЗА между страницами (чтобы база отдышалась)
                await asyncio.sleep(0.2)

        except Exception as e:
            logger.error(f"  Ошибка при обработке класса '{cls_name}' в узле {ancestor_id}: {e}")

    logger.info(f"Завершена обработка узла {ancestor_id}. Успешно: {success_count}, Пропущено: {skip_count}, Ошибок: {error_count}")


async def main():
    # Принудительно задаём стенд, перебивая значения из .env
    os.environ["NEOSINTEZ_BASE_URL"] = "https://operation.irkutskoil.ru"
    # Также бывает старый ключ
    os.environ["NEOSINTEZ_URL"] = "https://operation.irkutskoil.ru"
    
    load_dotenv()
    
    # Дополнительно передаем в конфиг
    from neosintez_api.config import NeosintezConfig
    config = NeosintezConfig(base_url="https://operation.irkutskoil.ru")
    
    async with NeosintezClient(config) as client:
        # Аутентификация
        try:
            await client.auth()
        except Exception as e:
            logger.error(f"Ошибка аутентификации: {e}")
            return

        for ancestor_id in TARGET_ANCESTOR_IDS:
            await process_objects_in_ancestor(client, ancestor_id)


if __name__ == "__main__":
    if os.name == "nt":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
