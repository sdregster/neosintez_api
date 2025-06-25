#!/usr/bin/env python
"""
Скрипт для создания Excel шаблона для импорта вложенных объектов разных классов.
"""

import json
import logging
import os
from typing import Dict, List, Any, Set

import pandas as pd
from dotenv import load_dotenv

load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("neosintez_import_template")

# Константы для структуры шаблона
LEVEL_COL = "Уровень"
CLASS_COL = "Класс"
NAME_COL = "Имя объекта"
DESCRIPTION_COL = "Описание"

# Типы данных для Excel
COLUMN_TYPES = {
    "String": str,
    "Number": float,
    "DateTime": "datetime64[ns]",
    "Boolean": bool,
}


def load_classes_info() -> Dict[str, Any]:
    """
    Загружает информацию о классах и их атрибутах из JSON файла.
    
    Returns:
        Словарь с информацией о классах
    """
    try:
        classes_file = os.path.join("data", "classes_for_import.json")
        if not os.path.exists(classes_file):
            logger.error(f"Файл с информацией о классах не найден: {classes_file}")
            return {"classes": []}
            
        with open(classes_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        logger.info(f"Загружена информация о {len(data.get('classes', []))} классах")
        return data
    except Exception as e:
        logger.error(f"Ошибка при загрузке информации о классах: {str(e)}")
        return {"classes": []}
        

def create_template(classes_info: Dict[str, Any], output_file: str = "nested_import_template.xlsx") -> str:
    """
    Создает Excel шаблон на основе информации о классах и их атрибутах.
    
    Args:
        classes_info: Словарь с информацией о классах
        output_file: Имя выходного файла
        
    Returns:
        Путь к созданному файлу
    """
    # Проверяем, есть ли информация о классах
    if not classes_info.get("classes", []):
        logger.error("Нет данных о классах для создания шаблона")
        return ""
        
    # Создаем каркас таблицы
    columns = [LEVEL_COL, CLASS_COL, NAME_COL, DESCRIPTION_COL]
    
    # Собираем информацию о всех атрибутах
    all_attributes: Dict[str, Dict[str, Any]] = {}
    class_names = []
    
    for cls in classes_info.get("classes", []):
        class_name = cls.get("name", "")
        class_names.append(class_name)
        
        for attr in cls.get("attributes", []):
            attr_name = attr.get("name", "")
            if attr_name not in all_attributes and attr_name not in columns:
                all_attributes[attr_name] = {
                    "id": attr.get("id", ""),
                    "type": attr.get("type", "String"),
                    "description": attr.get("description", ""),
                }
                columns.append(attr_name)
                
    # Создаем DataFrame с заголовками
    df = pd.DataFrame(columns=columns)
    
    # Заполняем примерами для каждого класса
    row_data = []
    
    # Добавляем примеры вложенной структуры для каждого класса
    level = 1
    for i, class_name in enumerate(class_names):
        # Корневой объект класса
        row_data.append({
            LEVEL_COL: level,
            CLASS_COL: class_name,
            NAME_COL: f"Корневой объект {class_name}",
            DESCRIPTION_COL: f"Описание для {class_name}"
        })
        
        # Вложенный объект того же класса
        row_data.append({
            LEVEL_COL: level + 1,
            CLASS_COL: class_name,
            NAME_COL: f"Вложенный объект {class_name}",
            DESCRIPTION_COL: f"Описание для вложенного {class_name}"
        })
        
        # Если есть следующий класс, добавляем его как вложенный на уровень ниже
        if i < len(class_names) - 1:
            next_class = class_names[i + 1]
            row_data.append({
                LEVEL_COL: level + 2,
                CLASS_COL: next_class,
                NAME_COL: f"Вложенный объект {next_class}",
                DESCRIPTION_COL: f"Описание для вложенного {next_class}"
            })
    
    # Добавляем данные в DataFrame
    df = pd.DataFrame(row_data)
    
    # Добавляем пустые колонки для всех атрибутов
    for attr_name in all_attributes.keys():
        if attr_name not in df.columns:
            df[attr_name] = ""
    
    # Обеспечиваем нужный порядок колонок
    df = df[columns]
    
    # Сохраняем в Excel
    os.makedirs("data", exist_ok=True)
    output_path = os.path.join("data", output_file)
    
    # Сохраняем с форматированием
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Импорт", index=False)
        
        # Настраиваем ширину колонок
        worksheet = writer.sheets["Импорт"]
        for i, column in enumerate(df.columns):
            max_length = max(
                df[column].astype(str).map(len).max(),
                len(str(column))
            )
            worksheet.column_dimensions[chr(65 + i)].width = max_length + 4
    
    logger.info(f"Шаблон для импорта создан: {output_path}")
    return output_path
    

def main():
    """
    Основная функция скрипта.
    """
    import argparse
    
    parser = argparse.ArgumentParser(description="Создание Excel шаблона для импорта вложенных объектов")
    parser.add_argument("--output", default="nested_import_template.xlsx", 
                       help="Имя выходного файла")
    args = parser.parse_args()
    
    # Загружаем информацию о классах
    classes_info = load_classes_info()
    
    # Создаем шаблон
    output_file = create_template(classes_info, args.output)
    
    if output_file:
        print(f"\nШаблон успешно создан: {output_file}")
    else:
        print("\nНе удалось создать шаблон. Проверьте логи.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Прервано пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {str(e)}")
        import traceback
        logger.error(f"Трассировка: {traceback.format_exc()}") 