#!/usr/bin/env python
"""
Скрипт для изучения структуры API Neosintez.

Этот скрипт помогает исследовать структуру ответов API для различных методов,
что позволяет адаптировать модели данных и методы работы с API.
"""

import asyncio
import json
import logging
import pprint
from pathlib import Path
from typing import Dict, Any, Tuple
from uuid import UUID

# Загрузка переменных окружения из .env файла
from dotenv import load_dotenv

from neosintez_api.client import NeosintezClient
from neosintez_api.config import load_settings
from neosintez_api.exceptions import NeosintezAuthError, NeosintezConnectionError

load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("neosintez_api_explorer")


class UUIDEncoder(json.JSONEncoder):
    """
    JSON-encoder для сериализации UUID.
    """

    def default(self, obj):
        if isinstance(obj, UUID):
            # Если объект - UUID, преобразуем его в строку
            return str(obj)
        return super().default(obj)


async def make_api_request(
    endpoint: str, method: str = "GET", params: Dict = None, data: Any = None
) -> Tuple[int, Any]:
    """
    Выполняет запрос к API и возвращает код статуса и результат.

    Args:
        endpoint: Конечная точка API
        method: HTTP метод (GET, POST, PUT, DELETE)
        params: Параметры запроса
        data: Данные для отправки в теле запроса

    Returns:
        Tuple[int, Any]: Код статуса и результат запроса
    """
    settings = load_settings()
    logger.info(f"Загружены настройки для подключения к {settings.base_url}")

    async with NeosintezClient(settings) as client:
        try:
            # Аутентификация
            logger.info("Попытка аутентификации...")
            token = await client.auth()
            logger.info(f"Получен токен: {token[:10]}...")

            # Выполнение запроса
            logger.info(f"Выполнение запроса {method} {endpoint}")
            status_code, response = await client._request_raw(
                method, endpoint, params=params, data=data
            )

            logger.info(f"Получен ответ с кодом: {status_code}")
            return status_code, response

        except NeosintezAuthError as e:
            logger.error(f"Ошибка аутентификации: {str(e)}")
            return 401, {"error": str(e)}
        except NeosintezConnectionError as e:
            logger.error(f"Ошибка соединения: {str(e)}")
            return 503, {"error": str(e)}
        except Exception as e:
            logger.error(f"Неожиданная ошибка: {str(e)}")
            return 500, {"error": str(e)}


async def explore_attributes_api() -> Dict[str, Any]:
    """
    Изучает структуру API для работы с атрибутами.

    Returns:
        Dict с результатами исследования
    """
    results = {}

    # 1. Получаем список всех атрибутов
    status, response = await make_api_request("api/attributes")
    results["all_attributes"] = {
        "status": status,
        "sample": response[:2] if isinstance(response, list) else response,
        "count": len(response) if isinstance(response, list) else 0,
    }

    # Сохраняем образец ответа в файл
    output_dir = Path("data")
    output_dir.mkdir(exist_ok=True)

    with open(output_dir / "attributes_sample.json", "w", encoding="utf-8") as f:
        if isinstance(response, list) and response:
            json.dump(response[:5], f, ensure_ascii=False, indent=2, cls=UUIDEncoder)
        else:
            json.dump(response, f, ensure_ascii=False, indent=2, cls=UUIDEncoder)

    # 2. Получаем подробную информацию об атрибуте (если есть хотя бы один)
    if isinstance(response, list) and response:
        attr_id = response[0].get("Id", "")
        if attr_id:
            status, attr_detail = await make_api_request(f"api/attributes/{attr_id}")
            results["attribute_detail"] = {"status": status, "data": attr_detail}

            with open(
                output_dir / "attribute_detail_sample.json", "w", encoding="utf-8"
            ) as f:
                json.dump(attr_detail, f, ensure_ascii=False, indent=2, cls=UUIDEncoder)

    # 3. Получаем атрибуты для класса объекта
    # Сначала получаем список классов
    status, classes = await make_api_request("api/structure/entities")

    if isinstance(classes, list) and classes:
        class_id = classes[0].get("Id", "")
        if class_id:
            status, class_attrs = await make_api_request(
                f"api/structure/entities/{class_id}/attributes"
            )
            results["class_attributes"] = {
                "status": status,
                "sample": class_attrs[:2]
                if isinstance(class_attrs, list)
                else class_attrs,
                "count": len(class_attrs) if isinstance(class_attrs, list) else 0,
            }

            with open(
                output_dir / "class_attributes_sample.json", "w", encoding="utf-8"
            ) as f:
                if isinstance(class_attrs, list) and class_attrs:
                    json.dump(
                        class_attrs[:5],
                        f,
                        ensure_ascii=False,
                        indent=2,
                        cls=UUIDEncoder,
                    )
                else:
                    json.dump(
                        class_attrs, f, ensure_ascii=False, indent=2, cls=UUIDEncoder
                    )

    return results


