"""
Тестирование получения объектов со стартовой страницы портала через API клиент.
"""

import asyncio
import json
import logging
import re
from typing import Any, Dict, List

from neosintez_api.config import NeosintezConfig
from neosintez_api.core.client import NeosintezClient


# Настройка логирования
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def extract_objects_from_html(html_content: str) -> List[Dict[str, Any]]:
    """
    Извлекает объекты из JavaScript кода в HTML-ответе.

    Args:
        html_content: HTML-содержимое страницы

    Returns:
        List[Dict[str, Any]]: Список объектов с их данными
    """
    try:
        # Ищем JavaScript блок с window.clientContext
        # Сначала ищем начало блока
        script_start = html_content.find("<script>window.clientContext = {")
        if script_start == -1:
            logger.warning("Не найден JavaScript блок с window.clientContext")
            return []

        # Ищем конец блока - следующий </script> после начала
        script_end = html_content.find("</script>", script_start)
        if script_end == -1:
            logger.warning("Не найден конец JavaScript блока")
            return []

        # Извлекаем содержимое между <script> и </script>
        script_content = html_content[script_start:script_end]

        # Извлекаем JSON из window.clientContext = { ... }
        json_start = script_content.find("{")
        if json_start == -1:
            logger.warning("Не найден JSON в JavaScript блоке")
            return []

        js_code = script_content[json_start:]

        # Очищаем JSON от возможных проблем
        # Удаляем комментарии
        js_code = re.sub(r"//.*?\n", "\n", js_code)
        js_code = re.sub(r"/\*.*?\*/", "", js_code, flags=re.DOTALL)

        logger.info(f"Найден JavaScript блок размером: {len(js_code)} символов")

        # Парсим JSON
        client_context = json.loads(js_code)

        # Получаем объекты
        objects_data = client_context.get("objects", {}).get("objects", [])

        logger.info(f"Найдено объектов: {len(objects_data)}")
        return objects_data

    except json.JSONDecodeError as e:
        logger.error(f"Ошибка парсинга JSON: {e}")

        # Попробуем извлечь объекты по частям
        try:
            logger.info("Пытаемся извлечь объекты по частям...")

            # Ищем начало массива объектов
            objects_start = js_code.find('"objects":[')
            if objects_start == -1:
                logger.error("Не найден массив объектов")
                return []

            # Ищем конец массива объектов
            bracket_count = 0
            objects_end = objects_start + 10  # Пропускаем '"objects":['

            for i, char in enumerate(js_code[objects_start + 10 :], objects_start + 10):
                if char == "[":
                    bracket_count += 1
                elif char == "]":
                    bracket_count -= 1
                    if bracket_count == 0:
                        objects_end = i + 1
                        break

            # Извлекаем массив объектов
            objects_array_str = js_code[objects_start + 10 : objects_end]

            # Разбиваем на отдельные объекты
            objects = []
            current_obj = ""
            brace_count = 0

            for char in objects_array_str:
                current_obj += char
                if char == "{":
                    brace_count += 1
                elif char == "}":
                    brace_count -= 1
                    if brace_count == 0:
                        # Завершили объект
                        try:
                            obj = json.loads(current_obj)
                            if "Id" in obj and "Name" in obj:
                                objects.append(obj)
                        except json.JSONDecodeError:
                            pass
                        current_obj = ""

            logger.info(f"Извлечено объектов по частям: {len(objects)}")
            return objects

        except Exception as e2:
            logger.error(f"Ошибка извлечения по частям: {e2}")
            return []

    except Exception as e:
        logger.error(f"Ошибка извлечения объектов: {e}")
        return []


