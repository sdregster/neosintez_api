#!/usr/bin/env python
"""
Скрипт для генерации Pydantic моделей из Swagger спецификации API Неосинтез.

Этот скрипт читает файл swagger.json и генерирует соответствующие Pydantic модели
в директории neosintez_api/core/generated/.
"""

import json
import os
import re
from typing import Any, Dict, List, Set, Tuple, Optional

# Путь к директории проекта
PROJECT_DIR = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
# Путь к файлу swagger.json
SWAGGER_PATH = os.path.join(PROJECT_DIR, "neosintez_api", "swagger.json")
# Путь к директории для генерируемых моделей
OUTPUT_DIR = os.path.join(PROJECT_DIR, "neosintez_api", "core", "generated")
# Имя файла с моделями
MODELS_FILE = "models.py"


def snake_case(name: str) -> str:
    """
    Преобразует строку в snake_case.

    Args:
        name: Строка для преобразования

    Returns:
        str: Строка в формате snake_case
    """
    # Заменяем не-алфавитные символы на подчеркивание
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    s2 = re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()
    # Заменяем все не-алфавитные символы на подчеркивание
    s3 = re.sub(r"[^a-z0-9_]", "_", s2)
    # Убираем повторяющиеся подчеркивания
    s4 = re.sub(r"_+", "_", s3)
    # Убираем подчеркивания в начале и конце
    return s4.strip("_")


def camel_case(snake_str: str) -> str:
    """
    Преобразует строку из snake_case в camelCase.

    Args:
        snake_str: Строка в формате snake_case

    Returns:
        str: Строка в формате camelCase
    """
    components = snake_str.split("_")
    return components[0] + "".join(x.title() for x in components[1:])


def pascal_case(snake_str: str) -> str:
    """
    Преобразует строку из snake_case в PascalCase.

    Args:
        snake_str: Строка в формате snake_case

    Returns:
        str: Строка в формате PascalCase
    """
    return "".join(x.title() for x in snake_str.split("_"))


