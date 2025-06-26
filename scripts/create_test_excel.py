"""
Скрипт для создания тестового Excel файла для импорта.
"""

import os

import pandas as pd


# Создаем директорию data, если она не существует
os.makedirs("data", exist_ok=True)

# Создаем DataFrame с тестовыми данными
data = [["Уровень", "Класс", "Имя объекта"], [1, "Папка", "Тестовая папка"]]

# Создаем DataFrame
df = pd.DataFrame(data)

# Сохраняем в Excel
output_path = os.path.join("data", "simple_import.xlsx")
df.to_excel(output_path, index=False, header=False)

print(f"Тестовый файл создан: {output_path}")

# Создаем еще один тестовый файл с двумя папками
data_extended = [
    ["Уровень", "Класс", "Имя объекта"],
    [1, "Папка", "Родительская папка"],
    [2, "Папка", "Вложенная папка"],
]

# Создаем DataFrame
df_extended = pd.DataFrame(data_extended)

# Сохраняем в Excel
output_path_extended = os.path.join("data", "two_folders.xlsx")
df_extended.to_excel(output_path_extended, index=False, header=False)

print(f"Файл с двумя папками создан: {output_path_extended}")

# Создаем файл с атрибутами
data_with_attributes = [
    ["Уровень", "Класс", "Имя объекта", "Описание", "Статус", "Дата"],
    [
        1,
        "Папка",
        "Папка с атрибутами",
        "Тестовая папка с атрибутами",
        "Активный",
        "2023-06-25",
    ],
    [
        2,
        "Папка",
        "Вложенная папка с атрибутами",
        "Описание вложенной папки",
        "В работе",
        "2023-06-26",
    ],
]

# Создаем DataFrame
df_with_attributes = pd.DataFrame(data_with_attributes)

# Сохраняем в Excel
output_path_with_attributes = os.path.join("data", "with_attributes.xlsx")
df_with_attributes.to_excel(output_path_with_attributes, index=False, header=False)

print(f"Файл с атрибутами создан: {output_path_with_attributes}")
