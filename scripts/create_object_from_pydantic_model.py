import asyncio
import logging
import sys
from typing import Any, Dict

from dotenv import load_dotenv
from pydantic import BaseModel, Field

from neosintez_api.client import NeosintezClient
from neosintez_api.config import load_settings


# Загрузка переменных окружения из .env файла
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,  # Меняем на DEBUG для большей информативности
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("neosintez_create_object")


# ────────────────────────────
#  1. Pydantic-модель пользователя
# ────────────────────────────
class SomeRandomModel(BaseModel):
    __class_name__ = "Папка МВЗ"

    Name: str
    МВЗ: str = Field(alias="МВЗ")  # alias оставляем «как есть», чтобы не терялась кириллица


# ────────────────────────────
#  2. Вспомогательные функции
# ────────────────────────────
# Глобальный кэш для метаданных сущностей
ENTITY_CACHE: Dict[str, Dict] = {}


async def get_entity_meta(client: NeosintezClient, class_name: str) -> Dict[str, Any]:
    """
    Получает метаданные класса по имени, используя кэширование.

    Args:
        client: Клиент API Neosintez
        class_name: Имя класса для поиска

    Returns:
        Dict[str, Any]: Метаданные класса с атрибутами
    """
    global ENTITY_CACHE

    # Если класс уже в кэше, возвращаем его
    if class_name in ENTITY_CACHE:
        logger.debug(f"Используем кэшированные метаданные класса '{class_name}'")
        return ENTITY_CACHE[class_name]

    logger.info(f"Загрузка метаданных класса '{class_name}' из API...")

    try:
        # Получаем классы вместе с атрибутами одним запросом
        logger.info("Запрашиваем классы вместе с атрибутами...")
        all_classes_with_attrs = await client.classes.get_all_with_attributes()
        logger.info(f"Получено {len(all_classes_with_attrs)} классов с атрибутами")

        # Ищем нужный класс по имени
        target_class = None
        for cls in all_classes_with_attrs:
            if cls.get("Name") == class_name:
                target_class = cls
                break

        if not target_class:
            logger.warning(f"Класс '{class_name}' не найден в списке классов с атрибутами")
            # Пробуем стандартный метод
            logger.info("Пробуем получить классы стандартным методом...")
            classes = await client.classes.get_all()
            logger.info(f"Получено {len(classes)} классов из API")

            # Ищем нужный класс по имени
            for cls in classes:
                if cls.Name == class_name:
                    target_class_obj = cls
                    target_class = target_class_obj.model_dump()
                    break

            if not target_class:
                raise ValueError(f"Класс '{class_name}' не найден в списке классов API Neosintez")

            logger.info(f"Найден класс '{class_name}' (ID: {target_class['Id']})")

            # Получаем атрибуты отдельно
            attributes = await client.classes.get_attributes(target_class["Id"])
            logger.info(f"Получено {len(attributes)} атрибутов для класса '{class_name}'")

            if len(attributes) == 0:
                logger.warning(f"Внимание: класс '{class_name}' не имеет атрибутов!")

            # Собираем информацию в словарь
            target_class["Attributes"] = [attr.model_dump() for attr in attributes]
        else:
            logger.info(f"Найден класс '{class_name}' (ID: {target_class['Id']}) с атрибутами")

            # Превращаем атрибуты из словаря {id: data} в список атрибутов для совместимости
            attributes_list = []
            if target_class.get("Attributes"):
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
                        logger.error(f"Ошибка при обработке атрибута {attr_id}: {e!s}")

            target_class["Attributes"] = attributes_list
            logger.info(f"Обработано {len(attributes_list)} атрибутов для класса '{class_name}'")

        # Сохраняем класс в кэше
        ENTITY_CACHE[class_name] = target_class

    except Exception as e:
        logger.error(f"Ошибка при получении метаданных класса '{class_name}': {e!s}")
        raise

    return ENTITY_CACHE[class_name]