def read_swagger(swagger_path: str) -> Dict[str, Any]:
    """
    Читает Swagger спецификацию из JSON файла.

    Args:
        swagger_path: Путь к файлу swagger.json

    Returns:
        Dict[str, Any]: Словарь с данными спецификации
    """
    try:
        with open(swagger_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        raise ValueError(f"Ошибка при чтении файла Swagger: {e}")


def get_python_type(schema_type: str, schema_format: Optional[str] = None) -> str:
    """
    Возвращает тип Python, соответствующий типу из Swagger.

    Args:
        schema_type: Тип из Swagger
        schema_format: Формат типа из Swagger

    Returns:
        str: Строка с типом Python
    """
    if schema_type == "string":
        if schema_format == "date-time":
            return "datetime.datetime"
        elif schema_format == "date":
            return "datetime.date"
        elif schema_format == "uuid":
            return "uuid.UUID"
        elif schema_format == "binary":
            return "bytes"
        return "str"
    elif schema_type == "integer":
        if schema_format == "int64":
            return "int"
        return "int"
    elif schema_type == "number":
        if schema_format == "float":
            return "float"
        elif schema_format == "double":
            return "float"
        return "float"
    elif schema_type == "boolean":
        return "bool"
    elif schema_type == "array":
        return "List"  # Тип элементов будет добавлен позже
    elif schema_type == "object":
        return "Dict[str, Any]"
    else:
        return "Any"


def analyze_schema_dependencies(schemas: Dict[str, Any]) -> Dict[str, Set[str]]:
    """
    Анализирует зависимости между схемами.

    Args:
        schemas: Словарь со схемами из Swagger

    Returns:
        Dict[str, Set[str]]: Словарь с зависимостями между схемами
    """
    dependencies: Dict[str, Set[str]] = {}

    for name, schema in schemas.items():
        dependencies[name] = set()

        def find_refs(obj):
            if isinstance(obj, dict):
                if "$ref" in obj and obj["$ref"].startswith("#/components/schemas/"):
                    ref_name = obj["$ref"].split("/")[-1]
                    if ref_name != name:  # Исключаем самоссылки
                        dependencies[name].add(ref_name)
                for value in obj.values():
                    find_refs(value)
            elif isinstance(obj, list):
                for item in obj:
                    find_refs(item)

        find_refs(schema)

    return dependencies


def sort_schemas_by_dependencies(
    schemas: Dict[str, Any], dependencies: Dict[str, Set[str]]
) -> List[str]:
    """
    Сортирует схемы по зависимостям для правильного порядка генерации.

    Args:
        schemas: Словарь со схемами из Swagger
        dependencies: Словарь с зависимостями между схемами

    Returns:
        List[str]: Отсортированный список имен схем
    """
    result = []
    visited = set()

    def visit(name):
        if name in visited:
            return
        visited.add(name)
        for dep in dependencies.get(name, set()):
            if dep in schemas:  # Проверяем, что зависимость существует в схемах
                visit(dep)
        result.append(name)

    for name in schemas:
        visit(name)

    return result


def generate_field_definition(
    name: str, field_schema: Dict[str, Any], required: List[str]
) -> Tuple[str, List[str], List[str]]:
    """
    Генерирует определение поля для Pydantic модели.

    Args:
        name: Имя поля
        field_schema: Схема поля из Swagger
        required: Список обязательных полей

    Returns:
        Tuple[str, List[str], List[str]]: Строка с определением поля, список импортов и список валидаторов
    """
    imports = []
    field_type = None
    field_default = None
    field_description = field_schema.get("description", "")
    validators = []
    field_options = []

    # Обрабатываем различные типы схем
    if "$ref" in field_schema:
        ref = field_schema["$ref"]
        if ref.startswith("#/components/schemas/"):
            field_type = ref.split("/")[-1]
    elif "type" in field_schema:
        schema_type = field_schema["type"]
        schema_format = field_schema.get("format")

        if schema_type == "array":
            items = field_schema.get("items", {})
            if "$ref" in items:
                item_type = items["$ref"].split("/")[-1]
                field_type = f"List[{item_type}]"
                imports.append("List")
            elif "type" in items:
                item_py_type = get_python_type(items["type"], items.get("format"))
                field_type = f"List[{item_py_type}]"
                imports.append("List")
                if "datetime" in item_py_type:
                    imports.append("datetime")
                if "uuid" in item_py_type:
                    imports.append("uuid")
            else:
                field_type = "List[Any]"
                imports.append("List")
                imports.append("Any")
        else:
            field_type = get_python_type(schema_type, schema_format)
            if "datetime" in field_type:
                imports.append("datetime")
            if "uuid" in field_type:
                imports.append("uuid")
    else:
        field_type = "Any"
        imports.append("Any")

    # Проверяем, является ли поле обязательным
    is_required = name in required

    # Если поле не обязательное, добавляем None к возможным типам
    if not is_required:
        field_type = f"Optional[{field_type}]"
        imports.append("Optional")
        field_default = "None"

    # Добавляем различные валидаторы и ограничения
    if "minimum" in field_schema:
        field_options.append(f"ge={field_schema['minimum']}")
    if "maximum" in field_schema:
        field_options.append(f"le={field_schema['maximum']}")
    if "minLength" in field_schema:
        field_options.append(f"min_length={field_schema['minLength']}")
    if "maxLength" in field_schema:
        field_options.append(f"max_length={field_schema['maxLength']}")
    if "pattern" in field_schema:
        pattern = field_schema["pattern"].replace("\\", "\\\\").replace('"', '\\"')
        field_options.append(f'pattern=r"{pattern}"')
    if "enum" in field_schema:
        enum_values = field_schema["enum"]
        enum_vals_str = ", ".join(
            f'"{v}"' if isinstance(v, str) else str(v) for v in enum_values
        )
        validators.append(
            f'@field_validator("{name}")\n    @classmethod\n    def validate_{snake_case(name)}(cls, v):\n        if v is not None and v not in [{enum_vals_str}]:\n            raise ValueError(f"{{v}} не является допустимым значением")\n        return v'
        )
        imports.append("field_validator")

    # Формируем строку определения поля
    field_str = f"{camel_case(name)}: {field_type}"

    # Добавляем опции поля, если они есть
    if field_options or field_default is not None or field_description:
        field_parts = []

        if field_default is not None:
            field_parts.append(f"default={field_default}")

        field_parts.extend(field_options)

        if field_description:
            field_parts.append(f'description="{field_description}"')

        field_str += f" = Field({', '.join(field_parts)})"
        imports.append("Field")

    return field_str, imports, validators


def generate_model(name: str, schema: Dict[str, Any]) -> Tuple[str, List[str]]:
    """
    Генерирует код Pydantic модели из схемы Swagger.

    Args:
        name: Имя модели
        schema: Схема из Swagger

    Returns:
        Tuple[str, List[str]]: Строка с кодом модели и список импортов
    """
    imports = ["BaseModel", "Field"]
    fields = []
    validators = []

    # Получаем описание модели
    description = schema.get("description", f"Модель {name}")

    # Получаем список обязательных полей
    required = schema.get("required", [])

    # Обрабатываем свойства схемы
    properties = schema.get("properties", {})
    for field_name, field_schema in properties.items():
        field_str, field_imports, field_validators = generate_field_definition(
            field_name, field_schema, required
        )
        fields.append(f"    {field_str}")
        imports.extend(field_imports)
        validators.extend(field_validators)

    # Генерируем код модели
    model_code = [f"class {name}(BaseModel):"]
    model_code.append(f'    """{description}"""')
    model_code.append("")

    # Если нет полей, добавляем pass
    if not fields:
        model_code.append("    pass")
    else:
        model_code.extend(fields)

    # Добавляем валидаторы, если они есть
    if validators:
        model_code.append("")
        for validator in validators:
            validator_lines = validator.split("\n")
            for line in validator_lines:
                model_code.append(f"    {line}")

    return "\n".join(model_code), list(set(imports))


def generate_models_file(schemas: Dict[str, Any]) -> Tuple[str, List[str]]:
    """
    Генерирует файл с Pydantic моделями из схем Swagger.

    Args:
        schemas: Словарь со схемами из Swagger

    Returns:
        Tuple[str, List[str]]: Строка с содержимым файла и список имен моделей
    """
    # Анализируем зависимости между схемами
    dependencies = analyze_schema_dependencies(schemas)

    # Сортируем схемы по зависимостям
    sorted_schemas = sort_schemas_by_dependencies(schemas, dependencies)

    # Генерируем код для каждой модели
    imports = set()
    model_code_blocks = []
    model_names = []

    for name in sorted_schemas:
        schema = schemas[name]
        model_code, model_imports = generate_model(name, schema)
        model_code_blocks.append(model_code)
        model_names.append(name)
        imports.update(model_imports)

    # Формируем импорты
    import_lines = [
        '"""',
        "Автоматически сгенерированные модели данных из Swagger спецификации API Неосинтез.",
        "",
        "НЕ РЕДАКТИРОВАТЬ ВРУЧНУЮ!",
        "Этот файл генерируется автоматически из swagger.json.",
        '"""',
        "",
        "from __future__ import annotations",
        "from typing import Any, Dict, List, Optional, Union",
        "from pydantic import BaseModel, Field, field_validator",
    ]

    # Добавляем специфические импорты
    if "datetime" in imports:
        import_lines.append("import datetime")
    if "uuid" in imports:
        import_lines.append("import uuid")

    # Собираем весь код файла
    file_content = "\n".join(import_lines) + "\n\n\n" + "\n\n\n".join(model_code_blocks)

    return file_content, model_names


def update_init_file(model_names: List[str]) -> str:
    """
    Обновляет файл __init__.py с экспортом всех моделей.

    Args:
        model_names: Список имен моделей

    Returns:
        str: Содержимое файла __init__.py
    """
    content = [
        '"""',
        "Автоматически сгенерированные модели данных из Swagger-описания API Неосинтез.",
        "",
        "НЕ РЕДАКТИРОВАТЬ ВРУЧНУЮ!",
        "Этот модуль содержит автоматически сгенерированные Pydantic-модели",
        "на основе Swagger-спецификации API Неосинтез.",
        '"""',
        "",
        "from .models import *",
        "",
        "__all__ = [",
    ]

    # Добавляем имена всех моделей
    for name in model_names:
        content.append(f'    "{name}",')

    content.append("]")

    return "\n".join(content)


def main():
    """
    Основная функция для генерации моделей из Swagger.
    """
    print(f"Чтение Swagger спецификации из {SWAGGER_PATH}...")
    swagger_data = read_swagger(SWAGGER_PATH)

    # Получаем схемы компонентов
    if "components" not in swagger_data or "schemas" not in swagger_data["components"]:
        raise ValueError("В Swagger спецификации отсутствуют компоненты или схемы")

    schemas = swagger_data["components"]["schemas"]
    print(f"Найдено {len(schemas)} схем в спецификации")

    # Генерируем файл с моделями
    print("Генерация моделей...")
    file_content, model_names = generate_models_file(schemas)

    # Создаем директорию для генерируемых файлов, если она не существует
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Записываем файл с моделями
    models_path = os.path.join(OUTPUT_DIR, MODELS_FILE)
    with open(models_path, "w", encoding="utf-8") as f:
        f.write(file_content)
    print(f"Модели сгенерированы и записаны в {models_path}")

    # Обновляем файл __init__.py
    init_content = update_init_file(model_names)
    init_path = os.path.join(OUTPUT_DIR, "__init__.py")
    with open(init_path, "w", encoding="utf-8") as f:
        f.write(init_content)
    print(f"Файл инициализации обновлен: {init_path}")

    print(f"Всего сгенерировано {len(model_names)} моделей")


if __name__ == "__main__":
    main()
