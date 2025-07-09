import asyncio
import logging
import os

from neosintez_api.core.client import NeosintezClient
from neosintez_api.services.excel_importer import ExcelImporter


# --- Конфигурация ---
# Настройка логирования для подробного вывода
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# EXCEL_FILE_PATH = "data/hierarchical_import_example.xlsx"
# EXCEL_FILE_PATH = "data/Neosintez_Template_06-13 Сети канализации (смета к договору).xlsx"
EXCEL_FILE_PATH = "data/huge_file.xlsx"
# PARENT_OBJECT_ID = settings.test_folder_id
PARENT_OBJECT_ID = "001847f9-f044-f011-91e3-005056b6948b"


# --- Функции для вывода результатов ---


def print_preview_results(preview):
    """Красиво печатает результаты предварительного просмотра."""
    print("\n--- Результаты предварительного просмотра импорта ---")
    if not preview:
        print("Не удалось получить предварительный просмотр.")
        return

    print("\n[Структура файла]")
    print(f"  - Всего строк для анализа: {preview.structure.total_rows}")
    print(f"  - Максимальная вложенность: {preview.structure.max_level}")
    print(f"  - Найденные классы: {preview.structure.classes_found}")
    print(f"  - Колонка 'Уровень': {preview.structure.level_column}")
    print(f"  - Колонка 'Класс': {preview.structure.class_column}")
    print(f"  - Колонка 'Имя объекта': {preview.structure.name_column}")
    print(f"  - Колонки атрибутов: {len(preview.structure.attribute_columns)} шт.")

    print("\n[Объекты для создания]")
    print(f"  - Предполагаемое количество объектов: {preview.estimated_objects}")
    for i, obj in enumerate(preview.objects_to_create[:5]):  # Показываем первые 5 для примера
        print(f"    - Уровень {obj['level']}: {obj['name']} (Класс: {obj['class_name']})")
    if len(preview.objects_to_create) > 5:
        print("    - ... и другие.")

    print("\n[Ошибки валидации]")
    if preview.validation_errors:
        for error in preview.validation_errors:
            print(f"  - [!] {error}")
    else:
        print("  - Ошибок валидации не найдено. Можно приступать к импорту.")
    print("--------------------------------------------------")


def print_import_results(result):
    """Красиво печатает результаты импорта."""
    print("\n--- Результаты импорта ---")
    if not result:
        print("Не удалось получить результаты импорта.")
        return

    print(f"\n- Длительность выполнения: {result.duration_seconds:.2f} сек.")
    print(f"- Всего создано объектов: {result.total_created}")

    print("\n[Создано по уровням]")
    if result.created_by_level:
        for level, count in sorted(result.created_by_level.items()):
            print(f"  - Уровень {level}: {count} шт.")
    else:
        print("  - Объекты не были созданы.")

    print("\n[Ошибки импорта]")
    if result.errors:
        for error in result.errors:
            print(f"  - [!] {error}")
    else:
        print("  - Ошибок при импорте не возникло.")
    print("--------------------------------------------------")


async def main():
    """Основная функция для запуска отладочного импорта."""

    if PARENT_OBJECT_ID == "ID-вашего-родительского-объекта":
        logging.warning("Пожалуйста, укажите реальный PARENT_OBJECT_ID в скрипте.")
        return

    if not os.path.exists(EXCEL_FILE_PATH):
        logging.error(f"Файл не найден по пути: {EXCEL_FILE_PATH}")
        logging.error("Пожалуйста, создайте файл 'data/hierarchical_import_example.xlsx' или укажите правильный путь.")
        return

    client = NeosintezClient()
    try:
        importer = ExcelImporter(client)

        # --- Шаг 1: Предварительный просмотр ---
        logging.info(f"Запуск предварительного просмотра для файла: {EXCEL_FILE_PATH}")
        preview = await importer.preview_import(EXCEL_FILE_PATH, PARENT_OBJECT_ID)
        print_preview_results(preview)

        if preview.validation_errors:
            logging.error("Обнаружены ошибки валидации. Импорт не может быть продолжен.")
            return

        # --- Шаг 2: Выполнение импорта ---
        # user_input = input("\nПредварительный просмотр завершен. Начать импорт? (y/n): ")
        # if user_input.lower() != "y":
        #     print("Импорт отменен пользователем.")
        #     return

        logging.info("Запуск импорта...")
        result = await importer.import_from_excel(EXCEL_FILE_PATH, PARENT_OBJECT_ID)
        print_import_results(result)

    except Exception as e:
        logging.error(f"Критическая ошибка: {e}", exc_info=True)
    finally:
        await client.close()
        logging.info("Соединение с клиентом закрыто.")


if __name__ == "__main__":
    asyncio.run(main())