def analyze_html_content(html_content: str) -> None:
    """Анализирует HTML-контент и извлекает полезную информацию."""

    logger.info("🔍 Анализ HTML-контента:")

    # Извлекаем заголовок страницы
    title_match = re.search(r"<title>(.*?)</title>", html_content, re.IGNORECASE)
    if title_match:
        logger.info(f"📄 Заголовок страницы: {title_match.group(1)}")

    # Ищем ссылки на CSS и JS файлы
    css_files = re.findall(r'href="([^"]*\.css[^"]*)"', html_content)
    js_files = re.findall(r'src="([^"]*\.js[^"]*)"', html_content)

    logger.info(f"🎨 Найдено CSS файлов: {len(css_files)}")
    logger.info(f"⚡ Найдено JS файлов: {len(js_files)}")

    # Ищем формы
    forms = re.findall(r"<form[^>]*>", html_content)
    logger.info(f"📝 Найдено форм: {len(forms)}")

    # Ищем ссылки на API endpoints
    api_links = re.findall(r'href="([^"]*api[^"]*)"', html_content, re.IGNORECASE)
    if api_links:
        logger.info(f"🔗 API ссылки: {api_links[:5]}...")  # Показываем первые 5

    # Ищем упоминания Neosintez
    neosintez_matches = re.findall(r"neosintez", html_content, re.IGNORECASE)
    logger.info(f"🏢 Упоминания Neosintez: {len(neosintez_matches)}")

    # Извлекаем объекты из JavaScript кода
    logger.info("\n📋 Извлечение объектов со стартовой страницы:")
    objects = extract_objects_from_html(html_content)

    if objects:
        logger.info(f"✅ Успешно извлечено {len(objects)} объектов:")
        for i, obj in enumerate(objects, 1):
            obj_id = obj.get("Id", "N/A")
            obj_name = obj.get("Name", "N/A")
            has_children = obj.get("HasChildren", False)
            level = obj.get("Level", 0)

            logger.info(f"  {i:2d}. ID: {obj_id}")
            logger.info(f"      Наименование: {obj_name}")
            logger.info(f"      Уровень: {level}, Есть дети: {has_children}")
            logger.info("")
    else:
        logger.warning("⚠️ Объекты не найдены в HTML-контенте")


def save_html_for_analysis(html_content: str, filename: str = "portal_page.html") -> None:
    """
    Сохраняет HTML-контент в файл для анализа.

    Args:
        html_content: HTML-содержимое страницы
        filename: Имя файла для сохранения
    """
    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write(html_content)
        logger.info(f"HTML сохранен в файл: {filename}")
    except Exception as e:
        logger.error(f"Ошибка сохранения HTML: {e}")


def search_for_objects_patterns(html_content: str) -> None:
    """
    Ищет различные паттерны объектов в HTML для диагностики.

    Args:
        html_content: HTML-содержимое страницы
    """
    logger.info("🔍 Диагностика: поиск паттернов объектов в HTML...")

    # Ищем упоминания "objects"
    objects_matches = re.findall(r'"objects"', html_content, re.IGNORECASE)
    logger.info(f"Найдено упоминаний 'objects': {len(objects_matches)}")

    # Ищем упоминания "clientContext"
    client_context_matches = re.findall(r"clientContext", html_content, re.IGNORECASE)
    logger.info(f"Найдено упоминаний 'clientContext': {len(client_context_matches)}")

    # Ищем упоминания "window"
    window_matches = re.findall(r"window\.", html_content, re.IGNORECASE)
    logger.info(f"Найдено упоминаний 'window.': {len(window_matches)}")

    # Ищем JSON-подобные структуры с Id
    id_matches = re.findall(r'"Id"\s*:\s*"[^"]*"', html_content, re.IGNORECASE)
    logger.info(f"Найдено полей 'Id': {len(id_matches)}")

    # Ищем JSON-подобные структуры с Name
    name_matches = re.findall(r'"Name"\s*:\s*"[^"]*"', html_content, re.IGNORECASE)
    logger.info(f"Найдено полей 'Name': {len(name_matches)}")

    # Показываем несколько примеров Id и Name
    if id_matches:
        logger.info("Примеры Id:")
        for i, match in enumerate(id_matches[:5]):
            logger.info(f"  {i + 1}. {match}")

    if name_matches:
        logger.info("Примеры Name:")
        for i, match in enumerate(name_matches[:5]):
            logger.info(f"  {i + 1}. {match}")


