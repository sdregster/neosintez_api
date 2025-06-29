"""
Модуль для иерархического импорта данных из Excel в Neosintez.
Автоматически определяет структуру Excel файла и создает объекты по уровням.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
from pydantic import BaseModel

from ..core.client import NeosintezClient
from neosintez_api.core.exceptions import NeosintezAPIError
from .factories import DynamicModelFactory
from .object_service import CreateRequest, ObjectService


logger = logging.getLogger("neosintez_api.excel_importer")


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


class ExcelImporter:
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
        self.factory = DynamicModelFactory(
            name_aliases=self.NAME_COLUMN_NAMES,
            class_name_aliases=self.CLASS_COLUMN_NAMES,
        )
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
                    raise NeosintezAPIError("Не удалось найти обязательные колонки: Уровень, Класс, Имя объекта")

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
            raise NeosintezAPIError(f"Ошибка при анализе Excel файла: {e}") from e

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
        objects_to_create = await self._load_objects_sequentially(excel_path, structure, parent_id, worksheet_name)

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

            # Создаем объекты последовательно по уровням
            created_objects = []
            created_by_level: Dict[int, int] = {}
            errors = []

            # Карта для отслеживания реальных ID по виртуальным
            virtual_to_real_id_map: Dict[str, str] = {parent_id: parent_id}

            # Группируем объекты по уровням
            objects_by_level: Dict[int, List[Dict[str, Any]]] = {}
            for obj in preview.objects_to_create:
                level = obj["level"]
                if level not in objects_by_level:
                    objects_by_level[level] = []
                objects_by_level[level].append(obj)

            # Итерируемся по уровням в отсортированном порядке
            for level in sorted(objects_by_level.keys()):
                logger.info(f"Создание объектов уровня {level}. Количество: {len(objects_by_level[level])}")

                requests_for_level: List[CreateRequest] = []

                # Формируем запросы для текущего уровня
                for obj_data in objects_by_level[level]:
                    try:
                        class_name = obj_data["class_name"]
                        name = obj_data["name"]
                        virtual_parent_id = obj_data.get("parentId")

                        parent_id_for_creation = virtual_to_real_id_map.get(virtual_parent_id)

                        if not parent_id_for_creation:
                            error_msg = (
                                f"Не найден реальный ID родителя для '{name}' (виртуальный ID: {virtual_parent_id})"
                            )
                            logger.error(error_msg)
                            errors.append(error_msg)
                            continue

                        class_info = await self._get_class_by_name(class_name)
                        class_id = class_info["Id"]

                        # Получаем атрибуты класса один раз
                        class_attributes = await self._get_class_attributes(class_id)

                        # Готовим данные для фабрики: имя объекта + его атрибуты
                        user_data_for_factory = {
                            self.NAME_COLUMN_NAMES[0]: name,
                            **obj_data["attributes"],
                        }

                        # Передаем метаданные в фабрику
                        blueprint = await self.factory.create_from_user_data(
                            user_data=user_data_for_factory,
                            class_name=class_name,
                            class_id=class_id,
                            attributes_meta={attr.Name: attr for attr in class_attributes},
                        )

                        requests_for_level.append(
                            CreateRequest(
                                model=blueprint.model_instance,
                                class_id=class_id,
                                class_name=class_name,
                                attributes_meta=blueprint.attributes_meta,
                                parent_id=parent_id_for_creation,
                            )
                        )
                    except Exception as e:
                        error_msg = f"Ошибка подготовки запроса для '{obj_data.get('name')}': {e}"
                        logger.error(error_msg, exc_info=True)
                        errors.append(error_msg)

                if not requests_for_level:
                    logger.warning(f"Нет запросов для создания на уровне {level}. Пропускаем.")
                    continue

                # Выполняем массовое создание для текущего уровня
                bulk_result = await self.object_service.create_many(requests_for_level)

                # Обрабатываем результат
                if bulk_result.errors:
                    errors.extend(bulk_result.errors)

                # Создаем временный словарь для быстрого сопоставления запросов с результатами
                # Ключ - (имя, ID родителя), значение - исходный словарь obj_data
                initial_requests_map = {
                    (req.model.name, str(req.parent_id)): obj_data
                    for req, obj_data in zip(requests_for_level, objects_by_level[level])
                }
                logger.debug(f"Карта запросов для уровня {level}: {list(initial_requests_map.keys())}")

                # Обновляем карту ID и собираем статистику
                for created_model in bulk_result.created_models:
                    # Ищем исходный запрос по имени и ID родителя
                    lookup_key = (created_model.name, str(created_model.parent_id))
                    logger.debug(f"Поиск созданной модели по ключу: {lookup_key}")
                    original_obj_data = initial_requests_map.get(lookup_key)

                    if original_obj_data and created_model.id:
                        virtual_id = original_obj_data.get("id")
                        if virtual_id:
                            virtual_to_real_id_map[virtual_id] = created_model.id

                        # Удаляем найденный ключ, чтобы обработать дубликаты имен, если они есть
                        del initial_requests_map[lookup_key]

                        created_objects.append(
                            {
                                "id": created_model.id,
                                "name": created_model.name,
                                "level": level,
                                **original_obj_data,
                            }
                        )
                        created_by_level[level] = created_by_level.get(level, 0) + 1
                    else:
                        logger.warning(
                            f"Не удалось сопоставить созданный объект '{created_model.name}' с исходными данными (ключ: {lookup_key})."
                        )

                logger.debug(f"Карта ID после уровня {level}: {virtual_to_real_id_map}")

            end_time = datetime.now()
            return ImportResult(
                total_created=len(created_objects),
                created_by_level=created_by_level,
                created_objects=created_objects,
                errors=errors,
                duration_seconds=(end_time - start_time).total_seconds(),
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
        parent_id: str,
        worksheet_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Загружает объекты из Excel и строит иерархическое дерево.
        """
        if worksheet_name is None:
            df = pd.read_excel(
                excel_path, header=None if not self._check_headers(pd.read_excel(excel_path, header=None)) else 0
            )
        else:
            df = pd.read_excel(
                excel_path,
                sheet_name=worksheet_name,
                header=None
                if not self._check_headers(pd.read_excel(excel_path, sheet_name=worksheet_name, header=None))
                else 0,
            )

        data_start_row = 1 if self._check_headers(df) else 0
        if not self._check_headers(df.head(1)):
            df.columns = [f"Column_{i}" for i in range(df.shape[1])]
            data_start_row = 0
            headers = df.columns.tolist()
        else:
            headers = df.columns.tolist()  # Используем реальные заголовки
            df.iloc[:, structure.level_column] = pd.to_numeric(df.iloc[:, structure.level_column], errors="coerce")

        data_df = df.dropna(subset=[df.columns[structure.level_column]]).reset_index(drop=True)

        objects = []
        last_parent_at_level: Dict[int, str] = {0: parent_id}

        for index, row in data_df.iterrows():
            try:
                level_val = row.iloc[structure.level_column]
                if pd.isna(level_val):
                    continue
                level = int(level_val)

                class_name = str(row.iloc[structure.class_column])
                name = str(row.iloc[structure.name_column])

                # Определяем родителя
                current_parent_id = last_parent_at_level.get(level - 1)
                if not current_parent_id:
                    logger.warning(
                        f"Не найден родитель для уровня {level} в строке {index + data_start_row}. "
                        f"Пропускаем объект '{name}'."
                    )
                    continue

                attributes = {}
                for col_idx, attr_name in structure.attribute_columns.items():
                    attr_value = row.iloc[col_idx]
                    if pd.notna(attr_value) and str(attr_value).strip():
                        attributes[attr_name] = attr_value

                # Виртуальный ID для построения дерева
                virtual_id = f"virtual::{name}::{index}"

                obj_data = {
                    "level": level,
                    "class_name": class_name,
                    "name": name,
                    "attributes": attributes,
                    "parentId": current_parent_id,
                    "id": virtual_id,  # Присваиваем временный ID
                    "row_index": index + data_start_row,
                }
                objects.append(obj_data)

                # Обновляем последнего родителя на текущем уровне
                last_parent_at_level[level] = virtual_id

                # Сбрасываем дочерние уровни, чтобы избежать неправильной привязки
                # при возврате на более высокий уровень (например, с 3 на 2)
                keys_to_delete = [k for k in last_parent_at_level if k > level]
                for k in keys_to_delete:
                    del last_parent_at_level[k]

            except (ValueError, IndexError) as e:
                logger.error(f"Ошибка парсинга строки {index + data_start_row}: {e}. Cтрока: {row.to_dict()}")

        return objects

    async def _validate_objects(self, objects_to_create: List[Dict[str, Any]]) -> List[str]:
        """Проверяет корректность данных для создания объектов."""
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
            # Используем get_classes_by_name, который возвращает список
            classes_found = await self.client.classes.get_classes_by_name(class_name)

            # Ищем точное совпадение имени, нечувствительное к регистру
            class_info = next((cls for cls in classes_found if cls["name"].lower() == class_name.lower()), None)

            if class_info:
                # В `class_info` у нас {'id': '...', 'name': '...'}
                # Для единообразия с другими частями системы, преобразуем к {'Id': '...', 'Name': '...'}
                standardized_class_info = {"Id": class_info["id"], "Name": class_info["name"]}
                self.classes_cache[class_name] = standardized_class_info
            else:
                raise NeosintezAPIError(f"Класс '{class_name}' не найден")

        return self.classes_cache[class_name]

    async def _get_class_attributes(self, class_id: str) -> List[Any]:
        """Получает атрибуты класса по ID с кэшированием."""
        if class_id not in self.class_attributes_cache:
            attributes = await self.client.classes.get_attributes(class_id)
            self.class_attributes_cache[class_id] = attributes
        return self.class_attributes_cache[class_id]