async def explore_objects_api(class_id: str = None) -> Dict[str, Any]:
    """
    Изучает структуру API для работы с объектами.

    Args:
        class_id: ID класса для фильтрации объектов (если None, берется первый найденный)

    Returns:
        Dict с результатами исследования
    """
    results = {}

    # Если класс не указан, берем первый из списка
    if not class_id:
        status, classes = await make_api_request("api/structure/entities")

        if isinstance(classes, list) and classes:
            class_id = classes[0].get("Id", "")
            if not class_id:
                logger.error("Не удалось получить ID класса")
                return {"error": "Не удалось получить ID класса"}

    # 1. Получаем список объектов по классу
    search_data = {
        "Filters": [
            {
                "Type": 5,  # ByClass
                "Value": class_id,
            }
        ],
        "Take": 10,
        "Skip": 0,
    }

    status, objects = await make_api_request(
        "api/objects/search", method="POST", data=search_data
    )
    results["objects_search"] = {
        "status": status,
        "sample": objects,
        "count": objects.get("Total", 0) if isinstance(objects, dict) else 0,
    }

    # Сохраняем образец ответа в файл
    output_dir = Path("data")
    output_dir.mkdir(exist_ok=True)

    with open(output_dir / "objects_search_sample.json", "w", encoding="utf-8") as f:
        json.dump(objects, f, ensure_ascii=False, indent=2, cls=UUIDEncoder)

    # 2. Если найдены объекты, получаем подробную информацию о первом
    if isinstance(objects, dict) and "Result" in objects and objects["Result"]:
        obj_id = objects["Result"][0].get("Id", "")
        if obj_id:
            status, obj_detail = await make_api_request(f"api/objects/{obj_id}")
            results["object_detail"] = {"status": status, "data": obj_detail}

            with open(
                output_dir / "object_detail_sample.json", "w", encoding="utf-8"
            ) as f:
                json.dump(obj_detail, f, ensure_ascii=False, indent=2, cls=UUIDEncoder)

            # 3. Получаем значения атрибутов объекта
            status, obj_attrs = await make_api_request(
                f"api/objects/{obj_id}/attributes"
            )
            results["object_attributes"] = {"status": status, "data": obj_attrs}

            with open(
                output_dir / "object_attributes_sample.json", "w", encoding="utf-8"
            ) as f:
                json.dump(obj_attrs, f, ensure_ascii=False, indent=2, cls=UUIDEncoder)

    return results


async def main():
    """
    Основная функция для запуска исследования API.
    """
    import argparse

    parser = argparse.ArgumentParser(description="Исследование структуры API Neosintez")
    parser.add_argument(
        "--class-id", type=str, help="ID класса для исследования объектов"
    )
    args = parser.parse_args()

    # Создаем директорию для результатов
    output_dir = Path("data/api_exploration")
    output_dir.mkdir(parents=True, exist_ok=True)

    print("\n====== Исследование API Neosintez ======\n")

    # Изучаем API атрибутов
    print("1. Исследование API атрибутов\n")
    attr_results = await explore_attributes_api()

    # Сохраняем результаты в файл
    with open(output_dir / "attributes_api_results.json", "w", encoding="utf-8") as f:
        json.dump(attr_results, f, ensure_ascii=False, indent=2, cls=UUIDEncoder)

    # Выводим результаты
    print("Результаты исследования API атрибутов:")
    pprint.pprint(attr_results)

    # Изучаем API объектов
    print("\n2. Исследование API объектов\n")
    obj_results = await explore_objects_api(args.class_id)

    # Сохраняем результаты в файл
    with open(output_dir / "objects_api_results.json", "w", encoding="utf-8") as f:
        json.dump(obj_results, f, ensure_ascii=False, indent=2, cls=UUIDEncoder)

    # Выводим результаты
    print("Результаты исследования API объектов:")
    pprint.pprint(obj_results)

    print("\n====== Исследование API завершено ======\n")
    print(f"Результаты сохранены в директории: {output_dir}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Прервано пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {str(e)}")
