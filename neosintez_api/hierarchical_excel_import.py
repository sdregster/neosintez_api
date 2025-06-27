"""
Модуль для иерархического импорта данных из Excel в Neosintez.
Автоматически определяет структуру Excel файла и создает объекты по уровням.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
from pydantic import BaseModel

from .core.client import NeosintezClient
from .core.enums import WioAttributeType
from .exceptions import ApiError
from .services.object_service import ObjectService


logger = logging.getLogger("neosintez_api.hierarchical_excel_import")


class ExcelStructure(BaseModel):
    """Структура Excel файла после анализа"""

    level_column: int
    class_column: int
    name_column: int
    attribute_columns: Dict[int, str]
    total_rows: int
    max_level: int
    classes_found: List[str]


class ImportPreview(BaseModel):
    """Предварительный просмотр импорта"""

    structure: ExcelStructure
    objects_to_create: List[Dict[str, Any]]
    estimated_objects: int
    validation_errors: List[str]


class ImportResult(BaseModel):
    """Результат импорта"""

    total_created: int
    created_by_level: Dict[int, int]
    created_objects: List[Dict[str, Any]]
    errors: List[str]
    duration_seconds: float


class HierarchicalExcelImporter:
    """
    Класс для иерархического импорта данных из Excel в Neosintez.
    Автоматически определяет структуру Excel файла и создает объекты по уровням.
    """

    # Ключевые заголовки колонок для автоопределения
    LEVEL_COLUMN_NAMES = ["Уровень", "Level", "Вложенность"]
    CLASS_COLUMN_NAMES = ["Класс", "Class", "Тип объекта"]
    NAME_COLUMN_NAMES = ["Имя объекта", "Name", "Название объекта", "Наименование"]

    def __init__(self, client: NeosintezClient):
        """
        Инициализация импортера.

        Args:
            client: Инициализированный клиент API Neosintez (должен иметь ресурсы classes и objects)
        """
        self.client = client
        self.object_service = ObjectService(client)
        self.classes_cache: Dict[str, Dict[str, Any]] = {}
        self.class_attributes_cache: Dict[str, List[Any]] = {}

    async def analyze_structure(self, excel_path: str, worksheet_name: Optional[str] = None) -> ExcelStructure:
        """
        Анализирует структуру Excel файла и определяет ключевые колонки.

        Args:
            excel_path: Путь к Excel файлу
            worksheet_name: Имя листа в Excel файле (если None, берется первый лист)

        Returns:
            ExcelStructure: Структура найденного файла

        Raises:
            ApiError: Если файл не может быть прочитан или структура неверна
        """
        logger.info(f"Анализ структуры файла {excel_path}")

        try:
            # Загружаем Excel файл
            if worksheet_name is None:
                df = pd.read_excel(excel_path, header=None)
            else:
                df = pd.read_excel(excel_path, sheet_name=worksheet_name, header=None)

            logger.info(f"Загружено {len(df)} строк данных")

            # Проверяем, содержит ли первая строка заголовки
            has_headers = self._check_headers(df)

            if has_headers:
                headers = [str(cell) for cell in df.iloc[0]]
                data_start_row = 1
            else:
                headers = [f"Column_{i}" for i in range(df.shape[1])]
                data_start_row = 0

            logger.debug(f"Заголовки: {headers}")

            # Определяем ключевые колонки
            level_column = self._find_column(headers, self.LEVEL_COLUMN_NAMES)
            class_column = self._find_column(headers, self.CLASS_COLUMN_NAMES)
            name_column = self._find_column(headers, self.NAME_COLUMN_NAMES)

            if level_column is None or class_column is None or name_column is None:
                if not has_headers:
                    # Предполагаем стандартное расположение колонок
                    level_column = 0
                    class_column = 1
                    name_column = 2
                    logger.info("Используем стандартное расположение колонок: Уровень(0), Класс(1), Имя объекта(2)")
                else:
                    raise ApiError("Не удалось найти обязательные колонки: Уровень, Класс, Имя объекта")

            # Определяем колонки атрибутов (все остальные)
            used_columns = {level_column, class_column, name_column}
            attribute_columns = {}
            name_columns_lower = [name.lower() for name in self.NAME_COLUMN_NAMES]

            for i in range(len(headers)):
                header_value = str(headers[i]).strip()
                # Исключаем любые колонки, похожие на имя, из атрибутов
                if i not in used_columns and header_value.lower() not in name_columns_lower:
                    if header_value != "" and header_value.lower() not in ["nan", "none"]:
                        attribute_columns[i] = header_value

            logger.debug(f"Найдены колонки атрибутов: {attribute_columns}")

            # Анализируем данные
            data_df = df.iloc[data_start_row:]
            max_level = 0
            classes_found = set()

            for _, row in data_df.iterrows():
                if pd.notna(row.iloc[level_column]):
                    level = int(row.iloc[level_column])
                    max_level = max(max_level, level)

                if pd.notna(row.iloc[class_column]):
                    classes_found.add(str(row.iloc[class_column]))

            return ExcelStructure(
                level_column=level_column,
                class_column=class_column,
                name_column=name_column,
                attribute_columns=attribute_columns,
                total_rows=len(data_df),
                max_level=max_level,
                classes_found=list(classes_found),
            )

        except Exception as e:
            logger.error(f"Ошибка при анализе Excel файла: {e}")
            raise ApiError(f"Ошибка при анализе Excel файла: {e}") from e

    async def preview_import(
        self, excel_path: str, parent_id: str, worksheet_name: Optional[str] = None
    ) -> ImportPreview:
        """
        Предварительный просмотр импорта без создания объектов.

        Args:
            excel_path: Путь к Excel файлу
            parent_id: ID родительского объекта
            worksheet_name: Имя листа в Excel файле

        Returns:
            ImportPreview: Предварительный просмотр импорта
        """
        logger.info(f"Предварительный просмотр импорта из {excel_path}")

        # Анализируем структуру
        structure = await self.analyze_structure(excel_path, worksheet_name)

        # Загружаем данные
        objects_to_create = await self._load_objects_sequentially(excel_path, structure, worksheet_name)

        # Подсчитываем объекты
        estimated_objects = len(objects_to_create)

        # Проверяем валидность
        validation_errors = await self._validate_objects(objects_to_create)

        return ImportPreview(
            structure=structure,
            objects_to_create=objects_to_create,
            estimated_objects=estimated_objects,
            validation_errors=validation_errors,
        )

    async def import_from_excel(
        self, excel_path: str, parent_id: str, worksheet_name: Optional[str] = None
    ) -> ImportResult:
        """
        Выполняет импорт данных из Excel файла.

        Args:
            excel_path: Путь к Excel файлу
            parent_id: ID родительского объекта
            worksheet_name: Имя листа в Excel файле

        Returns:
            ImportResult: Результат импорта
        """
        start_time = datetime.now()
        logger.info(f"Начинаем импорт из {excel_path} в объект {parent_id}")

        try:
            # Получаем предварительный просмотр
            preview = await self.preview_import(excel_path, parent_id, worksheet_name)

            if preview.validation_errors:
                logger.error(f"Найдены ошибки валидации: {preview.validation_errors}")
                return ImportResult(
                    total_created=0,
                    created_by_level={},
                    created_objects=[],
                    errors=preview.validation_errors,
                    duration_seconds=(datetime.now() - start_time).total_seconds(),
                )

            # Создаем объекты последовательно
            created_objects = []
            created_by_level: Dict[int, int] = {}
            errors = []
            last_parent_at_level: Dict[int, str] = {}

            if preview.objects_to_create:
                min_level_in_file = min(obj["level"] for obj in preview.objects_to_create)
                last_parent_at_level[min_level_in_file - 1] = parent_id

            for obj_data in preview.objects_to_create:
                try:
                    level = obj_data["level"]
                    current_parent_id = last_parent_at_level.get(level - 1)

                    if not current_parent_id:
                        raise ApiError(f"Не найден родительский объект для уровня {level}")

                    logger.info(
                        f"Создание объекта '{obj_data['name']}' (уровень {level}) с родителем {current_parent_id}"
                    )

                    # Создаем объект
                    object_id = await self._create_object_with_attributes(
                        name=obj_data["name"],
                        class_name=obj_data["class_name"],
                        parent_id=current_parent_id,
                        attributes=obj_data["attributes"],
                    )

                    last_parent_at_level[level] = object_id
                    levels_to_clear = [lvl for lvl in last_parent_at_level if lvl > level]
                    for lvl in levels_to_clear:
                        del last_parent_at_level[lvl]

                    # Сохраняем информацию о созданном объекте
                    created_object = {
                        "id": object_id,
                        "name": obj_data["name"],
                        "class_name": obj_data["class_name"],
                        "level": level,
                        "parent_id": current_parent_id,
                        "attributes": obj_data["attributes"],
                    }
                    created_objects.append(created_object)
                    created_by_level[level] = created_by_level.get(level, 0) + 1

                    logger.debug(f"Создан объект: {obj_data['name']} (ID: {object_id})")

                except Exception as e:
                    error_msg = f"Ошибка при создании объекта '{obj_data['name']}': {e}"
                    logger.error(error_msg)
                    errors.append(error_msg)

            total_created = len(created_objects)
            duration = (datetime.now() - start_time).total_seconds()

            logger.info(f"Импорт завершен: создано {total_created} объектов за {duration:.2f} секунд")

            return ImportResult(
                total_created=total_created,
                created_by_level=created_by_level,
                created_objects=created_objects,
                errors=errors,
                duration_seconds=duration,
            )

        except Exception as e:
            logger.error(f"Критическая ошибка при импорте: {e}")
            return ImportResult(
                total_created=0,
                created_by_level={},
                created_objects=[],
                errors=[f"Критическая ошибка: {e}"],
                duration_seconds=(datetime.now() - start_time).total_seconds(),
            )

    def _check_headers(self, df: pd.DataFrame) -> bool:
        """Проверяет, содержит ли первая строка заголовки."""
        if df is None or len(df) == 0:
            return False

        first_row = df.iloc[0]

        # Проверяем наличие ключевых слов в первой строке
        has_level = any(name.lower() in str(cell).lower() for name in self.LEVEL_COLUMN_NAMES for cell in first_row)
        has_class = any(name.lower() in str(cell).lower() for name in self.CLASS_COLUMN_NAMES for cell in first_row)
        has_name = any(name.lower() in str(cell).lower() for name in self.NAME_COLUMN_NAMES for cell in first_row)

        return has_level and has_class and has_name

    def _find_column(self, headers: List[str], column_names: List[str]) -> Optional[int]:
        """Находит колонку по списку возможных имен."""
        for i, header in enumerate(headers):
            header_lower = str(header).lower()
            for name in column_names:
                if name.lower() in header_lower:
                    return i
        return None

    async def _load_objects_sequentially(
        self,
        excel_path: str,
        structure: ExcelStructure,
        worksheet_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Загружает объекты из Excel в виде последовательного списка, сохраняя порядок."""

        if worksheet_name is None:
            df = pd.read_excel(excel_path, header=None)
        else:
            df = pd.read_excel(excel_path, sheet_name=worksheet_name, header=None)

        has_headers = self._check_headers(df)
        data_start_row = 1 if has_headers else 0
        data_df = df.iloc[data_start_row:]

        objects_list = []

        for _, row in data_df.iterrows():
            if pd.isna(row.iloc[structure.level_column]) or pd.isna(row.iloc[structure.class_column]):
                continue

            level = int(row.iloc[structure.level_column])
            class_name = str(row.iloc[structure.class_column]).strip()
            object_name = ""
            if pd.notna(row.iloc[structure.name_column]):
                object_name = str(row.iloc[structure.name_column]).strip()

            # Если имя объекта пустое, используем имя класса в качестве имени объекта
            if not object_name and class_name:
                logger.debug(f"Имя объекта для класса '{class_name}' не найдено, используется имя класса.")
                object_name = class_name

            if not object_name or not class_name:
                continue

            attributes = {}
            for col_idx, attr_name in structure.attribute_columns.items():
                if col_idx < len(row) and pd.notna(row.iloc[col_idx]):
                    value = row.iloc[col_idx]
                    if str(value).strip():
                        attributes[attr_name] = value

            obj_data = {"name": object_name, "class_name": class_name, "level": level, "attributes": attributes}
            objects_list.append(obj_data)

        return objects_list

    async def _validate_objects(self, objects_to_create: List[Dict[str, Any]]) -> List[str]:
        """Валидирует объекты перед импортом."""
        errors = []

        if not objects_to_create:
            errors.append("Не найдено объектов для импорта")
            return errors

        all_classes = set()
        for obj in objects_to_create:
            all_classes.add(obj["class_name"])

        for class_name in all_classes:
            try:
                await self._get_class_by_name(class_name)
            except Exception as e:
                errors.append(f"Класс '{class_name}' не найден в Neosintez: {e}")

        return errors

    async def _get_class_by_name(self, class_name: str) -> Dict[str, Any]:
        """Получает класс по имени с кэшированием."""
        if class_name not in self.classes_cache:
            class_id = await self.client.classes.find_by_name(class_name)
            if class_id:
                # Сохраняем базовую информацию класса без дополнительных запросов
                self.classes_cache[class_name] = {"Id": class_id, "Name": class_name}
            else:
                raise ApiError(f"Класс '{class_name}' не найден")

        return self.classes_cache[class_name]

    async def _create_object_with_attributes(
        self, name: str, class_name: str, parent_id: str, attributes: Dict[str, Any]
    ) -> str:
        """Создает объект с атрибутами."""

        # Получаем класс
        entity_class = await self._get_class_by_name(class_name)
        class_id = entity_class.get("Id") if isinstance(entity_class, dict) else entity_class.Id

        # Создаем базовый объект БЕЗ поля Parent (parent_id передается в query параметрах)
        object_data = {"Name": name, "Entity": {"Id": class_id, "Name": class_name}}

        response = await self.client.objects.create(object_data, parent_id=parent_id)
        object_id = response.get("Id")

        if not object_id:
            raise ApiError("Не удалось получить ID созданного объекта")

        # Устанавливаем атрибуты, если они есть
        if attributes:
            await self._set_object_attributes(object_id, class_id, attributes)

        return object_id

    async def _set_object_attributes(self, object_id: str, class_id: str, attributes: Dict[str, Any]):
        """Устанавливает атрибуты объекта."""

        # Получаем атрибуты класса
        if class_id not in self.class_attributes_cache:
            self.class_attributes_cache[class_id] = await self.client.classes.get_attributes(class_id)

        class_attributes = self.class_attributes_cache[class_id]

        # Создаем маппинг имя -> атрибут
        attr_by_name = {}
        for attr in class_attributes:
            attr_name = attr.Name if hasattr(attr, "Name") else attr.get("Name", f"Attribute_{attr.Id}")
            attr_by_name[attr_name] = attr

        # Формируем список атрибутов для установки
        attributes_list = []
        for attr_name, value in attributes.items():
            if attr_name in attr_by_name:
                attr_meta = attr_by_name[attr_name]
                attr_id = attr_meta.Id if hasattr(attr_meta, "Id") else attr_meta.get("Id")
                attr_type = attr_meta.Type if hasattr(attr_meta, "Type") else attr_meta.get("Type", 2)

                formatted_value = self._format_attribute_value(value, attr_type)

                logger.debug(
                    f"Подготовка атрибута для объекта {object_id}: "
                    f"Имя='{attr_name}', "
                    f"Тип={attr_type}, "
                    f"Исходное значение='{value}', "
                    f"Форматированное значение='{formatted_value}'"
                )

                if formatted_value is not None:
                    attributes_list.append({"Id": attr_id, "Value": formatted_value})
            else:
                logger.warning(f"Атрибут '{attr_name}' не найден в классе '{class_id}'")

        # Устанавливаем атрибуты
        if attributes_list:
            try:
                await self.client.objects.set_attributes(object_id, attributes_list)
                logger.debug(f"Установлено {len(attributes_list)} атрибутов для объекта {object_id}")
            except ApiError as e:
                logger.error(f"Ошибка при установке атрибутов объекта {object_id}: {e}")
                logger.error(f"Данные запроса: {e.request_data}")
                raise

    def _format_attribute_value(self, value: Any, attr_type: int) -> Any:
        """Форматирует значение атрибута согласно его типу."""
        if pd.isna(value) or (isinstance(value, str) and value.strip() == ""):
            return None

        # Сначала попробуем определить тип самого значения
        original_value = value
        try:
            attr_type_enum = WioAttributeType(attr_type)

            if attr_type_enum == WioAttributeType.NUMBER:
                if isinstance(value, str):
                    value = value.replace(",", ".").replace(" ", "")
                return float(value)

            if attr_type_enum in [WioAttributeType.DATE, WioAttributeType.DATETIME]:
                if isinstance(value, datetime):
                    return value.isoformat()
                # Pandas может парсить числа как даты, что нежелательно в данном случае.
                if isinstance(value, (int, float)):
                    logger.warning(
                        f"Значение '{original_value}' является числом, но тип атрибута - дата ({attr_type}). "
                        f"Значение будет передано как есть."
                    )
                    return original_value
                return pd.to_datetime(value).isoformat()

            if attr_type_enum in [WioAttributeType.STRING, WioAttributeType.TEXT]:
                return str(value)

            if attr_type_enum == WioAttributeType.OBJECT_LINK:
                return str(value)

            # Обработка булева типа из старого кода (Type 4)
            if attr_type == 4:
                if isinstance(value, bool):
                    return value
                return str(value).lower() in ("true", "1", "да", "yes")

            logger.warning(
                f"Неподдерживаемый тип атрибута {attr_type} для значения '{original_value}'. Используется как есть."
            )
            return original_value

        except (ValueError, TypeError) as e:
            logger.warning(
                f"Ошибка форматирования значения '{original_value}' для типа {attr_type}: {e}. "
                f"Значение будет передано как есть."
            )
            return original_value
        except Exception as e:
            logger.warning(
                f"Общая ошибка форматирования значения '{original_value}' для типа {attr_type}: {e}. "
                f"Значение будет передано как есть."
            )
            return original_value
