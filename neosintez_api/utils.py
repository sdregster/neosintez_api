"""
Утилиты для работы с API Неосинтез.
"""

import asyncio
import json
import logging
import re
from datetime import date, datetime, time
from decimal import Decimal
from functools import wraps
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Type,
    TypeVar,
    get_args,
    get_origin,
)
from uuid import UUID

import aiohttp

from neosintez_api.core.enums import WioAttributeType
from neosintez_api.core.exceptions import (
    NeosintezConnectionError,
    NeosintezTimeoutError,
    NeosintezValidationError,
)


# Настройка логирования
logger = logging.getLogger("neosintez_api")

T = TypeVar("T")


class CustomJSONEncoder(json.JSONEncoder):
    """
    Кастомный JSON-энкодер для сериализации UUID и datetime.
    """

    def default(self, obj):
        if isinstance(obj, UUID):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


async def retry_async(
    func: Callable[..., T],
    attempts: int = 3,
    delay: int = 1,
    exceptions: List[type] = None,
) -> T:
    """
    Декоратор для повторного выполнения асинхронной функции при возникновении ошибки.

    Args:
        func: Асинхронная функция для выполнения
        attempts: Количество попыток
        delay: Задержка между попытками в секундах
        exceptions: Список исключений, на которые нужно реагировать повторными попытками

    Returns:
        Результат выполнения функции

    Raises:
        Exception: Если все попытки завершились с ошибкой
    """
    if exceptions is None:
        exceptions = [NeosintezConnectionError, NeosintezTimeoutError]

    last_exception = None

    for attempt in range(1, attempts + 1):
        try:
            return await func()
        except tuple(exceptions) as e:
            last_exception = e
            if attempt < attempts:
                logger.warning(
                    f"Попытка {attempt} из {attempts} не удалась. Ошибка: {e!s}. Повтор через {delay} сек..."
                )
                await asyncio.sleep(delay)
            else:
                logger.error(f"Все {attempts} попыток не удались. Последняя ошибка: {e!s}")
                raise
        except Exception as e:
            logger.error(f"Неожиданная ошибка: {e!s}")
            raise

    # Этот код не должен выполняться, но добавлен для типизации
    assert last_exception is not None
    raise last_exception


def retry(
    attempts: int = 3,
    delay: int = 1,
    exceptions: Optional[List[type]] = None,
) -> Callable:
    """
    Декоратор для повторных попыток выполнения асинхронной функции.

    Args:
        attempts: Количество попыток
        delay: Задержка между попытками в секундах
        exceptions: Список исключений, на которые нужно реагировать повторными попытками

    Returns:
        Декорированная функция
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            return await retry_async(
                lambda: func(*args, **kwargs),
                attempts=attempts,
                delay=delay,
                exceptions=exceptions,
            )

        return wrapper

    return decorator


def normalize_dict_keys(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Нормализует ключи словаря, приводя их к camelCase формату.

    Args:
        data: Исходный словарь

    Returns:
        Dict[str, Any]: Словарь с нормализованными ключами
    """
    if not isinstance(data, dict):
        return data

    result = {}
    for key, value in data.items():
        # Приводим ключ к camelCase
        camel_key = key[0].lower() + key[1:] if key else key

        # Рекурсивно обрабатываем вложенные словари
        if isinstance(value, dict):
            result[camel_key] = normalize_dict_keys(value)
        elif isinstance(value, list):
            result[camel_key] = [normalize_dict_keys(i) if isinstance(i, dict) else i for i in value]
        else:
            result[camel_key] = value

    return result


async def parse_error_response(response: aiohttp.ClientResponse) -> Dict[str, Any]:
    """
    Парсит ответ с ошибкой от API и возвращает информацию об ошибке.

    Args:
        response: Объект ответа aiohttp

    Returns:
        Dict[str, Any]: Словарь с информацией об ошибке
    """
    status_code = response.status

    try:
        response_text = await response.text()
        message = response_text
        response_data = None

        # Пытаемся распарсить JSON из тела ответа
        try:
            response_data = json.loads(response_text)
            if isinstance(response_data, dict):
                # Пытаемся извлечь сообщение об ошибке
                if "error" in response_data:
                    message = response_data["error"]
                elif "message" in response_data:
                    message = response_data["message"]
                elif "Message" in response_data:
                    message = response_data["Message"]
        except json.JSONDecodeError:
            pass

        return {"status_code": status_code, "message": message, "data": response_data}
    except Exception as e:
        logger.error(f"Ошибка при парсинге ответа с ошибкой: {e!s}")
        return {
            "status_code": status_code,
            "message": f"Ошибка при парсинге ответа: {e!s}",
            "data": None,
        }


