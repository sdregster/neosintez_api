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
from .class_service import ClassService
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
    validation_warnings: List[str]


class ImportResult(BaseModel):
    """Результат импорта"""

    total_created: int
    created_by_level: Dict[int, int]
    created_objects: List[Dict[str, Any]]
    errors: List[str]
    warnings: List[str]
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
        self.class_service = ClassService(client)  # Используем сервисный слой с кэшем
        self.factory = DynamicModelFactory(
            client=self.client,
            class_service=self.class_service,  # Передаем общий экземпляр
            name_aliases=self.NAME_COLUMN_NAMES,
            class_name_aliases=self.CLASS_COLUMN_NAMES,
        )

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
                    try:
                        level = int(row.iloc[level_column])
                        max_level = max(max_level, level)
                    except (ValueError, TypeError):
                        # Игнорируем строки, где уровень не является числом
                        pass

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
            logger.error(f"Ошибка при анализе Excel файла: {e}", exc_info=True)
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

        # Загружаем данные и собираем ошибки загрузки
        objects_to_create, loading_errors = await self._load_objects_sequentially(
            excel_path, structure, parent_id, worksheet_name
        )

        # Подсчитываем объекты
        estimated_objects = len(objects_to_create)

        # Проверяем валидность
        validation_errors, validation_warnings = await self._validate_objects(objects_to_create)
        validation_errors.extend(loading_errors)  # Добавляем ошибки, найденные при загрузке

        return ImportPreview(
            structure=structure,
            objects_to_create=objects_to_create,
            estimated_objects=estimated_objects,
            validation_errors=validation_errors,
            validation_warnings=validation_warnings,
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
                    warnings=preview.validation_warnings,
                    duration_seconds=(datetime.now() - start_time).total_seconds(),
                )

            # Создаем объекты последовательно по уровням
            created_objects = []
            created_by_level: Dict[int, int] = {}
            errors = []
            warnings = list(preview.validation_warnings)  # Начинаем с предупреждений из preview

            # Новый сет для отслеживания ID объектов, которые не удалось создать или были пропущены
            failed_or_skipped_virtual_ids = set()

            # Карта для отслеживания реальных ID по виртуальным
            virtual_to_real_id_map: Dict[str, str] = {parent_id: parent_id}

            # Группируем объекты по уровням
            objects_by_level: Dict[int, List[Dict[str, Any]]] = {}
            for obj in preview.objects_to_create:
                level = obj["level"]
                if level not in objects_by_level:
                    objects_by_level[level] = []
                objects_by_level[level].append(obj)

            # Создаем объекты, начиная с верхнего уровня
            for level in sorted(objects_by_level.keys()):
                logger.info(f"Создание объектов на уровне {level}")
                requests_to_process = []
                batch_virtual_ids = set()

                for obj_data in objects_by_level[level]:
                    virtual_id = obj_data["virtual_id"]
                    virtual_parent_id = obj_data["parent_id"]

                    # Пропускаем объект, если его родитель не был создан
                    if virtual_parent_id in failed_or_skipped_virtual_ids:
                        failed_or_skipped_virtual_ids.add(virtual_id)
                        continue

                    # Заменяем виртуальный родительский ID на реальный
                    real_parent_id = virtual_to_real_id_map.get(virtual_parent_id)

                    if not real_parent_id:
                        # Родитель не найден, значит ветка сломана.
                        # Добавляем ошибку один раз и пропускаем всю ветку без лишних логов.
                        if virtual_parent_id not in failed_or_skipped_virtual_ids:
                            errors.append(
                                f"Не найден родительский объект с ID '{virtual_parent_id}' для создания '{obj_data['name']}'. "
                                "Ветка импорта пропущена."
                            )
                        failed_or_skipped_virtual_ids.add(virtual_id)
                        continue

                    # Создаем модель Pydantic для создания объекта
                    try:
                        # Готовим данные для фабрики
                        user_data_for_factory = {
                            "Класс": obj_data["class_name"],
                            "Имя объекта": obj_data["name"],
                            **obj_data["attributes"],
                        }
                        # Фабрика вернет "чертеж" с готовой моделью
                        blueprint = await self.factory.create(user_data_for_factory)

                        # Добавляем запрос в список на обработку,
                        # передавая всю необходимую мета-информацию
                        request = CreateRequest(
                            model=blueprint.model_instance,
                            class_id=blueprint.class_id,
                            class_name=blueprint.class_name,
                            attributes_meta=blueprint.attributes_meta,
                            parent_id=real_parent_id,
                            virtual_id=obj_data["virtual_id"],
                        )
                        requests_to_process.append(request)
                        batch_virtual_ids.add(request.virtual_id)

                    except Exception as e:
                        error_msg = f"Ошибка подготовки данных для объекта '{obj_data['name']}': {e}"
                        logger.error(error_msg, exc_info=True)
                        errors.append(error_msg)
                        # Если подготовка не удалась, считаем объект сбойным
                        failed_or_skipped_virtual_ids.add(obj_data["virtual_id"])

                if not requests_to_process:
                    continue

                # Пакетное создание объектов на текущем уровне
                try:
                    # Используем корректный метод create_many
                    creation_result = await self.object_service.create_many(requests_to_process)

                    # Обрабатываем успешные результаты
                    succeeded_virtual_ids = set()
                    for created_model in creation_result.created_models:
                        # Находим исходный запрос по инстансу модели.
                        # Это надежно, так как ObjectService мутирует исходный объект.
                        original_request = next(
                            (req for req in requests_to_process if req.model is created_model),
                            None,
                        )
                        if original_request:
                            virtual_id = original_request.virtual_id
                            real_id = created_model._id
                            virtual_to_real_id_map[virtual_id] = real_id
                            succeeded_virtual_ids.add(virtual_id)

                            # Ищем исходные данные по virtual_id для отчета
                            source_data = next(
                                (obj for obj in preview.objects_to_create if obj.get("virtual_id") == virtual_id), {}
                            )
                            created_objects.append(
                                {
                                    "id": real_id,
                                    "name": created_model.name,
                                    "class_name": created_model.Neosintez.class_name,
                                    "level": source_data.get("level", -1),
                                }
                            )
                            created_by_level[level] = created_by_level.get(level, 0) + 1
                        else:
                            logger.warning(
                                f"Не удалось найти исходный запрос для созданного объекта с ID {created_model._id}"
                            )

                    # Определяем сбои на уровне через разницу множеств
                    level_failures = batch_virtual_ids - succeeded_virtual_ids
                    failed_or_skipped_virtual_ids.update(level_failures)

                    # Добавляем ошибки из результата пакетной операции
                    if creation_result.errors:
                        errors.extend(creation_result.errors)

                except Exception as e:
                    error_msg = f"Критическая ошибка при пакетном создании объектов на уровне {level}: {e}"
                    logger.error(error_msg, exc_info=True)
                    errors.append(error_msg)
                    # Если вся пачка упала, все ID в ней считаются сбойными
                    failed_or_skipped_virtual_ids.update(batch_virtual_ids)

            duration = (datetime.now() - start_time).total_seconds()
            logger.info(f"Импорт завершен за {duration:.2f} сек.")

            return ImportResult(
                total_created=len(created_objects),
                created_by_level=created_by_level,
                created_objects=created_objects,
                errors=errors,
                warnings=warnings,
                duration_seconds=duration,
            )

        except Exception as e:
            logger.error(f"Критическая ошибка в процессе импорта: {e}", exc_info=True)
            return ImportResult(
                total_created=0,
                created_by_level={},
                created_objects=[],
                errors=[f"Критическая ошибка: {e}"],
                warnings=[],
                duration_seconds=(datetime.now() - start_time).total_seconds(),
            )

    def _check_headers(self, df: pd.DataFrame) -> bool:
        """Проверяет, содержит ли первая строка в DataFrame заголовки."""
        if df.empty:
            return False
        first_row = df.iloc[0]
        # Простой эвристический анализ: если большинство ячеек в первой строке - строки,
        # то скорее всего это заголовки.
        string_cells = sum(isinstance(cell, str) for cell in first_row)
        return string_cells / len(first_row) > 0.5

    def _find_column(self, headers: List[str], column_names: List[str]) -> Optional[int]:
        """Находит индекс колонки по одному из возможных имен."""
        headers_lower = [str(h).lower() for h in headers]
        names_lower = [str(n).lower() for n in column_names]
        for name in names_lower:
            if name in headers_lower:
                return headers_lower.index(name)
        return None

    async def _load_objects_sequentially(
        self,
        excel_path: str,
        structure: ExcelStructure,
        parent_id: str,
        worksheet_name: Optional[str] = None,
    ) -> tuple[List[Dict[str, Any]], List[str]]:
        """
        Загружает объекты из Excel и строит иерархическую структуру для импорта.
        Возвращает плоский список объектов и список ошибок, найденных при загрузке.
        """
        if structure.total_rows == 0:
            return [], []

        # Загружаем данные
        try:
            # Читаем только первый лист, если имя не указано
            sheet_to_read = worksheet_name or 0

            # Сначала читаем без заголовков, чтобы проверить их наличие
            df_no_header = pd.read_excel(excel_path, sheet_name=sheet_to_read, header=None)

            if self._check_headers(df_no_header):
                # Если заголовки есть, перечитываем с ними
                df = pd.read_excel(excel_path, sheet_name=sheet_to_read, header=0)
            else:
                # Иначе используем данные как есть, с числовыми индексами колонок
                df = df_no_header

        except Exception as e:
            logger.error(f"Не удалось прочитать Excel файл: {e}", exc_info=True)
            # Используем корректный конструктор исключения
            raise NeosintezAPIError(message=f"Не удалось прочитать Excel файл: {e}", status_code=400) from e

        objects_to_create = []
        errors = []
        parent_map: Dict[int, str] = {0: parent_id}  # level -> virtual_id
        virtual_id_counter = 0

        for index, row in df.iterrows():
            # Пропускаем пустые строки, где нет даже уровня
            if pd.isna(row.iloc[structure.level_column]):
                continue

            try:
                level = int(row.iloc[structure.level_column])

                class_name_raw = row.iloc[structure.class_column]
                name_raw = row.iloc[structure.name_column]

                # Проверяем строки без класса или имени. Это критическая ошибка.
                if pd.isna(class_name_raw) or str(class_name_raw).strip().lower() in ("", "nan") or \
                   pd.isna(name_raw) or str(name_raw).strip() == "":
                    error_msg = f"Строка {index + 2}: Отсутствуют обязательные данные (Класс или Имя объекта)."
                    logger.error(error_msg)
                    errors.append(error_msg)
                    continue

                class_name = str(class_name_raw)
                name = str(name_raw)

                # Создаем виртуальный ID для этого объекта
                virtual_id_counter += 1
                virtual_id = f"virtual::{virtual_id_counter}"

                # Определяем родителя
                current_parent_id = parent_map.get(level - 1)
                if not current_parent_id:
                    # --- ИЗМЕНЕННАЯ ЛОГИКА ---
                    # Вместо переназначения родителя, регистрируем как ошибку
                    max_level_before_jump = max(parent_map.keys()) if parent_map else 0
                    error_msg = (
                        f"Строка {index + 2}: Нарушена иерархия. "
                        f"Объект '{name}' уровня {level} не может следовать за уровнем {max_level_before_jump}."
                    )
                    logger.error(error_msg)
                    errors.append(error_msg)
                    continue  # Пропускаем эту строку

                # Собираем атрибуты
                attributes = {}
                for col_index, attr_name in structure.attribute_columns.items():
                    if col_index < len(row):
                        value = row.iloc[col_index]
                        if pd.notna(value) and value != "":
                            attributes[attr_name] = value

                objects_to_create.append(
                    {
                        "row_index": index + 2,  # +1 за header, +1 за 0-индексацию
                        "level": level,
                        "class_name": class_name,
                        "name": name,
                        "parent_id": current_parent_id,
                        "virtual_id": virtual_id,
                        "attributes": attributes,
                    }
                )

                # Обновляем карту родителя для следующего уровня
                parent_map[level] = virtual_id

            except (ValueError, IndexError) as e:
                logger.error(f"Ошибка парсинга строки {index + 2}: {e}", exc_info=True)
                continue

        return objects_to_create, errors

    async def _validate_objects(self, objects_to_create: List[Dict[str, Any]]) -> tuple[List[str], List[str]]:
        """
        Проверяет объекты перед созданием, используя кешированный ClassService.
        Возвращает кортеж (критические_ошибки, предупреждения).
        """
        errors = []
        warnings = []
        if not objects_to_create:
            return errors, warnings

        try:
            # Убедимся, что кэш классов и атрибутов в ClassService загружен
            await self.class_service._ensure_cache_loaded()

            # Создаем словарь {имя_класса: класс} для быстрой проверки
            all_classes = await self.class_service.get_all()
            class_name_map = {cls.Name.lower(): cls for cls in all_classes}

            # 1. Проверить существование всех классов (критическая ошибка)
            class_names_from_file = {obj["class_name"].lower() for obj in objects_to_create if "class_name" in obj}

            for name in class_names_from_file:
                if name not in class_name_map:
                    original_name = next(
                        (obj["class_name"] for obj in objects_to_create if obj["class_name"].lower() == name), name
                    )
                    errors.append(f"Класс '{original_name}' не найден в Неосинтезе.")

            if errors:
                # Если есть ошибки с классами, нет смысла проверять атрибуты
                return errors, warnings

            # 2. Проверить атрибуты для каждого объекта (предупреждение)
            unique_warnings = set()
            for obj in objects_to_create:
                class_name = obj.get("class_name")
                if not class_name:
                    continue

                class_info = class_name_map.get(class_name.lower())
                if not class_info:
                    # Ошибка уже добавлена выше
                    continue

                # Получаем атрибуты из кэша ClassService
                class_attributes = await self.class_service.get_attributes(str(class_info.Id))
                class_attribute_names = {attr.Name.lower() for attr in class_attributes}

                for attr_name in obj.get("attributes", {}):
                    if attr_name.lower() not in class_attribute_names:
                        # Собираем уникальные пары (класс, атрибут) для группировки
                        unique_warnings.add((class_name, attr_name))

            # Форматируем сгруппированные предупреждения
            for class_name, attr_name in sorted(list(unique_warnings)):
                warnings.append(f"Атрибут '{attr_name}' не найден в классе '{class_name}'.")

        except NeosintezAPIError as e:
            logger.error(f"Произошла ошибка API при валидации: {e}", exc_info=True)
            errors.append(f"Ошибка API при проверке данных: {e}")
        except Exception as e:
            logger.error(f"Произошла непредвиденная ошибка при валидации: {e}", exc_info=True)
            errors.append(f"Непредвиденная ошибка при проверке данных: {e}")

        return errors, warnings
