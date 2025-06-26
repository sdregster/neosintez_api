"""
Модуль для импорта данных из Excel в Неосинтез через Pydantic-модели.
Обеспечивает чтение Excel файлов, преобразование в Pydantic-модели и параллельное создание объектов.
"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, TypeVar, Union
from uuid import UUID

import pandas as pd
from pydantic import BaseModel, ValidationError

from .core.client import NeosintezClient
from .exceptions import ApiError
from .services.object_service import ObjectService


# Определяем тип для Pydantic моделей
T = TypeVar("T", bound=BaseModel)

# Настройка логгера
logger = logging.getLogger("neosintez_api.excel_import")


class ImportResult(BaseModel):
    """
    Результат импорта данных из Excel.

    Attributes:
        total_rows: Общее количество строк для импорта
        successful: Количество успешно созданных объектов
        failed: Количество неудачных попыток создания
        errors: Список ошибок с деталями
        execution_time: Время выполнения импорта в секундах
        created_object_ids: Список ID созданных объектов
    """

    total_rows: int
    successful: int
    failed: int
    errors: List[Dict[str, Any]]
    execution_time: float
    created_object_ids: List[str]


class ExcelImporter:
    """
    Класс для импорта данных из Excel в Неосинтез через Pydantic-модели.

    Обеспечивает:
    - Чтение Excel файлов с помощью pandas
    - Преобразование строк в Pydantic-модели
    - Параллельное создание объектов с ограничением нагрузки
    - Формирование детального отчета о результатах импорта
    """

    def __init__(self, client: NeosintezClient, max_concurrent_requests: int = 10, batch_size: int = 50):
        """
        Инициализирует импортер.

        Args:
            client: Клиент для взаимодействия с API Неосинтеза
            max_concurrent_requests: Максимальное количество параллельных запросов
            batch_size: Размер батча для обработки данных
        """
        self.client = client
        self.object_service = ObjectService(client)
        self.max_concurrent_requests = max_concurrent_requests
        self.batch_size = batch_size
        self._semaphore = asyncio.Semaphore(max_concurrent_requests)

    async def import_from_excel(
        self,
        excel_path: Union[str, Path],
        model_class: Type[T],
        parent_id: Union[str, UUID],
        sheet_name: Optional[str] = None,
        start_row: int = 0,
        name_column: str = "Name",
    ) -> ImportResult:
        """
        Импортирует данные из Excel файла.

        Args:
            excel_path: Путь к Excel файлу
            model_class: Класс Pydantic-модели для создания объектов
            parent_id: ID родительского объекта
            sheet_name: Название листа Excel (если None, берется первый лист)
            start_row: Номер строки, с которой начинать чтение (0-based)
            name_column: Название колонки с именем объекта

        Returns:
            ImportResult: Результат импорта с детальной статистикой

        Raises:
            FileNotFoundError: Если Excel файл не найден
            ValueError: Если указанный лист не существует
            ApiError: При ошибках API
        """
        start_time = datetime.now()

        logger.info(f"Начинаю импорт из файла {excel_path}")
        logger.info(f"Модель: {model_class.__name__}, Родитель: {parent_id}")

        try:
            # Читаем Excel файл
            df = await self._read_excel_file(excel_path, sheet_name, start_row)
            logger.info(f"Прочитано {len(df)} строк из Excel файла")

            # Проверяем наличие колонки с именем
            if name_column not in df.columns:
                available_columns = ", ".join(df.columns.tolist())
                raise ValueError(
                    f"Колонка '{name_column}' не найдена в Excel файле. Доступные колонки: {available_columns}"
                )

            # Удаляем пустые строки
            df = df.dropna(subset=[name_column])
            logger.info(f"После удаления пустых строк осталось {len(df)} записей")

            if df.empty:
                logger.warning("Нет данных для импорта")
                return ImportResult(
                    total_rows=0, successful=0, failed=0, errors=[], execution_time=0.0, created_object_ids=[]
                )

            # Преобразуем DataFrame в модели
            models = await self._convert_dataframe_to_models(df, model_class)
            logger.info(f"Создано {len(models)} валидных моделей из {len(df)} строк")

            # Создаем объекты параллельно с ограничением нагрузки
            results = await self._create_objects_parallel(models, parent_id)

            # Формируем итоговый результат
            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()

            successful_ids = [r["object_id"] for r in results if r["success"]]
            errors = [r for r in results if not r["success"]]

            result = ImportResult(
                total_rows=len(df),
                successful=len(successful_ids),
                failed=len(errors),
                errors=errors,
                execution_time=execution_time,
                created_object_ids=successful_ids,
            )

            logger.info(f"Импорт завершен за {execution_time:.2f} сек.")
            logger.info(f"Успешно: {result.successful}, Ошибок: {result.failed}")

            return result

        except Exception as e:
            logger.error(f"Критическая ошибка при импорте: {e}")
            raise ApiError(f"Ошибка импорта из Excel: {e}") from e

    async def _read_excel_file(
        self, excel_path: Union[str, Path], sheet_name: Optional[str], start_row: int
    ) -> pd.DataFrame:
        """
        Читает Excel файл с помощью pandas.

        Args:
            excel_path: Путь к Excel файлу
            sheet_name: Название листа
            start_row: Стартовая строка

        Returns:
            pd.DataFrame: Данные из Excel файла
        """
        excel_path = Path(excel_path)

        if not excel_path.exists():
            raise FileNotFoundError(f"Excel файл не найден: {excel_path}")

        logger.debug(f"Читаю Excel файл: {excel_path}")

        try:
            # Используем движок openpyxl для xlsx файлов
            engine = "openpyxl" if excel_path.suffix.lower() in [".xlsx", ".xlsm"] else None

            df = pd.read_excel(excel_path, sheet_name=sheet_name, skiprows=start_row, engine=engine)

            logger.debug(f"Прочитано {len(df)} строк и {len(df.columns)} колонок")
            return df

        except Exception as e:
            raise ValueError(f"Ошибка при чтении Excel файла: {e}") from e

    async def _convert_dataframe_to_models(self, df: pd.DataFrame, model_class: Type[T]) -> List[T]:
        """
        Преобразует DataFrame в список Pydantic-моделей.

        Args:
            df: DataFrame с данными
            model_class: Класс Pydantic-модели

        Returns:
            List[T]: Список валидных моделей
        """
        models = []
        errors = []

        for index, row in df.iterrows():
            try:
                # Преобразуем Series в словарь, заменяя NaN на None
                row_dict = row.where(pd.notna(row), None).to_dict()

                # Создаем модель
                model = model_class(**row_dict)
                models.append(model)

            except ValidationError as e:
                error_details = {
                    "row_index": int(index),
                    "error_type": "validation_error",
                    "error_message": str(e),
                    "row_data": row.to_dict(),
                }
                errors.append(error_details)
                logger.warning(f"Ошибка валидации в строке {index}: {e}")

            except Exception as e:
                error_details = {
                    "row_index": int(index),
                    "error_type": "conversion_error",
                    "error_message": str(e),
                    "row_data": row.to_dict(),
                }
                errors.append(error_details)
                logger.warning(f"Ошибка преобразования в строке {index}: {e}")

        if errors:
            logger.warning(f"Обнаружено {len(errors)} ошибок при создании моделей")

        return models

    async def _create_objects_parallel(self, models: List[T], parent_id: Union[str, UUID]) -> List[Dict[str, Any]]:
        """
        Создает объекты параллельно с ограничением нагрузки.

        Args:
            models: Список моделей для создания
            parent_id: ID родительского объекта

        Returns:
            List[Dict[str, Any]]: Результаты создания объектов
        """
        logger.info(f"Создаю {len(models)} объектов с максимум {self.max_concurrent_requests} параллельными запросами")

        # Разбиваем на батчи
        batches = [models[i : i + self.batch_size] for i in range(0, len(models), self.batch_size)]
        all_results = []

        for batch_num, batch in enumerate(batches, 1):
            logger.info(f"Обрабатываю батч {batch_num}/{len(batches)} ({len(batch)} объектов)")

            # Создаем задачи для всех объектов в батче
            tasks = [self._create_single_object(model, parent_id) for model in batch]

            # Выполняем задачи параллельно
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Обрабатываем результаты батча
            for result in batch_results:
                if isinstance(result, Exception):
                    all_results.append(
                        {
                            "success": False,
                            "error_type": "execution_error",
                            "error_message": str(result),
                            "object_id": None,
                        }
                    )
                else:
                    all_results.append(result)

        return all_results

    async def _create_single_object(self, model: T, parent_id: Union[str, UUID]) -> Dict[str, Any]:
        """
        Создает один объект с семафором для ограничения нагрузки.

        Args:
            model: Модель объекта
            parent_id: ID родительского объекта

        Returns:
            Dict[str, Any]: Результат создания объекта
        """
        async with self._semaphore:
            try:
                object_id = await self.object_service.create(model, parent_id)

                return {
                    "success": True,
                    "object_id": object_id,
                    "model_name": getattr(model, "Name", getattr(model, "name", "Unknown")),
                    "error_type": None,
                    "error_message": None,
                }

            except Exception as e:
                logger.error(f"Ошибка при создании объекта {getattr(model, 'Name', 'Unknown')}: {e}")

                return {
                    "success": False,
                    "object_id": None,
                    "model_name": getattr(model, "Name", getattr(model, "name", "Unknown")),
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                }

    def print_import_summary(self, result: ImportResult) -> None:
        """
        Выводит краткий отчет о результатах импорта.

        Args:
            result: Результат импорта
        """
        print("\n" + "=" * 60)
        print("ОТЧЕТ О РЕЗУЛЬТАТАХ ИМПОРТА")
        print("=" * 60)
        print(f"Общее количество строк:     {result.total_rows}")
        print(f"Успешно создано объектов:   {result.successful}")
        print(f"Ошибок:                     {result.failed}")
        print(f"Время выполнения:           {result.execution_time:.2f} сек")
        print(f"Скорость:                   {result.total_rows / result.execution_time:.1f} строк/сек")

        if result.failed > 0:
            print("\nОшибки:")
            for i, error in enumerate(result.errors[:5], 1):  # Показываем первые 5 ошибок
                error_type = error.get("error_type", "unknown")
                error_msg = error.get("error_message", "Unknown error")
                model_name = error.get("model_name", "Unknown")
                print(f"  {i}. {model_name}: {error_type} - {error_msg}")

            if len(result.errors) > 5:
                print(f"  ... и еще {len(result.errors) - 5} ошибок")

        print("=" * 60)

    async def validate_excel_structure(
        self, excel_path: Union[str, Path], model_class: Type[T], sheet_name: Optional[str] = None, start_row: int = 0
    ) -> Dict[str, Any]:
        """
        Проверяет структуру Excel файла на совместимость с Pydantic-моделью.

        Args:
            excel_path: Путь к Excel файлу
            model_class: Класс Pydantic-модели
            sheet_name: Название листа
            start_row: Стартовая строка

        Returns:
            Dict[str, Any]: Результат валидации структуры
        """
        try:
            # Читаем только первые несколько строк для анализа
            df = await self._read_excel_file(excel_path, sheet_name, start_row)

            if df.empty:
                return {"valid": False, "error": "Excel файл пуст или не содержит данных"}

            # Получаем поля модели
            model_fields = set(model_class.model_fields.keys())
            excel_columns = set(df.columns)

            # Проверяем соответствие колонок
            missing_fields = model_fields - excel_columns
            extra_columns = excel_columns - model_fields

            # Пытаемся создать модель из первой строки
            first_row = df.iloc[0].where(pd.notna(df.iloc[0]), None).to_dict()

            validation_errors = []
            try:
                model_class(**first_row)
            except ValidationError as e:
                validation_errors = [str(err) for err in e.errors()]

            return {
                "valid": len(missing_fields) == 0 and len(validation_errors) == 0,
                "total_rows": len(df),
                "model_fields": list(model_fields),
                "excel_columns": list(excel_columns),
                "missing_fields": list(missing_fields),
                "extra_columns": list(extra_columns),
                "validation_errors": validation_errors,
                "sample_data": first_row,
            }

        except Exception as e:
            return {"valid": False, "error": f"Ошибка при валидации структуры: {e}"}
