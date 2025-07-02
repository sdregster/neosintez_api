"""
Модуль для иерархического импорта данных из Excel в Neosintez.
Автоматически определяет структуру Excel файла и создает объекты по уровням.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
from pydantic import BaseModel

from neosintez_api.core.exceptions import NeosintezAPIError

from ..core.client import NeosintezClient
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
            client=self.client,
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

                # Готовим пачку запросов для текущего уровня
                for obj_data in objects_by_level[level]:
                    try:
                        # Родитель должен быть уже создан на предыдущем шаге
                        virtual_parent_id = obj_data.get("parentId")
                        real_parent_id = virtual_to_real_id_map.get(str(virtual_parent_id))

                        if not real_parent_id:
                            error_msg = f"Не найден реальный ID родителя для '{obj_data['name']}' (виртуальный ID: {obj_data['id']})"
                            logger.error(error_msg)
                            errors.append(error_msg)
                            continue

                        # Готовим данные для фабрики: все, что есть в строке Excel
                        user_data_for_factory = {
                            "Класс": obj_data["class_name"],
                            "Имя объекта": obj_data["name"],
                            **obj_data["attributes"],
                        }

                        # Фабрика сама найдет класс и его атрибуты
                        blueprint = await self.factory.create(user_data_for_factory)

                        # Добавляем запрос в пачку
                        requests_for_level.append(
                            CreateRequest(
                                model=blueprint.model_instance,
                                class_id=blueprint.class_id,
                                class_name=blueprint.class_name,
                                attributes_meta=blueprint.attributes_meta,
                                parent_id=real_parent_id,
                                virtual_id=obj_data["id"],
                            )
                        )
                    except Exception as e:
                        error_msg = f"Ошибка подготовки запроса для '{obj_data.get('name')}': {e}"
                        logger.error(error_msg, exc_info=True)
                        errors.append(error_msg)

                if not requests_for_level:
                    logger.warning(f"Нет валидных запросов для создания на уровне {level}. Пропускаем.")
                    continue

                # Выполняем массовое создание для текущего уровня
                logger.info(f"Отправка {len(requests_for_level)} запросов на создание для уровня {level}...")
                bulk_result = await self.object_service.create_many(requests_for_level)

                # Обрабатываем результат
                if bulk_result.errors:
                    for error in bulk_result.errors:
                        logger.error(f"Ошибка при массовом создании на уровне {level}: {error}")
                        errors.append(error)

                # Сопоставляем созданные объекты с исходными данными по виртуальному ID
                initial_requests_map = {
                    req.virtual_id: obj_data for req, obj_data in zip(requests_for_level, objects_by_level[level])
                }

                for created_model, request in zip(bulk_result.created_models, requests_for_level):
                    original_obj_data = initial_requests_map.get(request.virtual_id)

                    if original_obj_data and created_model._id:
                        virtual_id = original_obj_data.get("id")
                        if virtual_id:
                            virtual_to_real_id_map[virtual_id] = str(created_model._id)

                        created_objects.append(
                            {
                                "id": str(created_model._id),
                                "name": created_model.name,
                                "level": level,
                                "class_name": original_obj_data["class_name"],
                            }
                        )
                        created_by_level[level] = created_by_level.get(level, 0) + 1
                    else:
                        logger.warning(
                            f"Не удалось сопоставить созданный объект '{created_model.name}' "
                            f"с исходными данными (virtual_id: {request.virtual_id})."
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
        try:
            # Читаем Excel, определяя наличие заголовков
            if worksheet_name is None:
                df = pd.read_excel(excel_path, header=None)
            else:
                df = pd.read_excel(excel_path, sheet_name=worksheet_name, header=None)

            has_headers = self._check_headers(df)
            if has_headers:
                # Если заголовки есть, перечитываем с ними
                if worksheet_name is None:
                    df = pd.read_excel(excel_path, header=0)
                else:
                    df = pd.read_excel(excel_path, sheet_name=worksheet_name, header=0)
                data_start_row = 1
            else:
                # Если заголовков нет, используем числовые индексы
                data_start_row = 0

            # Приводим названия колонок к строковому типу для надежности
            df.columns = df.columns.astype(str)
            structure.attribute_columns = {k: str(v) for k, v in structure.attribute_columns.items()}

        except Exception as e:
            logger.error(f"Не удалось прочитать Excel файл: {e}", exc_info=True)
            raise NeosintezAPIError(message=f"Не удалось прочитать Excel файл: {e}") from e

        # Удаляем строки, где отсутствует значение уровня
        level_col_name = df.columns[structure.level_column]
        df = df.dropna(subset=[level_col_name]).reset_index(drop=True)
        df[level_col_name] = pd.to_numeric(df[level_col_name], errors="coerce").astype("Int64")

        objects = []
        last_parent_at_level: Dict[int, str] = {0: parent_id}

        for index, row in df.iterrows():
            try:
                level = int(row.iloc[structure.level_column])
                class_name = str(row.iloc[structure.class_column])
                name = str(row.iloc[structure.name_column])

                # Определяем родителя из карты
                parent_for_current_obj = last_parent_at_level.get(level - 1)
                if parent_for_current_obj is None:
                    logger.warning(
                        f"Строка {index + data_start_row + 1}: Не найден родитель для уровня {level}. "
                        f"Проверьте последовательность уровней. Пропускаем объект '{name}'."
                    )
                    continue

                attributes = {}
                for col_idx, attr_name in structure.attribute_columns.items():
                    # Ищем столбец по индексу, так как имена могут быть ненадёжными
                    if col_idx < len(row):
                        attr_value = row.iloc[col_idx]
                        if pd.notna(attr_value) and str(attr_value).strip():
                            attributes[attr_name] = attr_value

                # Виртуальный ID для построения дерева
                virtual_id = f"virtual::{level}::{index}"

                obj_data = {
                    "level": level,
                    "class_name": class_name,
                    "name": name,
                    "attributes": attributes,
                    "parentId": parent_for_current_obj,
                    "id": virtual_id,  # Присваиваем временный ID
                    "row_index": index + data_start_row + 1,
                }
                objects.append(obj_data)

                # Обновляем последнего родителя на текущем уровне
                last_parent_at_level[level] = virtual_id

                # Сбрасываем дочерние уровни, чтобы избежать неправильной привязки
                keys_to_delete = [k for k in last_parent_at_level if k > level]
                for k in keys_to_delete:
                    del last_parent_at_level[k]

            except (ValueError, IndexError, KeyError) as e:
                logger.error(
                    f"Ошибка парсинга строки {index + data_start_row + 1}: {e}. Cтрока: {row.to_dict()}", exc_info=True
                )

        return objects

    async def _validate_objects(self, objects_to_create: List[Dict[str, Any]]) -> List[str]:
        """Проверяет корректность данных для создания объектов."""
        errors = []
        if not objects_to_create:
            errors.append("Не найдено объектов для импорта.")
            return errors

        # 1. Проверяем, что все указанные классы существуют
        unique_class_names = {obj["class_name"] for obj in objects_to_create}
        logger.info(f"Проверка существования классов: {unique_class_names}")
        for class_name in unique_class_names:
            try:
                # Используем кэширующий метод
                await self._get_class_by_name(class_name)
            except NeosintezAPIError as e:
                error_message = f"Класс '{class_name}' не найден в Неосинтезе. {e}"
                logger.error(error_message)
                errors.append(error_message)

        # # 2. Проверяем наличие дубликатов имен на одном уровне иерархии
        # names_by_parent: Dict[str, set] = {}
        # for obj in objects_to_create:
        #     parent_id = str(obj.get("parentId"))
        #     name = obj.get("name")
        #     row = obj.get("row_index", "N/A")

        #     if parent_id not in names_by_parent:
        #         names_by_parent[parent_id] = set()

        #     if name in names_by_parent[parent_id]:
        #         error_message = (
        #             f"Строка {row}: Обнаружен дубликат имени '{name}' "
        #             f"у одного и того же родителя. "
        #             f"Имена дочерних объектов должны быть уникальны."
        #         )
        #         logger.warning(error_message)
        #         errors.append(error_message)
        #     else:
        #         names_by_parent[parent_id].add(name)

        return errors

    async def _get_class_by_name(self, class_name: str) -> Dict[str, Any]:
        """Получает информацию о классе по имени, используя кеш."""
        if class_name not in self.classes_cache:
            try:
                class_info_list = await self.client.classes.get_classes_by_name(class_name)
                if not class_info_list:
                    raise NeosintezAPIError(f"Класс '{class_name}' не найден.")
                # Ищем точное совпадение
                class_info = next((c for c in class_info_list if c["name"].lower() == class_name.lower()), None)
                if not class_info:
                    raise NeosintezAPIError(
                        f"Найдено несколько классов, похожих на '{class_name}', но точное совпадение отсутствует."
                    )
                self.classes_cache[class_name] = class_info
            except Exception as e:
                logger.error(f"Ошибка при получении класса '{class_name}': {e}")
                raise NeosintezAPIError(f"Ошибка при получении класса '{class_name}': {e}") from e
        return self.classes_cache[class_name]

    async def _get_class_attributes(self, class_id: str) -> List[Any]:
        """Получает атрибуты класса, используя кеш."""
        if class_id not in self.class_attributes_cache:
            try:
                attributes = await self.client.classes.get_attributes(class_id)
                self.class_attributes_cache[class_id] = attributes
            except Exception as e:
                logger.error(f"Ошибка при получении атрибутов для класса ID '{class_id}': {e}")
                raise
        return self.class_attributes_cache[class_id]