def build_attribute_body(attr_meta: Dict[str, Any], value: Any) -> Dict[str, Any]:
    """
    Превращает «сырое» значение из модели в тело атрибута WioObjectAttribute.

    Args:
        attr_meta: Метаданные атрибута
        value: Значение атрибута

    Returns:
        Dict[str, Any]: Тело атрибута для API запроса
    """
    # Импортируем функции из utils
    from neosintez_api.utils import build_attribute_body as utils_build_attribute_body

    # Используем функцию build_attribute_body из utils
    try:
        return utils_build_attribute_body(attr_meta, value)
    except Exception as e:
        logger.warning(f"Ошибка при создании тела атрибута: {e!s}. Используем обычную версию.")

        # Используем обычную версию функции как запасной вариант
        return {
            "Name": attr_meta["Name"],
            "Id": attr_meta["Id"],
            "Type": attr_meta["Type"],
            "Value": value,
        }


# ────────────────────────────
#  3. Основная процедура
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

    object_name = model.Name

    # 2) Создаём объект (Name уходит прямо в WioObjectNode)
    create_payload = {
        "Name": object_name,
        "Entity": {
            "Id": str(class_id),
            "Name": entity["Name"],
        },  # Преобразуем UUID в строку
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

    # 5) Читаем объект назад для верификации
    logger.info("Проверка созданного объекта...")
    created_obj = await client.objects.get_by_id(object_id)

    if created_obj.Name != object_name:
        logger.warning(f"Имя объекта '{created_obj.Name}' не совпадает с ожидаемым '{object_name}'")

    # Проверяем каждый атрибут
    all_verified = True
    for field_name, field_value in model.__dict__.items():
        if field_name == "Name" or field_value is None:
            continue

        if field_name in attr_by_name:
            attr_meta = attr_by_name[field_name]
            attr_id = attr_meta["Id"]

            try:
                attr_value = await client.attributes.get_value(object_id, attr_id)

                if attr_value == field_value:
                    logger.info(f"Атрибут {field_name} успешно установлен: {attr_value}")
                else:
                    logger.warning(f"Атрибут {field_name} имеет значение '{attr_value}', ожидалось: '{field_value}'")
                    all_verified = False
            except Exception as e:
                logger.error(f"Ошибка при проверке атрибута {field_name}: {e!s}")
                all_verified = False

    if all_verified:
        logger.info("Все атрибуты успешно проверены и установлены")
    else:
        logger.warning("Не все атрибуты установлены корректно!")

    return object_id


# ────────────────────────────
#  4. Пример вызова
# ────────────────────────────
async def main():
    """
    Пример использования функции создания объекта из модели.
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

                # Создаем модель объекта
                instance = SomeRandomModel(Name="Тестовая МВЗ-папка", МВЗ="0001")
                logger.info(f"Подготовлена модель {instance.__class_name__}: {instance.Name}")

                # Создаем объект
                logger.info("Начинаем процесс создания объекта...")
                object_id = await create_object_from_model(client, instance, parent_id)
                logger.info(f"✓ Объект успешно создан: {object_id}")

                # Проверяем созданный объект
                logger.info("Проверка созданного объекта...")
                created_obj = await client.objects.get_by_id(object_id)
                logger.info(f"Объект подтверждён: {created_obj.Name} (ID: {created_obj.Id})")

                return object_id

            except Exception as e:
                logger.error(f"Ошибка при создании объекта: {e!s}", exc_info=True)
                return None
    except Exception as e:
        logger.error(f"Критическая ошибка при инициализации: {e!s}", exc_info=True)
        return None


if __name__ == "__main__":
    try:
        # Запускаем основную функцию
        result = asyncio.run(main())

        # Проверяем результат
        if result:
            logger.info(f"Скрипт успешно выполнен. Создан объект с ID: {result}")
            sys.exit(0)
        else:
            logger.error("Скрипт выполнен с ошибкой. Объект не был создан.")
            sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Прервано пользователем")
        sys.exit(130)
    except Exception as e:
        logger.critical(f"Критическая ошибка: {e!s}", exc_info=True)
        sys.exit(1)