def chunk_list(items: List[Any], size: int) -> List[List[Any]]:
    """
    Разделяет список на части указанного размера.

    Args:
        items: Список для разделения
        size: Размер каждой части

    Returns:
        List[List[Any]]: Список частей исходного списка
    """
    return [items[i : i + size] for i in range(0, len(items), size)]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Маппинг типов атрибутов
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Таблица соответствия типов Python типам атрибутов в API Неосинтеза
PYTHON_TO_WIO_TYPE_MAPPING = {
    # Строковые типы
    str: WioAttributeType.STRING,
    # Числовые типы
    int: WioAttributeType.NUMBER,
    float: WioAttributeType.NUMBER,
    Decimal: WioAttributeType.NUMBER,
    # Временные типы
    datetime: WioAttributeType.DATETIME,
    date: WioAttributeType.DATE,
    time: WioAttributeType.TIME,
    # Логические типы - будут преобразованы в числовые (0/1)
    bool: WioAttributeType.NUMBER,
    # Специальные типы (UUID считаем за строковый тип)
    UUID: WioAttributeType.STRING,
    # Списки и коллекции - по умолчанию обычная коллекция,
    # но нужно проверять дополнительно, если List[UUID] - это ReferenceCollection
    list: WioAttributeType.COLLECTION,
    List: WioAttributeType.COLLECTION,
}


def get_wio_attribute_type(python_type: type) -> WioAttributeType:
    """
    Определяет тип атрибута Неосинтеза на основе типа Python.

    Args:
        python_type: Тип данных Python

    Returns:
        WioAttributeType: Соответствующий тип атрибута для API Неосинтеза

    Raises:
        NeosintezValidationError: Если тип не может быть преобразован
    """
    # Проверяем, является ли тип параметризованным (например, List[str])
    origin = get_origin(python_type)
    args = get_args(python_type)

    # Проверяем случай List[UUID] - это коллекция ссылок на объекты
    if origin is list or origin is List:
        if args and args[0] is UUID:
            return WioAttributeType.REFERENCE_COLLECTION
        return WioAttributeType.COLLECTION

    # Проверяем обычный тип
    if python_type in PYTHON_TO_WIO_TYPE_MAPPING:
        return PYTHON_TO_WIO_TYPE_MAPPING[python_type]

    # Тип не поддерживается
    raise NeosintezValidationError(f"Тип Python '{python_type}' не поддерживается для атрибутов Неосинтеза")


def convert_value_to_wio_format(value: Any, wio_type: WioAttributeType) -> Any:
    """
    Конвертирует Python-значение в формат, понятный API Неосинтеза.

    Args:
        value: Исходное значение
        wio_type: Тип атрибута в API Неосинтеза

    Returns:
        Any: Преобразованное значение

    Raises:
        NeosintezValidationError: Если значение не может быть преобразовано
    """
    # None всегда возвращаем как есть
    if value is None:
        return None

    # Преобразование в зависимости от типа
    try:
        if wio_type == WioAttributeType.STRING:
            # Строковый тип
            if isinstance(value, UUID):
                return str(value)
            return str(value)

        elif wio_type == WioAttributeType.NUMBER:
            # Числовой тип
            if isinstance(value, bool):
                return 1 if value else 0
            return float(value)

        elif wio_type == WioAttributeType.DATE:
            # Тип даты
            if isinstance(value, datetime):
                return value.strftime("%Y-%m-%d")
            if isinstance(value, date):
                return value.strftime("%Y-%m-%d")
            return str(value)

        elif wio_type == WioAttributeType.TIME:
            # Тип времени
            if isinstance(value, datetime):
                return value.strftime("%H:%M:%S")
            if isinstance(value, time):
                return value.strftime("%H:%M:%S")
            return str(value)

        elif wio_type == WioAttributeType.DATETIME:
            # Тип даты и времени
            if isinstance(value, (datetime, date)):
                return value.isoformat()
            return str(value)

        elif wio_type == WioAttributeType.OBJECT_LINK:
            # Ссылка на объект (UUID)
            if isinstance(value, UUID):
                return str(value)
            return str(value)

        elif wio_type in (
            WioAttributeType.COLLECTION,
            WioAttributeType.REFERENCE_COLLECTION,
        ):
            # Коллекция
            if not isinstance(value, list):
                value = [value]

            # Для коллекции ссылок преобразуем все элементы в строки UUID
            if wio_type == WioAttributeType.REFERENCE_COLLECTION:
                return [str(item) if isinstance(item, UUID) else item for item in value]

            return value

        # Пробуем преобразовать в дату/время
        if wio_type == WioAttributeType.DATETIME:
            return str(value.isoformat())
        if wio_type == WioAttributeType.DATE:
            return str(value.date())
        if wio_type == WioAttributeType.TIME:
            return str(value.time())

    except (ValueError, TypeError) as e:
        raise NeosintezValidationError(
            f"Не удалось преобразовать значение '{value}' в тип '{wio_type.as_string}': {e!s}"
        ) from e

    # Для всех остальных типов возвращаем значение как есть
    return value


