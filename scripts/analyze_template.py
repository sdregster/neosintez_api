"""
Анализ шаблона импорта и подготовка структуры данных для импорта в Неосинтез.
"""

import asyncio
import json
import logging
import os
import sys
from typing import Any, Dict, List

import pandas as pd

from dotenv import load_dotenv

from neosintez_api.client import NeosintezClient
from neosintez_api.config import load_settings
from neosintez_api.exceptions import NeosintezAuthError, NeosintezConnectionError

# Загрузка переменных окружения из .env файла
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("neosintez_analyzer")


class TemplateAnalyzer:
    """
    Класс для анализа Excel шаблона и подготовки структуры данных для импорта.
    """

    def __init__(
        self,
        client: NeosintezClient,
        excel_path: str,
    ):
        """
        Инициализация анализатора.

        Args:
            client: Инициализированный клиент API Neosintez
            excel_path: Путь к Excel файлу с данными для анализа
        """
        self.client = client
        self.excel_path = excel_path
        self.df = None
        self.classes = {}  # Словарь классов: имя класса -> EntityClass
        self.class_attributes = {}  # Словарь атрибутов классов: id класса -> список атрибутов
        self.analyzed_structure = {}  # Результаты анализа

    async def load_excel(self) -> pd.DataFrame:
        """
        Загружает данные из Excel файла.

        Returns:
            DataFrame с данными Excel
        """
        logger.info(f"Загрузка данных из файла {self.excel_path}")
        try:
            self.df = pd.read_excel(self.excel_path)
            logger.info(
                f"Загружено {len(self.df)} строк данных и {len(self.df.columns)} колонок"
            )
            return self.df
        except Exception as e:
            logger.error(f"Ошибка при загрузке Excel файла: {str(e)}")
            raise

    async def load_neosintez_classes(self) -> Dict[str, Any]:
        """
        Получает список классов из Neosintez API.

        Returns:
            Словарь классов: имя класса -> EntityClass
        """
        logger.info("Получение списка классов объектов из Neosintez")
        try:
            entities = await self.client.classes.get_all()
            self.classes = {entity.Name: entity for entity in entities}
            logger.info(f"Получено {len(entities)} классов")
            return self.classes
        except Exception as e:
            logger.error(f"Ошибка при получении классов: {str(e)}")
            raise

    async def load_class_attributes(self, class_id: str) -> List[Any]:
        """
        Загружает атрибуты класса из Neosintez.

        Args:
            class_id: ID класса

        Returns:
            Список атрибутов класса
        """
        if class_id in self.class_attributes:
            return self.class_attributes[class_id]

        logger.info(f"Получение атрибутов класса {class_id}")
        try:
            attributes = await self.client.classes.get_attributes(class_id)
            logger.info(f"Получено {len(attributes)} атрибутов для класса {class_id}")
            self.class_attributes[class_id] = attributes
            return attributes
        except Exception as e:
            logger.error(f"Ошибка при получении атрибутов класса {class_id}: {str(e)}")
            return []

    async def analyze_unique_classes(self) -> Dict[str, Any]:
        """
        Анализирует уникальные значения в колонке 'Класс'.

        Returns:
            Словарь с информацией о классах
        """
        if self.df is None:
            await self.load_excel()

        result = {"unique_values": [], "counts": {}, "total_count": 0}

        # Проверяем наличие колонки 'Класс'
        if "Класс" in self.df.columns:
            # Получаем все уникальные значения
            unique_classes = self.df["Класс"].dropna().unique()
            result["unique_values"] = list(unique_classes)
            result["total_count"] = len(unique_classes)

            # Подсчитываем количество каждого класса
            for cls in unique_classes:
                count = len(self.df[self.df["Класс"] == cls])
                result["counts"][cls] = count

            logger.info(f"Найдено {len(unique_classes)} уникальных классов")
            for cls, count in result["counts"].items():
                logger.info(f"  - {cls}: {count} записей")

        else:
            logger.warning("Колонка 'Класс' не найдена в файле")

        return result

    async def analyze_column_structure(self) -> Dict[str, Any]:
        """
        Анализирует структуру колонок и их значений.

        Returns:
            Словарь с информацией о колонках
        """
        if self.df is None:
            await self.load_excel()

        result = {
            "columns_info": {},
            "total_columns": len(self.df.columns),
            "key_columns": {},
        }

        # Анализируем каждую колонку
        for column in self.df.columns:
            # Основная информация
            non_null = self.df[column].count()
            null_count = self.df[column].isna().sum()
            unique_count = self.df[column].nunique()

            # Определяем тип данных
            col_type = str(self.df[column].dtype)

            # Сводная информация о колонке
            col_info = {
                "name": column,
                "non_null_count": int(non_null),
                "null_count": int(null_count),
                "unique_count": int(unique_count),
                "dtype": col_type,
                "fill_rate": float(non_null / len(self.df))
                if len(self.df) > 0
                else 0.0,
            }

            # Добавляем примеры значений, если есть непустые
            if non_null > 0:
                sample_values = self.df[column].dropna().head(5).tolist()
                col_info["sample_values"] = sample_values

            result["columns_info"][column] = col_info

        # Определяем ключевые колонки
        key_columns = [
            "Уровень",
            "Класс",
            "Идентификатор",
            "Имя объекта",
            "Наименование раздела",
        ]
        for key_col in key_columns:
            if key_col in self.df.columns:
                result["key_columns"][key_col] = {
                    "found": True,
                    "index": list(self.df.columns).index(key_col),
                }
            else:
                result["key_columns"][key_col] = {"found": False}

        return result

    async def analyze_template(self) -> Dict[str, Any]:
        """
        Анализирует шаблон импорта и формирует полную структуру данных.

        Returns:
            Словарь с полным анализом шаблона
        """
        # Загружаем данные
        if self.df is None:
            await self.load_excel()

        # Базовая информация о файле
        self.analyzed_structure = {
            "file_info": {
                "path": self.excel_path,
                "rows_count": len(self.df),
                "columns_count": len(self.df.columns),
                "columns": list(self.df.columns),
            },
            "preview": {
                "first_rows": self.df.head(3).to_dict(orient="records"),
            },
        }

        # Анализируем классы
        classes_info = await self.analyze_unique_classes()
        self.analyzed_structure["classes"] = classes_info

        # Анализируем структуру колонок
        columns_info = await self.analyze_column_structure()
        self.analyzed_structure["columns"] = columns_info

        # Определяем структуру для сопоставления с Neosintez
        # Загружаем классы из Neosintez
        await self.load_neosintez_classes()

        # Добавляем информацию о сопоставлении классов
        class_mappings = {}
        for class_name in classes_info["unique_values"]:
            # Пытаемся найти класс в Neosintez
            if class_name in self.classes:
                entity_class = self.classes[class_name]
                class_mappings[class_name] = {
                    "id": str(entity_class.Id),
                    "name": entity_class.Name,
                    "match_type": "exact",
                    "count": classes_info["counts"][class_name],
                }
                logger.info(f"Класс '{class_name}' найден в Neosintez")

                # Загружаем атрибуты класса
                attributes = await self.load_class_attributes(str(entity_class.Id))
                class_mappings[class_name]["attributes_count"] = len(attributes)
                class_mappings[class_name]["attributes"] = [
                    {"id": str(attr.Id), "name": attr.Name} for attr in attributes
                ]

                # Добавим эту часть после строки, где получаем атрибуты класса
                class_attributes = await self.client.classes.get_all_with_attributes()
                for class_data in class_attributes:
                    if str(class_data.get("Id")) == str(entity_class.Id):
                        logger.info(
                            f"Найдены данные класса {class_data['Name']} в общем списке"
                        )
                        if "Attributes" in class_data and class_data["Attributes"]:
                            logger.info(
                                f"Структура атрибутов класса: {json.dumps(dict(list(class_data['Attributes'].items())[:2]), ensure_ascii=False)}"
                            )

                # Получаем все атрибуты через общий эндпоинт
                all_attributes_response = await self.client._request(
                    "GET", "api/attributes"
                )
                if (
                    isinstance(all_attributes_response, dict)
                    and "Result" in all_attributes_response
                ):
                    all_attributes = all_attributes_response["Result"]
                    # Пример первых двух атрибутов для понимания структуры
                    if all_attributes and len(all_attributes) > 1:
                        logger.info(
                            f"Пример атрибута из общего эндпоинта: {json.dumps(all_attributes[0], ensure_ascii=False)}"
                        )
            else:
                # Пытаемся найти частичное совпадение
                found = False
                for neosintez_class_name, entity_class in self.classes.items():
                    if (
                        class_name.lower() in neosintez_class_name.lower()
                        or neosintez_class_name.lower() in class_name.lower()
                    ):
                        class_mappings[class_name] = {
                            "id": str(entity_class.Id),
                            "name": entity_class.Name,
                            "original_name": neosintez_class_name,
                            "match_type": "partial",
                            "count": classes_info["counts"][class_name],
                        }
                        logger.info(
                            f"Для класса '{class_name}' найдено частичное совпадение: '{neosintez_class_name}'"
                        )

                        # Загружаем атрибуты класса
                        attributes = await self.load_class_attributes(
                            str(entity_class.Id)
                        )
                        class_mappings[class_name]["attributes_count"] = len(attributes)
                        class_mappings[class_name]["attributes"] = [
                            {"id": str(attr.Id), "name": attr.Name}
                            for attr in attributes
                        ]

                        found = True
                        break

                if not found:
                    class_mappings[class_name] = {
                        "id": None,
                        "name": class_name,
                        "match_type": "not_found",
                        "count": classes_info["counts"][class_name],
                    }
                    logger.warning(f"Класс '{class_name}' не найден в Neosintez")

        self.analyzed_structure["neosintez_mappings"] = {
            "class_mappings": class_mappings,
            "mapped_count": sum(
                1 for m in class_mappings.values() if m["match_type"] != "not_found"
            ),
            "unmapped_count": sum(
                1 for m in class_mappings.values() if m["match_type"] == "not_found"
            ),
        }

        # Сопоставляем колонки с атрибутами классов
        column_attribute_mappings = {}
        unmapped_columns = []

        # Исключаем ключевые колонки из сопоставления с атрибутами
        excluded_columns = ["Уровень", "Класс", "Идентификатор", "Наименование раздела"]

        for column in self.df.columns:
            if column not in excluded_columns:
                mapped = False

                # Для каждого класса проверяем соответствие колонки атрибутам
                for class_name, mapping in class_mappings.items():
                    if mapping["match_type"] != "not_found" and "attributes" in mapping:
                        for attr in mapping["attributes"]:
                            # Проверяем точное совпадение
                            if attr["name"] == column:
                                column_attribute_mappings[column] = {
                                    "class_name": class_name,
                                    "attribute_id": attr["id"],
                                    "attribute_name": attr["name"],
                                    "match_type": "exact",
                                }
                                mapped = True
                                break

                            # Проверяем частичное совпадение
                            if (
                                attr["name"].lower() in column.lower()
                                or column.lower() in attr["name"].lower()
                            ):
                                column_attribute_mappings[column] = {
                                    "class_name": class_name,
                                    "attribute_id": attr["id"],
                                    "attribute_name": attr["name"],
                                    "match_type": "partial",
                                }
                                mapped = True
                                break

                    if mapped:
                        break

                if not mapped:
                    unmapped_columns.append(column)

        self.analyzed_structure["attribute_mappings"] = {
            "mapped_columns": column_attribute_mappings,
            "unmapped_columns": unmapped_columns,
            "mapped_count": len(column_attribute_mappings),
            "unmapped_count": len(unmapped_columns),
        }

        return self.analyzed_structure

    async def save_analysis_results(self, output_file: str) -> None:
        """
        Сохраняет результаты анализа в JSON-файл.

        Args:
            output_file: Путь к выходному файлу
        """
        if not self.analyzed_structure:
            await self.analyze_template()

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(
                self.analyzed_structure,
                f,
                ensure_ascii=False,
                indent=2,
                default=lambda o: str(o)
                if not isinstance(o, (dict, list, str, int, float, bool, type(None)))
                else o,
            )

        logger.info(f"Результаты анализа сохранены в {output_file}")


