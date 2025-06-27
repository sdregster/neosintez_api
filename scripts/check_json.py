"""
Скрипт для проверки и отображения структуры JSON файла с результатами импорта.
"""

import json
from pathlib import Path


def main():
    # Путь к файлу с результатами
    result_path = Path("data/import_test_result.json")

    print(f"Проверка файла: {result_path}")

    # Проверяем существование файла
    if not result_path.exists():
        print(f"Файл '{result_path}' не найден!")
        return

    print(f"Файл существует, размер: {result_path.stat().st_size} байт")

    # Загружаем данные из JSON
    try:
        with open(result_path, encoding="utf-8") as f:
            content = f.read()
            print(f"Прочитано {len(content)} символов")
            data = json.loads(content)
            print("JSON успешно загружен")
    except json.JSONDecodeError as e:
        print(f"Ошибка декодирования JSON: {e}")
        # Выведем часть содержимого файла
        with open(result_path, encoding="utf-8") as f:
            print("Первые 100 символов файла:")
            print(f.read(100))
        return
    except Exception as e:
        print(f"Ошибка при чтении файла: {e}")
        return

    # Проверяем наличие необходимых ключей
    required_keys = ["test_mode", "excel_structure", "objects_hierarchy"]
    for key in required_keys:
        if key not in data:
            print(f"Ключ '{key}' отсутствует в данных")
        else:
            print(f"Ключ '{key}' найден")

    # Выводим основную информацию
    print("\n=== Основная информация ===")
    print(f"Тестовый режим: {data.get('test_mode')}")

    # Информация о структуре Excel
    print("\n=== Структура Excel ===")
    excel_info = data.get("excel_structure", {})
    print(f"Файл: {excel_info.get('file_path')}")
    print(f"Общее количество строк: {excel_info.get('total_rows')}")

    # Найденные колонки
    cols = excel_info.get("columns_found", {})
    level_col = cols.get("level", {})
    class_col = cols.get("class", {})
    name_col = cols.get("name", {})

    print(f"Колонка уровня: {level_col.get('name')} (индекс {level_col.get('index')})")
    print(f"Колонка класса: {class_col.get('name')} (индекс {class_col.get('index')})")
    print(f"Колонка имени: {name_col.get('name')} (индекс {name_col.get('index')})")

    # Примеры данных
    print("\n=== Примеры данных из Excel ===")
    for i, sample in enumerate(excel_info.get("data_sample", [])):
        print(f"Строка {i}: Уровень={sample.get('level')}, Класс={sample.get('class')}, Имя={sample.get('name')}")

    # Информация об иерархии объектов
    print("\n=== Иерархия объектов ===")
    hierarchy = data.get("objects_hierarchy", [])
    print(f"Всего объектов: {len(hierarchy)}")

    for i, obj in enumerate(hierarchy):
        print(f"\nОбъект {i + 1}: {obj.get('name')}")
        print(f"  ID: {obj.get('id')}")
        print(f"  Класс: {obj.get('class_name')} (ID класса: {obj.get('class_id')})")
        print(f"  Родитель: {obj.get('parent_id')}")
        print(f"  Уровень: {obj.get('level')}")

        attrs = obj.get("attributes", {})
        if attrs:
            print(f"  Атрибуты: {attrs}")

    # Сводка по типам объектов
    print("\n=== Сводка по типам объектов ===")
    class_counts = {}
    for obj in hierarchy:
        class_name = obj.get("class_name")
        if class_name:
            if class_name not in class_counts:
                class_counts[class_name] = 0
            class_counts[class_name] += 1

    for class_name, count in class_counts.items():
        print(f"  {class_name}: {count} объектов")


if __name__ == "__main__":
    main()