def format_attribute_value(attr_meta: Dict[str, Any], value: Any) -> Any:
    """
    Форматирует значение атрибута в соответствии с его типом.

    Args:
        attr_meta: Метаданные атрибута
        value: Значение атрибута

    Returns:
        Any: Отформатированное значение
    """
    if value is None:
        return None

    # Получаем тип атрибута
    attr_type = attr_meta.get("Type") if isinstance(attr_meta, dict) else getattr(attr_meta, "Type", None)

    if attr_type is None:
        return value  # Если не удалось определить тип, возвращаем как есть

    try:
        # Преобразуем значение в зависимости от типа атрибута
        if attr_type == WioAttributeType.NUMBER:
            # Целое число
            if isinstance(value, str) and value.strip():
                return int(value)
            return int(value) if value is not None else None
        elif attr_type == WioAttributeType.STRING:
            # Строка
            return str(value) if value is not None else None
        elif attr_type == WioAttributeType.DATE:
            # Дата
            if isinstance(value, datetime):
                return value.date().isoformat()
            return str(value)
        elif attr_type == WioAttributeType.TIME:
            # Время
            if isinstance(value, datetime):
                return value.time().isoformat()
            return str(value)
        elif attr_type == WioAttributeType.DATETIME:
            # Дата и время
            if isinstance(value, datetime):
                return value.isoformat()
            return str(value)
        elif attr_type == WioAttributeType.TEXT:
            # Текст с форматированием
            return str(value) if value is not None else None
        elif attr_type == WioAttributeType.FILE:
            # Файл
            return value
        elif attr_type == WioAttributeType.OBJECT_LINK:
            # Ссылка на другой объект
            return value
        else:
            # Другие типы
            return value
    except (ValueError, TypeError):
        # В случае ошибки преобразования возвращаем исходное значение
        return value


def build_attribute_body(attr_meta: Any, value: Any) -> Dict[str, Any]:
    """
    Создает тело атрибута для API.
    Возвращает словарь с Id, отформатированным Value и правильным Type.
    """
    attr_id = getattr(attr_meta, "Id", None) or (attr_meta.get("Id") if isinstance(attr_meta, dict) else None)
    if not attr_id:
        raise ValueError("Метаданные атрибута должны содержать 'Id'.")

    api_attr_type = getattr(attr_meta, "Type", None) or (attr_meta.get("Type") if isinstance(attr_meta, dict) else None)
    if api_attr_type is None:
        raise ValueError(f"Метаданные для атрибута '{attr_id}' не содержат 'Type'.")

    formatted_value: Any

    if api_attr_type == 8:  # Ссылка на объект
        if isinstance(value, dict) and "Id" in value:
            formatted_value = value  # Передаем словарь как есть
        else:
            raise TypeError(f"Для ссылочного атрибута {attr_id} ожидался dict с ключом 'Id', но получен {type(value)}")
    elif value is None:
        formatted_value = None
    elif isinstance(value, (str, int, float, bool)):
        formatted_value = value
    elif isinstance(value, (datetime, date, UUID)):
        formatted_value = str(value.isoformat() if isinstance(value, (datetime, date)) else value)
    elif isinstance(value, dict):
        formatted_value = value
    else:
        formatted_value = str(value)

    return {"Id": str(attr_id), "Value": formatted_value, "Type": api_attr_type}


def get_field_external_name(model_class: type, field_name: str) -> str:
    """
    Получает имя поля для внешнего API на основе модели Pydantic.
    Учитывает alias, если он задан через Field(alias=...).

    Args:
        model_class: Класс модели Pydantic
        field_name: Имя поля в Python-коде

    Returns:
        str: Имя поля для API (alias или оригинальное имя)
    """
    # Получаем информацию о поле из модели
    field_info = model_class.__fields__.get(field_name)
    if field_info and field_info.alias != field_name:
        return field_info.alias
    return field_name


def generate_field_name(display_name: str) -> str:
    """Генерирует валидное имя поля Python из отображаемого имени на русском."""
    trans_map = {
        "а": "a",
        "б": "b",
        "в": "v",
        "г": "g",
        "д": "d",
        "е": "e",
        "ё": "yo",
        "ж": "zh",
        "з": "z",
        "и": "i",
        "й": "y",
        "к": "k",
        "л": "l",
        "м": "m",
        "н": "n",
        "о": "o",
        "п": "p",
        "р": "r",
        "с": "s",
        "т": "t",
        "у": "u",
        "ф": "f",
        "х": "kh",
        "ц": "ts",
        "ч": "ch",
        "ш": "sh",
        "щ": "shch",
        "ъ": "",
        "ы": "y",
        "ь": "",
        "э": "e",
        "ю": "yu",
        "я": "ya",
        " ": "_",
    }
    lowered_name = display_name.lower()
    latin_name = "".join([trans_map.get(char, char) for char in lowered_name])
    latin_name = re.sub(r"[^\w_]", "", latin_name)
    latin_name = re.sub(r"__+", "_", latin_name)
    return latin_name.strip("_")


def neosintez_type_to_python_type(neo_type: int) -> Type:
    """Конвертирует числовой тип атрибута из Неосинтеза в тип Python."""
    if neo_type == 1:
        # Используем float, так как он может принимать и int, и float.
        # Это решает проблему, когда API возвращает число с плавающей точкой.
        return float
    elif neo_type == 2:
        return str
    else:
        return Any