async def main():
    """
    Основная функция для запуска анализа шаблона.
    """
    try:
        # Загрузка настроек из переменных окружения
        settings = load_settings()
        logger.info(f"Загружены настройки для подключения к {settings.base_url}")

        # Определяем параметры анализа
        import argparse

        parser = argparse.ArgumentParser(
            description="Анализ шаблона импорта для Neosintez"
        )
        parser.add_argument(
            "--file", default="template.xlsx", help="Имя Excel файла в папке data"
        )
        parser.add_argument(
            "--output",
            default="template_analysis.json",
            help="Имя файла для сохранения результатов анализа",
        )
        args = parser.parse_args()

        # Путь к Excel файлу
        excel_path = args.file
        if not os.path.exists(excel_path):
            # Пробуем добавить префикс data/
            excel_path = os.path.join("data", args.file)
            if not os.path.exists(excel_path):
                logger.error(f"Файл {excel_path} не найден")
                return

        # Выходной файл для результатов анализа
        output_file = args.output
        if not os.path.dirname(output_file):
            output_file = os.path.join("data", output_file)

        logger.info(f"Запуск анализа файла: {excel_path}")

        # Инициализация клиента API
        async with NeosintezClient(settings) as client:
            try:
                # Аутентификация
                logger.info("Попытка аутентификации...")
                token = await client.auth()
                logger.info(f"Получен токен: {token[:10]}...")

                # Создаем анализатор
                analyzer = TemplateAnalyzer(
                    client=client,
                    excel_path=excel_path,
                )

                # Выполняем анализ
                analysis_result = await analyzer.analyze_template()

                # Сохраняем результаты
                await analyzer.save_analysis_results(output_file)

                logger.info(
                    f"Анализ успешно завершен. Результаты сохранены в {output_file}"
                )

                # Выводим краткую сводку
                logger.info("Краткая сводка анализа:")
                logger.info(
                    f"- Строк в файле: {analysis_result['file_info']['rows_count']}"
                )
                logger.info(
                    f"- Колонок в файле: {analysis_result['file_info']['columns_count']}"
                )
                logger.info(
                    f"- Найдено классов: {analysis_result['classes']['total_count']}"
                )

                # Выводим информацию о сопоставлении классов
                if "neosintez_mappings" in analysis_result:
                    mappings = analysis_result["neosintez_mappings"]
                    logger.info(f"- Сопоставлено {mappings['mapped_count']} классов")
                    logger.info(
                        f"- Не сопоставлено {mappings['unmapped_count']} классов"
                    )

                # Выводим информацию о сопоставлении атрибутов
                if "attribute_mappings" in analysis_result:
                    attr_mappings = analysis_result["attribute_mappings"]
                    logger.info(
                        f"- Сопоставлено {attr_mappings['mapped_count']} колонок с атрибутами"
                    )
                    logger.info(
                        f"- Не сопоставлено {attr_mappings['unmapped_count']} колонок"
                    )

            except NeosintezAuthError as e:
                logger.error(f"Ошибка аутентификации: {str(e)}")
            except NeosintezConnectionError as e:
                logger.error(f"Ошибка соединения: {str(e)}")
            except Exception as e:
                logger.error(f"Неожиданная ошибка: {str(e)}")
                logger.error(f"Детали: {type(e).__name__}: {str(e)}")
                import traceback

                logger.error(traceback.format_exc())
    except Exception as e:
        logger.error(f"Ошибка при инициализации: {str(e)}")
        import traceback

        logger.error(traceback.format_exc())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Прервано пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {str(e)}")
        sys.exit(1)