def save_objects_to_json(objects: List[Dict[str, Any]], filename: str = "extracted_objects.json") -> None:
    """
    Сохраняет извлеченные объекты в JSON файл.

    Args:
        objects: Список объектов
        filename: Имя файла для сохранения
    """
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(objects, f, ensure_ascii=False, indent=2)
        logger.info(f"Объекты сохранены в файл: {filename}")
    except Exception as e:
        logger.error(f"Ошибка сохранения объектов: {e}")


def print_objects_summary(objects: List[Dict[str, Any]]) -> None:
    """
    Выводит краткую сводку по извлеченным объектам.

    Args:
        objects: Список объектов
    """
    if not objects:
        return

    logger.info("\n📊 Сводка по извлеченным объектам:")
    logger.info(f"   Всего объектов: {len(objects)}")

    # Группируем по уровням
    levels = {}
    for obj in objects:
        level = obj.get("Level", 0)
        levels[level] = levels.get(level, 0) + 1

    logger.info("   Распределение по уровням:")
    for level in sorted(levels.keys()):
        logger.info(f"     Уровень {level}: {levels[level]} объектов")

    # Показываем объекты с детьми
    objects_with_children = [obj for obj in objects if obj.get("HasChildren", False)]
    logger.info(f"   Объектов с детьми: {len(objects_with_children)}")

    # Показываем объекты без детей
    objects_without_children = [obj for obj in objects if not obj.get("HasChildren", False)]
    logger.info(f"   Объектов без детей: {len(objects_without_children)}")


async def test_portal_page():
    """Тестирует получение стартовой страницы портала и извлечение объектов."""

    # Инициализация клиента
    config = NeosintezConfig()
    client = NeosintezClient(config)

    try:
        async with client:
            # Аутентификация
            await client.auth()
            logger.info("Аутентификация успешна")

            # Получаем стартовую страницу
            logger.info("Получаем стартовую страницу портала...")
            html_content = await client.get_portal_page("/")

            logger.info(f"Получен HTML размером: {len(html_content)} символов")
            logger.info(f"Первые 500 символов: {html_content[:500]}...")

            # Проверяем наличие ключевых элементов
            if "neosintez" in html_content.lower():
                logger.info("✅ Страница содержит упоминания Neosintez")
            else:
                logger.warning("⚠️ Страница не содержит ожидаемого контента")

            # Сохраняем HTML для анализа
            save_html_for_analysis(html_content)

            # Диагностика паттернов
            search_for_objects_patterns(html_content)

            # Анализируем HTML-контент и извлекаем объекты
            analyze_html_content(html_content)

            # Извлекаем объекты
            objects = extract_objects_from_html(html_content)

            if objects:
                # Сохраняем объекты в JSON
                save_objects_to_json(objects)

                # Выводим сводку
                print_objects_summary(objects)

                logger.info(f"\n🎉 Успешно извлечено {len(objects)} объектов со стартовой страницы!")
                logger.info("📁 Объекты сохранены в файл extracted_objects.json")
            else:
                logger.warning("⚠️ Объекты не найдены в HTML-контенте")

            # Тестируем получение страницы с параметрами
            logger.info("Тестируем получение страницы с параметрами...")
            try:
                objects_page = await client.get_portal_page("/objects", params={"id": "test"})
                logger.info(f"Получена страница объектов размером: {len(objects_page)} символов")
            except Exception as e:
                logger.warning(f"Не удалось получить страницу объектов: {e}")

            return html_content

    except Exception as e:
        logger.error(f"Ошибка при получении страницы: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(test_portal_page())
