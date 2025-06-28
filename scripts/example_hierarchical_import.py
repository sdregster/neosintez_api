"""
Тестовый скрипт для демонстрации работы HierarchicalExcelImporter
с использованием существующего Excel-файла.
"""

import asyncio
import logging
import os
import traceback

import pandas as pd
from neosintez_api.config import NeosintezConfig
from neosintez_api.core.client import NeosintezClient
from neosintez_api.services.excel_importer import ExcelImporter

# Настройка логирования для вывода детальной информации
logging.basicConfig(level=logging.INFO)
logging.getLogger("neosintez_api").setLevel(logging.INFO)


async def main():
    """
    Основной сценарий:
    1.  Инициализация клиента и импортера.
    2.  Анализ структуры файла.
    3.  Предварительный просмотр импорта.
    4.  Выполнение импорта.
    5.  Очистка.
    """
    settings = NeosintezConfig()
    client = NeosintezClient(settings)
    importer = ExcelImporter(client)

    # Путь к файлу для импорта
    test_excel_path = os.path.join("data", "test_import.xlsx")
    created_objects = []

    if not os.path.exists(test_excel_path):
        print(f"Файл для импорта не найден по пути: {test_excel_path}")
        print(
            "Пожалуйста, убедитесь, что файл существует и содержит данные для импорта."
        )
        return

    try:
        # 1. Анализ структуры
        print("--- Этап 1: Анализ структуры Excel ---")
        structure = await importer.analyze_structure(test_excel_path)
        print(structure.model_dump_json(indent=2))
        print("-" * 30)

        # 2. Предварительный просмотр
        print("--- Этап 2: Предварительный просмотр импорта ---")
        preview = await importer.preview_import(
            test_excel_path, parent_id=settings.test_folder_id
        )
        print(f"Найдено объектов для создания: {preview.estimated_objects}")
        print("Ошибки валидации:", "Отсутствуют" if not preview.validation_errors else "")
        for err in preview.validation_errors:
            print(f"  - {err}")

        print("Объекты для создания (виртуальное дерево):")
        # Распечатаем дерево в читаемом виде
        for obj in preview.objects_to_create:
            indent = "  " * (obj["level"] - 1)
            print(
                f"{indent}- {obj['name']} "
                f"(Класс: {obj['class_name']}, "
                f"Родитель: {obj.get('parentId')})"
            )
        
        print("-" * 30)

        if preview.validation_errors:
            print("Импорт прерван из-за ошибок валидации.")
            return

        # 3. Выполнение импорта
        print("--- Этап 3: Выполнение импорта ---")
        result = await importer.import_from_excel(
            test_excel_path, parent_id=settings.test_folder_id
        )
        print(f"Импорт завершен за {result.duration_seconds:.2f} сек.")
        print(f"Всего создано объектов: {result.total_created}")
        print("Создано по уровням:", result.created_by_level)
        print("Ошибки:", "Отсутствуют" if not result.errors else "")
        for err in result.errors:
            print(f"  - {err}")
        print("\nСозданные объекты:")
        for obj in result.created_objects:
            created_objects.append(obj)
            print(f"  - ID: {obj['id']}, Имя: {obj['name']}, Уровень: {obj['level']}")

        print("-" * 30)
        print(
            f"Проверьте созданную иерархию в Неосинтез в папке с ID: {settings.test_folder_id}"
        )

    except Exception as e:
        print(f"\nКритическая ошибка при выполнении: {e}")
        traceback.print_exc()

    finally:
        # 4. Очистка
        await client.close()
        print("\nСоединение с клиентом закрыто.")
        # TODO: Добавить опциональное удаление созданных объектов


if __name__ == "__main__":
    asyncio.run(main()) 