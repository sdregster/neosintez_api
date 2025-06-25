"""
Скрипт, который создаёт объект из Pydantic-модели, а затем получает данные из Неосинтеза и собирает из ответа исходную Pydantic-модель.
"""

import asyncio
import logging
from typing import Any, Dict, List, Type, Optional, TypeVar
from uuid import UUID
from pydantic import BaseModel, Field, create_model

from dotenv import load_dotenv

from neosintez_api.client import NeosintezClient
from neosintez_api.config import load_settings

import sys

# Загрузка переменных окружения из .env файла
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("neosintez_create_read_object")

# Определяем тип для динамических моделей
T = TypeVar("T", bound=BaseModel)


# ────────────────────────────
#  1. Pydantic-модель пользователя
# ────────────────────────────
class SomeRandomModel(BaseModel):
    __class_name__ = "Папка МВЗ"

    Name: str
    МВЗ: str = Field(alias="МВЗ")


# ────────────────────────────
#  2. Вспомогательные функции
# ────────────────────────────
# Глобальный кэш для метаданных сущностей
ENTITY_CACHE: Dict[str, Dict] = {}

async def get_entity_meta(
    client: NeosintezClient,
    class_name: Optional[str] = None,
    class_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Получает метаданные класса по имени или ID, используя кэширование.
    
    Args:
        client: Клиент API Neosintez
        class_name: Имя класса для поиска (опционально, если указан class_id)
        class_id: ID класса для поиска (опционально, если указан class_name)
        
    Returns:
        Dict[str, Any]: Метаданные класса с атрибутами
    """
    global ENTITY_CACHE
    
    # Проверяем наличие хотя бы одного идентификатора
    if class_name is None and class_id is None:
        raise ValueError("Необходимо указать либо class_name, либо class_id")
    
    # Формируем ключ кэша
    cache_key = class_id if class_name is None else class_name
    
    # Если класс уже в кэше, возвращаем его
    if cache_key in ENTITY_CACHE:
        logger.debug(f"Используем кэшированные метаданные класса '{cache_key}'")
        return ENTITY_CACHE[cache_key]
        
    logger.info(f"Загрузка метаданных класса '{cache_key}' из API...")
    
    try:
        # Получаем классы вместе с атрибутами одним запросом (явно указываем only=false)
        logger.info("Запрашиваем классы вместе с атрибутами...")
        endpoint = "api/structure/entities"
        params = {"only": "false"}  # Явно запрашиваем с атрибутами
        
        all_classes_with_attrs = await client._request("GET", endpoint, params=params)
        if isinstance(all_classes_with_attrs, list):
            logger.info(f"Получено {len(all_classes_with_attrs)} классов с атрибутами")
        else:
            logger.warning("Получен неожиданный формат ответа при запросе классов")
            all_classes_with_attrs = []
        
        # Ищем нужный класс по имени или ID
        target_class = None
        for cls in all_classes_with_attrs:
            if (class_name and cls.get("Name") == class_name) or (class_id and str(cls.get("Id")) == str(class_id)):
                target_class = cls
                break
                
        if not target_class:
            logger.warning(f"Класс '{cache_key}' не найден в списке классов с атрибутами")
            # Пробуем стандартный метод
            logger.info("Пробуем получить классы стандартным методом...")
            classes = await client.classes.get_all()
            logger.info(f"Получено {len(classes)} классов из API")
            
            # Ищем нужный класс по имени или ID
            for cls in classes:
                if (class_name and cls.Name == class_name) or (class_id and str(cls.Id) == str(class_id)):
                    target_class_obj = cls
                    target_class = target_class_obj.model_dump()
                    break
            
            if not target_class:
                search_term = class_name if class_name else f"с ID {class_id}"
                raise ValueError(f"Класс {search_term} не найден в списке классов API Neosintez")
                
            logger.info(f"Найден класс '{target_class['Name']}' (ID: {target_class['Id']})")
            
            # Получаем атрибуты отдельно
            attributes = await client.classes.get_attributes(target_class['Id'])
            logger.info(f"Получено {len(attributes)} атрибутов для класса '{target_class['Name']}'")
            
            if len(attributes) == 0:
                logger.warning(f"Внимание: класс '{target_class['Name']}' не имеет атрибутов!")
                
            # Собираем информацию в словарь
            target_class["Attributes"] = [attr.model_dump() for attr in attributes]
        else:
            logger.info(f"Найден класс '{target_class['Name']}' (ID: {target_class['Id']}) с атрибутами")
                
            # Превращаем атрибуты из словаря {id: data} в список атрибутов для совместимости
            attributes_list = []
            if "Attributes" in target_class and target_class["Attributes"]:
                if isinstance(target_class["Attributes"], dict):
                    # Если атрибуты в формате словаря {id: data}
                    for attr_id, attr_data in target_class["Attributes"].items():
                        try:
                            # Создаем базовую структуру атрибута
                            attr_dict = {"Id": attr_id}
                            
                            # Если attr_data - словарь, копируем все его поля
                            if isinstance(attr_data, dict):
                                attr_dict.update(attr_data)
                            # Если attr_data - число (скорее всего тип атрибута), сохраняем как Type
                            elif isinstance(attr_data, (int, float)):
                                attr_dict["Type"] = int(attr_data)
                                attr_dict["Name"] = f"Attribute {attr_id}"
                            
                            # Добавляем в список атрибутов
                            attributes_list.append(attr_dict)
                        except Exception as e:
                            logger.error(f"Ошибка при обработке атрибута {attr_id}: {str(e)}")
                elif isinstance(target_class["Attributes"], list):
                    # Если атрибуты уже в формате списка
                    attributes_list = target_class["Attributes"]
                        
            target_class["Attributes"] = attributes_list
            logger.info(f"Обработано {len(attributes_list)} атрибутов для класса '{target_class['Name']}'")
        
        # Сохраняем класс в кэше
        ENTITY_CACHE[cache_key] = target_class
        # Также сохраняем по другому ключу для удобства поиска
        if class_name is None and "Name" in target_class:
            ENTITY_CACHE[target_class["Name"]] = target_class
        if class_id is None and "Id" in target_class:
            ENTITY_CACHE[str(target_class["Id"])] = target_class
        
    except Exception as e:
        logger.error(f"Ошибка при получении метаданных класса '{cache_key}': {str(e)}")
        raise
        
    return ENTITY_CACHE[cache_key]


def build_attribute_body(attr_meta: Dict[str, Any], value: Any) -> Dict[str, Any]:
    """
    Превращает «сырое» значение из модели в тело атрибута WioObjectAttribute.
    """
    return {
        "Name": attr_meta["Name"],  # Используем реальное имя атрибута
        "Id": attr_meta["Id"],
        "Type": attr_meta["Type"],
        "Value": value,
    }


# ────────────────────────────
#  3. Основная процедура создания объекта
# ────────────────────────────
async def create_object_from_model(
    client: NeosintezClient,
    model: BaseModel,
    parent_id: str,
) -> str:
    """
    Создает объект в Neosintez на основе Pydantic-модели.
    
    Args:
        client: Клиент API Neosintez
        model: Модель данных для создания объекта
        parent_id: ID родительского объекта
        
    Returns:
        str: ID созданного объекта
    """
    # Получаем имя класса из модели
    class_name = getattr(model.__class__, "__class_name__", None)
    if not class_name:
        raise ValueError("В модели не указано имя класса через __class_name__")
    
    logger.info(f"Создание объекта типа '{class_name}'")
    
    # 1) Находим метаданные класса и атрибутов
    entity = await get_entity_meta(client, class_name)
    class_id = entity["Id"]

    # Маппинг «Название атрибута → метаданные»
    attr_by_name = {a["Name"]: a for a in entity["Attributes"]}
    logger.debug(f"Доступные атрибуты класса '{class_name}': {', '.join(attr_by_name.keys())}")
    
    # Если атрибутов нет, выдаем предупреждение
    if not attr_by_name:
        logger.warning(f"Класс '{class_name}' не имеет атрибутов! Будет создан объект без атрибутов.")

    # Получаем имя объекта из модели
    if not hasattr(model, "Name"):
        raise ValueError("В модели нет обязательного поля 'Name'")
        
    object_name = getattr(model, "Name")
    
    # 2) Создаём объект (Name уходит прямо в WioObjectNode)
    create_payload = {
        "Name": object_name,
        "Entity": {"Id": str(class_id), "Name": entity["Name"]},  # Преобразуем UUID в строку
        # Добавляем обязательные поля
        "IsActualVersion": True,
        "Version": 1,
        "VersionTimestamp": "2023-01-01T00:00:00Z",
    }
    
    logger.info(f"Создание объекта '{object_name}' в родительском объекте {parent_id}")
    object_id = await client.objects.create(parent_id, create_payload)
    logger.info(f"Объект успешно создан. ID: {object_id}")

    # 3) Подготавливаем набор атрибутов (кроме Name)
    attributes_body = []
    
    # Итерируем по всем полям модели, кроме Name
    for field_name, field_value in model.__dict__.items():
        if field_name == "Name" or field_value is None:
            # Name уже установлен при создании объекта, None-значения пропускаем
            continue
            
        # Ищем соответствующий атрибут в классе по имени
        if field_name in attr_by_name:
            attr_meta = attr_by_name[field_name]
            attributes_body.append(build_attribute_body(attr_meta, field_value))
            logger.info(f"Подготовлен атрибут {field_name}={field_value}")
        else:
            logger.warning(f"Атрибут '{field_name}' не найден в классе '{class_name}'")

    # 4) Записываем атрибуты, если есть что писать
    if attributes_body:
        logger.info(f"Установка {len(attributes_body)} атрибутов для объекта {object_id}")
        success = await client.attributes.set_attributes(object_id, attributes_body)
        if not success:
            logger.error("Ошибка при установке атрибутов!")
        
    return object_id


# ────────────────────────────
#  4. Получение модели из объекта
# ────────────────────────────
async def read_object_to_model(
    client: NeosintezClient,
    object_id: str,
    model_class: Type[T]
) -> T:
    """
    Создаёт экземпляр модели на основе данных объекта из Neosintez
    
    Args:
        client: Клиент API Neosintez
        object_id: ID объекта
        model_class: Класс модели для создания
        
    Returns:
        Экземпляр указанной модели с данными из объекта
    """
    logger.info(f"Получение данных объекта {object_id} для создания модели")
    
    # 1) Получаем информацию об объекте через API-клиент
    obj = await client.objects.get_by_id(object_id)
    logger.info(f"Получен объект: {obj.Name} (ID класса: {obj.EntityId})")
    
    # Получаем информацию о классе объекта
    entity_id = obj.EntityId
    entity = await get_entity_meta(client, None, entity_id)  # Получим класс по ID
    entity_name = entity["Name"]
    
    logger.info(f"Определен класс объекта: {entity_name}")
    
    # Получаем имя класса из модели
    class_name = getattr(model_class, "__class_name__", None)
    if not class_name:
        raise ValueError("В модели не указано имя класса через __class_name__")
    
    # Убеждаемся, что класс объекта соответствует классу модели
    if entity_name != class_name:
        logger.warning(
            f"Класс объекта '{entity_name}' не соответствует классу модели '{class_name}'. "
            "Это может вызвать проблемы с атрибутами."
        )
    
    # 2) Маппинг атрибутов класса по ID для получения имен атрибутов
    attr_by_id = {str(a["Id"]): a for a in entity["Attributes"]}
    
    # 3) Готовим данные для создания модели
    model_data = {"Name": obj.Name}
    
    # 4) Обрабатываем атрибуты из объекта
    if obj.Attributes and isinstance(obj.Attributes, dict):
        logger.info(f"Найдено {len(obj.Attributes)} атрибутов в объекте")
        
        for attr_id, attr_data in obj.Attributes.items():
            # Получаем метаданные атрибута по ID
            if attr_id in attr_by_id:
                attr_meta = attr_by_id[attr_id]
                attr_name = attr_meta["Name"]
                
                # Извлекаем значение атрибута
                attr_value = attr_data.get("Value") if isinstance(attr_data, dict) else attr_data
                logger.debug(f"Обрабатываем атрибут {attr_name}={attr_value}")
                
                # Сопоставляем с полями модели
                for field_name, field in model_class.__annotations__.items():
                    # Проверяем как обычное имя поля, так и alias
                    field_info = model_class.model_fields.get(field_name)
                    field_alias = field_info.alias if field_info and field_info.alias else field_name
                    
                    if field_name == attr_name or field_alias == attr_name:
                        model_data[field_name] = attr_value
                        logger.info(f"Установлено поле {field_name}={attr_value}")
                        break
                else:
                    logger.debug(f"Атрибут '{attr_name}' не соответствует ни одному полю модели")
            else:
                logger.warning(f"Не найдены метаданные для атрибута с ID {attr_id}")
    else:
        logger.warning(f"В объекте нет атрибутов или они не в ожидаемом формате")
    
    # 5) Создаём модель из собранных данных
    try:
        instance = model_class(**model_data)
        logger.info(f"Создана модель: {instance}")
        return instance
    except Exception as e:
        logger.error(f"Ошибка при создании модели: {str(e)}", exc_info=True)
        raise ValueError(f"Невозможно создать модель из данных объекта: {str(e)}")


# ────────────────────────────
#  5. Пример вызова
# ────────────────────────────
async def main():
    """
    Пример использования функций создания и чтения объекта из/в модель.
    """
    try:
        # Загрузка настроек из переменных окружения
        settings = load_settings()
        logger.info(f"Загружены настройки для подключения к {settings.base_url}")

        async with NeosintezClient(settings) as client:
            try:
                # Аутентификация
                logger.info("Аутентификация в Neosintez API...")
                token = await client.auth()
                logger.info(f"Успешная аутентификация, получен токен: {token[:10]}...")
                
                # ID родительского объекта
                parent_id = "e8ca0ee1-e750-f011-91e5-005056b6948b"  # корневая папка
                logger.info(f"Используем родительский объект: {parent_id}")
                
                # 1) Создаем исходную модель объекта
                original_instance = SomeRandomModel(Name="Тестовая МВЗ-папка", МВЗ="0001")
                logger.info(f"Подготовлена модель {original_instance.__class__.__name__}: {original_instance.Name}")
                
                # 2) Создаем объект в Неосинтезе
                logger.info("Начинаем процесс создания объекта...")
                object_id = await create_object_from_model(client, original_instance, parent_id)
                logger.info(f"✓ Объект успешно создан: {object_id}")
                
                # 3) Получаем данные объекта из Неосинтеза и создаем модель
                logger.info("Получаем данные объекта и восстанавливаем модель...")
                restored_instance = await read_object_to_model(client, object_id, SomeRandomModel)
                logger.info(f"✓ Модель восстановлена из объекта: {restored_instance}")
                
                # 4) Сравниваем исходную модель и восстановленную
                logger.info("Сравнение исходной и восстановленной моделей:")
                original_dict = original_instance.model_dump()
                restored_dict = restored_instance.model_dump()
                
                # Проверяем совпадение всех полей
                is_equal = True
                for field_name in original_dict:
                    if original_dict[field_name] != restored_dict.get(field_name):
                        logger.warning(
                            f"Поле {field_name} не совпадает: "
                            f"исходное={original_dict[field_name]}, "
                            f"восстановленное={restored_dict.get(field_name)}"
                        )
                        is_equal = False
                
                if is_equal:
                    logger.info("✓ Модели полностью совпадают!")
                else:
                    logger.warning("⚠ Модели отличаются!")
                
                return object_id, is_equal
                
            except Exception as e:
                logger.error(f"Ошибка при выполнении операций: {str(e)}", exc_info=True)
                return None, False
    except Exception as e:
        logger.error(f"Критическая ошибка при инициализации: {str(e)}", exc_info=True)
        return None, False


if __name__ == "__main__":
    try:
        # Запускаем основную функцию
        object_id, is_equal = asyncio.run(main())
        
        # Проверяем результат
        if object_id and is_equal:
            logger.info(f"Скрипт успешно выполнен. Объект с ID: {object_id} создан и восстановлен в модель.")
            sys.exit(0)
        elif object_id:
            logger.warning(f"Скрипт выполнен частично. Объект создан (ID: {object_id}), но модели отличаются.")
            sys.exit(1)
        else:
            logger.error("Скрипт выполнен с ошибкой. Объект не был создан или не был восстановлен.")
            sys.exit(2)
    except KeyboardInterrupt:
        logger.info("Прервано пользователем")
        sys.exit(130)
    except Exception as e:
        logger.critical(f"Критическая ошибка: {str(e)}", exc_info=True)
        sys.exit(1)
