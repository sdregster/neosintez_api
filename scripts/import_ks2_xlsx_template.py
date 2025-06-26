"""
Скрипт для импорта данных КС-2 из заранее подготовленного шаблона в Неосистезу.
"""

import asyncio
import json
import logging
import os
import sys
import traceback
from typing import Any, Dict, List, Optional
from uuid import UUID
from datetime import datetime

import pandas as pd

# Загрузка переменных окружения из .env файла
from dotenv import load_dotenv

from neosintez_api.client import NeosintezClient
from neosintez_api.config import load_settings
from neosintez_api.models import EntityClass

load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("neosintez_import")


class UUIDEncoder(json.JSONEncoder):
    """
    JSON-encoder для сериализации UUID и datetime.
    """

    def default(self, obj):
        if isinstance(obj, UUID):
            # Если объект - UUID, преобразуем его в строку
            return str(obj)
        elif hasattr(obj, "isoformat"):
            # Если объект имеет метод isoformat (например, datetime, date)
            return obj.isoformat()
        return super().default(obj)


class NeosintezExcelImporter:
    """
    Класс для импорта данных из Excel в Neosintez согласно заданной структуре маппинга.
    """

    # Ключевые заголовки колонок для автоопределения
    LEVEL_COLUMN_NAMES = ["Уровень", "Level", "Вложенность"]
    CLASS_COLUMN_NAMES = ["Класс", "Class", "Тип объекта"]
    NAME_COLUMN_NAMES = ["Имя объекта", "Name", "Название объекта", "Наименование"]

    def __init__(
        self,
        client: NeosintezClient,
        excel_path: str,
        target_object_id: str,
        worksheet_name: str = None,
    ):
        """
        Инициализация импортера с автоматическим определением колонок.

        Args:
            client: Инициализированный клиент API Neosintez
            excel_path: Путь к Excel файлу с данными для импорта
            target_object_id: ID объекта в Neosintez, куда будут импортированы данные
            worksheet_name: Имя листа в Excel файле (если None, берется первый лист)
        """
        self.client = client
        self.excel_path = excel_path
        self.target_object_id = target_object_id
        self.worksheet_name = worksheet_name

        self.df = None  # DataFrame с данными из Excel
        self.headers = None  # Заголовки столбцов
        self.level_column = None  # Индекс колонки с уровнями
        self.class_column = None  # Индекс колонки с классами
        self.name_column = None  # Индекс колонки с именами объектов

        self.classes = {}  # Словарь классов: имя класса -> EntityClass
        self.class_attributes = {}  # Словарь атрибутов классов: id класса -> список атрибутов

        # Информация о найденных колонках для отладки
        self.columns_info = {}

        # Флаг, указывающий, что первая строка - это заголовки
        self.has_headers = True

    async def load_excel(self) -> pd.DataFrame:
        """
        Загружает данные из Excel файла и определяет ключевые колонки.

        Returns:
            DataFrame с данными Excel
        """
        logger.info(f"Загрузка данных из файла {self.excel_path}")
        try:
            # Если имя листа не указано, берем первый лист
            if self.worksheet_name is None:
                self.df = pd.read_excel(self.excel_path, header=None)
            else:
                self.df = pd.read_excel(
                    self.excel_path, sheet_name=self.worksheet_name, header=None
                )

            logger.info(f"Загружено {len(self.df)} строк данных")

            # Проверяем, содержит ли первая строка заголовки
            self._check_headers()

            # Определяем заголовки и ключевые колонки
            self._detect_columns()

            return self.df
        except Exception as e:
            logger.error(f"Ошибка при загрузке Excel файла: {str(e)}")
            raise

    def _check_headers(self):
        """
        Проверяет, содержит ли первая строка заголовки.
        """
        if self.df is None or len(self.df) == 0:
            return

        # Проверяем первую строку на наличие ключевых слов для заголовков
        first_row = self.df.iloc[0]

        # Проверяем наличие ключевых слов в первой строке
        has_level = any(
            name.lower() in str(cell).lower()
            for name in self.LEVEL_COLUMN_NAMES
            for cell in first_row
        )
        has_class = any(
            name.lower() in str(cell).lower()
            for name in self.CLASS_COLUMN_NAMES
            for cell in first_row
        )
        has_name = any(
            name.lower() in str(cell).lower()
            for name in self.NAME_COLUMN_NAMES
            for cell in first_row
        )

        self.has_headers = has_level and has_class and has_name

        if self.has_headers:
            logger.info("Первая строка содержит заголовки")
            # Используем первую строку как заголовки
            self.headers = [str(cell) for cell in first_row]
        else:
            logger.info(
                "Первая строка не содержит заголовки, используем стандартные имена колонок"
            )
            # Используем стандартные имена колонок
            self.headers = [f"Column_{i}" for i in range(len(first_row))]

            # Предполагаем, что первые три колонки - это Уровень, Класс, Имя объекта
            if len(self.headers) >= 3:
                self.level_column = 0
                self.class_column = 1
                self.name_column = 2
                logger.info(
                    "Используем стандартное расположение колонок: Уровень(0), Класс(1), Имя объекта(2)"
                )

    def _detect_columns(self):
        """
        Автоматически определяет ключевые колонки по их заголовкам.
        """
        if self.df is None or len(self.df) == 0:
            logger.error("DataFrame не загружен или пуст")
            return

        # Если у нас уже определены колонки, ничего не делаем
        if (
            self.level_column is not None
            and self.class_column is not None
            and self.name_column is not None
        ):
            return

        # Если нет заголовков, используем первую строку для определения
        if not self.has_headers:
            return

        # Сохраняем все колонки для отладки
        self.columns_info = {
            col_idx: col_name for col_idx, col_name in enumerate(self.headers)
        }

        # Определяем колонку уровня
        for name in self.LEVEL_COLUMN_NAMES:
            for col_idx, col_name in enumerate(self.headers):
                if isinstance(col_name, str) and name.lower() in col_name.lower():
                    self.level_column = col_idx
                    logger.info(
                        f"Определена колонка уровня: '{col_name}' (индекс {col_idx})"
                    )
                    break
            if self.level_column is not None:
                break

        # Определяем колонку класса
        for name in self.CLASS_COLUMN_NAMES:
            for col_idx, col_name in enumerate(self.headers):
                if isinstance(col_name, str) and name.lower() in col_name.lower():
                    self.class_column = col_idx
                    logger.info(
                        f"Определена колонка класса: '{col_name}' (индекс {col_idx})"
                    )
                    break
            if self.class_column is not None:
                break

        # Определяем колонку имени объекта
        for name in self.NAME_COLUMN_NAMES:
            for col_idx, col_name in enumerate(self.headers):
                if isinstance(col_name, str) and name.lower() in col_name.lower():
                    self.name_column = col_idx
                    logger.info(
                        f"Определена колонка имени: '{col_name}' (индекс {col_idx})"
                    )
                    break
            if self.name_column is not None:
                break

        # Проверяем, что все необходимые колонки найдены
        if self.level_column is None:
            logger.warning(
                f"Не удалось определить колонку уровня. Искали {self.LEVEL_COLUMN_NAMES}"
            )
        if self.class_column is None:
            logger.warning(
                f"Не удалось определить колонку класса. Искали {self.CLASS_COLUMN_NAMES}"
            )
        if self.name_column is None:
            logger.warning(
                f"Не удалось определить колонку имени объекта. Искали {self.NAME_COLUMN_NAMES}"
            )

    async def load_neosintez_classes(self) -> Dict[str, EntityClass]:
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
        logger.info(f"Получение атрибутов класса {class_id}")
        try:
            attributes = await self.client.classes.get_attributes(class_id)
            logger.info(f"Получено {len(attributes)} атрибутов для класса {class_id}")
            return attributes
        except Exception as e:
            logger.error(f"Ошибка при получении атрибутов класса {class_id}: {str(e)}")
            return []

    async def build_object_hierarchy(self) -> List[Dict[str, Any]]:
        """
        Строит иерархию объектов на основе данных из Excel.

        Returns:
            Список объектов с их иерархией и атрибутами
        """
        if self.df is None:
            await self.load_excel()

        # Проверяем, что все необходимые колонки определены
        if (
            self.level_column is None
            or self.class_column is None
            or self.name_column is None
        ):
            logger.error(
                "Не все необходимые колонки определены. Невозможно построить иерархию."
            )
            return []

        # Загружаем классы, если они еще не загружены
        if not self.classes:
            await self.load_neosintez_classes()

        objects = []
        parent_by_level = {0: None}  # Словарь родителей по уровням

        # Определяем, с какой строки начинаются данные
        start_row = 1 if self.has_headers else 0

        # Проходим по всем строкам DataFrame (пропускаем заголовки, если они есть)
        for idx, row in self.df.iloc[start_row:].iterrows():
            level_value = row.iloc[self.level_column]
            if pd.isna(level_value):
                continue

            level = int(level_value)
            class_name = row.iloc[self.class_column]
            if pd.isna(class_name):
                continue

            name = row.iloc[self.name_column]
            if pd.isna(name):
                name = f"{class_name} #{idx + 1}"

            # Проверяем, есть ли класс в списке полученных из Neosintez
            class_id = None
            class_found = False
            entity_class = None

            # Пробуем найти класс точно по имени
            if class_name in self.classes:
                entity_class = self.classes[class_name]
                class_id = entity_class.Id
                class_found = True
            else:
                # Если точное совпадение не найдено, ищем частичное совпадение
                for existing_class_name, entity_class_obj in self.classes.items():
                    if class_name.lower() in existing_class_name.lower():
                        entity_class = entity_class_obj
                        class_id = entity_class.Id
                        logger.info(
                            f"Для класса '{class_name}' найдено частичное совпадение: '{existing_class_name}'"
                        )
                        class_found = True
                        break

            if not class_found:
                logger.warning(
                    f"Класс '{class_name}' не найден в Neosintez. Пропуск строки {idx}."
                )
                continue

            # Определяем родительский объект
            parent_id = parent_by_level.get(level - 1, self.target_object_id)

            # Создаем объект
            obj = {
                "id": f"row_{idx}",
                "name": name,
                "class_id": str(class_id),  # Преобразуем UUID в строку
                "class_name": class_name,
                "parent_id": parent_id,
                "level": level,
                "row_index": idx,
                "attributes": {},
            }

            # Заполняем атрибуты из строки
            for col_idx, col_name in enumerate(self.headers):
                if col_idx not in (
                    self.level_column,
                    self.class_column,
                    self.name_column,
                ):
                    value = row.iloc[col_idx]
                    if not pd.isna(value):
                        # Добавляем атрибут в словарь
                        obj["attributes"][col_name] = value
                        logger.debug(
                            f"Добавлен атрибут '{col_name}' = '{value}' для объекта '{name}'"
                        )

            objects.append(obj)

            # Запоминаем объект как родителя для следующего уровня
            parent_by_level[level] = obj["id"]

        # Подробно выводим информацию о каждом объекте
        logger.info(f"Построена иерархия из {len(objects)} объектов")
        for obj in objects:
            attrs_info = ", ".join([f"{k}: {v}" for k, v in obj["attributes"].items()])
            logger.info(
                f"Объект: '{obj['name']}' (ID: {obj['id']}, Класс: {obj['class_name']}, Родитель: {obj['parent_id']}, Уровень: {obj['level']}, Атрибуты: {attrs_info})"
            )

        return objects

    async def create_objects_in_neosintez(
        self, objects: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Создает объекты в Neosintez.

        Args:
            objects: Список объектов для создания

        Returns:
            Список созданных объектов с добавленными ID из Neosintez
        """
        logger.info(
            f"Начало создания объектов в Neosintez. Всего объектов: {len(objects)}"
        )

        # Словарь для хранения созданных объектов: временный id -> реальный id в Neosintez
        created_objects = {}
        result = []
        root_level_objects = []  # Список объектов первого уровня

        # Сначала создаем объекты первого уровня (родитель - целевой объект)
        for obj in sorted(objects, key=lambda x: x["level"]):
            try:
                # Определяем ID родителя
                parent_id = self.target_object_id
                if obj["parent_id"] in created_objects:
                    parent_id = created_objects[obj["parent_id"]]

                # Создаем объект с атрибутами
                created_obj = await self.create_object_with_attributes(
                    name=obj["name"],
                    entity_class_id=obj["class_id"],
                    parent_id=parent_id,
                    attributes=obj["attributes"],
                )

                if created_obj:
                    # Сохраняем соответствие временного ID и реального ID
                    created_objects[obj["id"]] = created_obj["Id"]

                    # Добавляем в результат
                    result_obj = obj.copy()
                    result_obj["neosintez_id"] = created_obj["Id"]
                    result.append(result_obj)

                    # Если это объект первого уровня, добавляем его в список ключевых объектов
                    if obj["level"] == 1:
                        root_level_objects.append(
                            {
                                "name": obj["name"],
                                "id": created_obj["Id"],
                                "class": obj["class_name"],
                            }
                        )
                else:
                    logger.error(f"Не удалось создать объект {obj['name']}")
            except Exception as e:
                logger.error(f"Ошибка при создании объекта {obj['name']}: {str(e)}")
                traceback.print_exc(file=sys.stderr)

        # Выводим информацию о созданных ключевых объектах
        if root_level_objects:
            logger.info("Созданные объекты первого уровня (ключевые объекты): ")
            print("\n" + "=" * 80)
            print("СОЗДАННЫЕ КЛЮЧЕВЫЕ ОБЪЕКТЫ (уровень 1):")
            print("=" * 80)

            for obj in root_level_objects:
                logger.info(f"► {obj['name']} (Класс: {obj['class']})")
                logger.info(f"  UUID: {obj['id']}")

                # Формируем ссылку на объект
                object_url = (
                    f"{str(self.client.base_url).rstrip('/')}/objects?id={obj['id']}"
                )
                logger.info(f"  Ссылка: {object_url}")

                print(f"► {obj['name']} (Класс: {obj['class']})")
                print(f"  UUID: {obj['id']}")
                print(f"  Ссылка: {object_url}")
                print("-" * 80)

        logger.info(f"Создано {len(result)} объектов в Neosintez")
        return result

    async def set_object_attributes(
        self, object_id: str, attributes: Dict[str, Any]
    ) -> bool:
        """
        Устанавливает атрибуты объекта.

        Args:
            object_id: ID объекта
            attributes: Словарь атрибутов (имя -> значение)

        Returns:
            bool: True, если атрибуты успешно установлены
        """
        logger.info(f"Установка атрибутов для объекта {object_id}")

        # Получаем объект для определения его класса
        try:
            obj = await self.client.objects.get_by_id(object_id)
            entity_id = obj.EntityId

            # Получаем атрибуты класса
            class_attributes = await self.load_class_attributes(str(entity_id))

            # Формируем список атрибутов для обновления
            attributes_data = []

            for attr_name, attr_value in attributes.items():
                # Пропускаем описание, так как оно уже установлено при создании объекта
                if attr_name == "Описание":
                    continue

                # Ищем атрибут по имени
                attr_found = None
                for class_attr in class_attributes:
                    if class_attr.Name == attr_name:
                        attr_found = class_attr
                        break

                if attr_found:
                    # Преобразуем datetime в строку ISO формата, если это необходимо
                    if hasattr(attr_value, "isoformat"):
                        attr_value = attr_value.isoformat()

                    # Создаем объект атрибута в формате WioObjectAttribute
                    attribute_data = {
                        "Id": str(attr_found.Id),
                        "Name": attr_found.Name,
                        "Type": attr_found.Type
                        if isinstance(attr_found.Type, int)
                        else attr_found.Type.Id
                        if hasattr(attr_found.Type, "Id")
                        else None,
                        "Value": attr_value,
                    }
                    attributes_data.append(attribute_data)
                    logger.info(
                        f"Атрибут '{attr_name}' (ID: {attr_found.Id}) будет установлен в '{attr_value}'"
                    )
                else:
                    logger.warning(
                        f"Атрибут '{attr_name}' не найден для класса {entity_id}"
                    )

            # Если есть атрибуты для обновления
            if attributes_data:
                # Вызываем API для обновления атрибутов
                endpoint = f"api/objects/{object_id}/attributes"
                await self.client._request("PUT", endpoint, data=attributes_data)
                logger.info(f"Атрибуты объекта {object_id} успешно обновлены")
                return True
            else:
                logger.info(f"Нет атрибутов для обновления у объекта {object_id}")
                return True

        except Exception as e:
            logger.error(
                f"Ошибка при установке атрибутов объекта {object_id}: {str(e)}"
            )
            return False

    async def set_object_attributes_direct(
        self, object_id: str, attributes: Dict[str, Any]
    ) -> bool:
        """
        Устанавливает атрибуты объекта напрямую через API.

        Args:
            object_id: ID объекта
            attributes: Словарь атрибутов (имя -> значение)

        Returns:
            bool: True, если атрибуты успешно установлены
        """
        logger.info(f"Установка атрибутов для объекта {object_id} (прямой метод)")

        try:
            # Получаем объект для определения его класса
            obj = await self.client.objects.get_by_id(object_id)
            entity_id = obj.EntityId

            # Получаем атрибуты класса
            class_attributes = await self.load_class_attributes(str(entity_id))

            # Формируем список атрибутов для обновления
            attributes_to_update = []

            for attr_name, attr_value in attributes.items():
                # Ищем атрибут в списке атрибутов класса
                class_attr = next(
                    (a for a in class_attributes if a["Name"] == attr_name), None
                )
                if class_attr:
                    attr_id = class_attr["Id"]
                    attr_type = class_attr["Type"]
                    logger.info(
                        f"Атрибут '{attr_name}' (ID: {attr_id}, тип: {attr_type}) будет установлен в '{attr_value}'"
                    )

                    # Форматируем значение в зависимости от типа атрибута
                    formatted_value = self.format_attribute_value(attr_value, attr_type)

                    # Добавляем атрибут в список для обновления
                    attributes_to_update.append(
                        {
                            "Id": attr_id,
                            "Name": attr_name,
                            "Type": attr_type,
                            "Value": formatted_value,
                        }
                    )
                else:
                    logger.warning(
                        f"Атрибут '{attr_name}' не найден для класса {entity_id}"
                    )

            # Если нет атрибутов для обновления, возвращаем True
            if not attributes_to_update:
                return True

            # Отправляем запрос на обновление атрибутов напрямую через API
            async with self.client._session.put(
                f"{self.client._api_url}/api/objects/{object_id}/attributes",
                json=attributes_to_update,
                headers=self.client._headers,
            ) as response:
                if response.status == 200:
                    logger.info(f"Атрибуты объекта {object_id} успешно обновлены")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(
                        f"Ошибка при обновлении атрибутов объекта {object_id}: {error_text}"
                    )
                    return False

        except Exception as e:
            logger.error(f"Ошибка при установке атрибутов объекта {object_id}: {e}")
            traceback.print_exc()
            return False

    def format_attribute_value(self, value: Any, attr_type: int) -> Any:
        """
        Форматирует значение атрибута в зависимости от его типа.

        Args:
            value: Значение атрибута
            attr_type: Тип атрибута

        Returns:
            Отформатированное значение атрибута
        """
        # Типы атрибутов:
        # 1 - Число
        # 2 - Строка
        # 3 - Дата
        # 4 - Ссылка
        # 5 - Файл
        # 6 - Текст
        # 7 - Флаг
        # 8 - Справочник

        if attr_type == 1:  # Число
            try:
                return float(value) if value is not None else None
            except (ValueError, TypeError):
                return 0

        elif attr_type == 2:  # Строка
            return str(value) if value is not None else None

        elif attr_type == 3:  # Дата
            if isinstance(value, str):
                try:
                    # Преобразуем строку в datetime
                    dt = datetime.strptime(value, "%Y-%m-%d")
                    # Возвращаем в формате ISO 8601
                    return dt.strftime("%Y-%m-%dT%H:%M:%S")
                except ValueError:
                    try:
                        # Пробуем другой формат
                        dt = datetime.strptime(value, "%d.%m.%Y")
                        return dt.strftime("%Y-%m-%dT%H:%M:%S")
                    except ValueError:
                        return value
            elif isinstance(value, datetime):
                return value.strftime("%Y-%m-%dT%H:%M:%S")
            return value

        elif attr_type == 4:  # Ссылка
            if isinstance(value, dict) and "Id" in value and "Name" in value:
                return value
            elif isinstance(value, str):
                try:
                    # Проверяем, является ли строка UUID
                    uuid_obj = UUID(value)
                    return {"Id": str(uuid_obj), "Name": str(uuid_obj)}
                except ValueError:
                    return {"Id": None, "Name": value}
            return None

        elif attr_type == 6:  # Текст
            return str(value) if value is not None else None

        elif attr_type == 7:  # Флаг
            if isinstance(value, bool):
                return value
            elif isinstance(value, str):
                return value.lower() in ("true", "1", "yes", "да", "y")
            elif isinstance(value, (int, float)):
                return value > 0
            return False

        elif attr_type == 8:  # Справочник
            if isinstance(value, dict) and "Id" in value and "Name" in value:
                return value
            elif isinstance(value, str):
                try:
                    # Проверяем, является ли строка UUID
                    uuid_obj = UUID(value)
                    return {"Id": str(uuid_obj), "Name": str(uuid_obj)}
                except ValueError:
                    return {"Id": None, "Name": value}
            return None

        # Для всех остальных типов возвращаем значение без изменений
        return value

    async def verify_created_objects_by_id(
        self, created_objects: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Проверяет наличие созданных объектов путем запроса каждого объекта по его ID.
        Более надежный метод, чем verify_imported_objects, так как не зависит от структуры родительского объекта.

        Args:
            created_objects: Список созданных объектов

        Returns:
            Dict[str, Any]: Результаты проверки
        """
        logger.info("Проверка наличия созданных объектов путем запроса по ID")

        verification_results = {
            "total_objects": len(created_objects),
            "found_objects": 0,
            "missing_objects": 0,
            "details": [],
        }

        # Проверяем каждый созданный объект по его ID
        for obj in created_objects:
            obj_name = obj["name"]
            obj_id = obj.get("neosintez_id", "")

            # Если ID объекта присутствует
            if obj_id:
                try:
                    # Получаем объект по ID
                    found_obj = await self.client.objects.get_by_id(obj_id)
                    verification_results["found_objects"] += 1
                    verification_results["details"].append(
                        {
                            "name": obj_name,
                            "id": obj_id,
                            "status": "найден",
                            "system_name": found_obj.Name,
                        }
                    )
                    logger.info(f"Объект найден: {found_obj.Name} (ID: {obj_id})")
                except Exception as e:
                    verification_results["missing_objects"] += 1
                    verification_results["details"].append(
                        {
                            "name": obj_name,
                            "id": obj_id,
                            "status": "не найден",
                            "error": str(e),
                        }
                    )
                    logger.warning(
                        f"Объект не найден: {obj_name} (ID: {obj_id}), ошибка: {str(e)}"
                    )
            else:
                verification_results["missing_objects"] += 1
                verification_results["details"].append(
                    {
                        "name": obj_name,
                        "id": "не указан",
                        "status": "не найден",
                        "error": "ID не указан",
                    }
                )
                logger.warning(f"Объект не имеет ID: {obj_name}")

        # Выводим сводку
        logger.info(
            f"Проверка завершена. Найдено: {verification_results['found_objects']} из {verification_results['total_objects']} объектов"
        )
        if verification_results["missing_objects"] > 0:
            logger.warning(
                f"Не найдено {verification_results['missing_objects']} объектов"
            )

        return verification_results

    async def test_excel_structure(self) -> Dict[str, Any]:
        """
        Тестовый метод для проверки распознавания структуры Excel.

        Returns:
            Словарь с информацией о распознанной структуре
        """
        if self.df is None:
            await self.load_excel()

        result = {
            "file_path": self.excel_path,
            "total_rows": len(self.df),
            "has_headers": self.has_headers,
            "columns_found": {
                "level": {
                    "index": self.level_column,
                    "name": self.headers[self.level_column]
                    if self.level_column is not None
                    else None,
                },
                "class": {
                    "index": self.class_column,
                    "name": self.headers[self.class_column]
                    if self.class_column is not None
                    else None,
                },
                "name": {
                    "index": self.name_column,
                    "name": self.headers[self.name_column]
                    if self.name_column is not None
                    else None,
                },
            },
            "all_columns": self.columns_info,
            "data_sample": [],
        }

        # Определяем, с какой строки начинаются данные
        start_row = 1 if self.has_headers else 0

        # Добавляем примеры данных (до 5 строк с данными)
        for idx, row in self.df.iloc[start_row : start_row + 5].iterrows():
            row_data = {
                "row_idx": idx,
                "level": row.iloc[self.level_column]
                if self.level_column is not None
                else None,
                "class": row.iloc[self.class_column]
                if self.class_column is not None
                else None,
                "name": row.iloc[self.name_column]
                if self.name_column is not None
                else None,
            }
            result["data_sample"].append(row_data)

        return result

    async def process_import(self, test_mode: bool = False) -> Dict[str, Any]:
        """
        Выполняет полный процесс импорта данных из Excel в Neosintez.

        Args:
            test_mode: Режим тестирования (True - без реального создания объектов)

        Returns:
            Результаты импорта
        """
        logger.info(f"Начало импорта данных из {self.excel_path} в Neosintez")

        # Загружаем данные из Excel
        await self.load_excel()

        # Тестовый режим: проверяем распознавание структуры Excel
        if test_mode:
            test_result = await self.test_excel_structure()
            logger.info(
                f"Тестовый режим. Распознана структура Excel: {json.dumps(test_result, indent=2, ensure_ascii=False)}"
            )

        # Загружаем классы из Neosintez
        classes = await self.load_neosintez_classes()

        # Строим иерархию объектов
        objects = await self.build_object_hierarchy()
        logger.info(f"Построена иерархия из {len(objects)} объектов")

        # Выводим информацию о каждом объекте
        for obj in objects:
            attributes_str = ", ".join(
                [f"{k}: {v}" for k, v in obj["attributes"].items()]
            )
            logger.info(
                f"Объект: '{obj['name']}' (ID: {obj['id']}, Класс: {obj['class_name']}, Родитель: {obj['parent_id']}, Уровень: {obj['level']}, Атрибуты: {attributes_str})"
            )

        # В тестовом режиме не создаем объекты
        if test_mode:
            logger.info("Тестовый режим: объекты не создаются в Neosintez")
            # Сохраняем результат в файл для анализа
            result = {
                "objects": objects,
                "test_mode": True,
                "timestamp": datetime.now().isoformat(),
            }
            self.save_result(result, "import_test_result.json")
            return result
        else:
            # Создаем объекты в Neosintez
            created_objects = await self.create_objects_in_neosintez(objects)
            logger.info(f"Создано {len(created_objects)} объектов в Neosintez")

            # Проверяем наличие созданных объектов
            logger.info("Проверка наличия созданных объектов путем запроса по ID")
            verified_objects = []
            for obj in created_objects:
                if "neosintez_id" in obj:
                    try:
                        neosintez_obj = await self.client.objects.get_by_id(
                            obj["neosintez_id"]
                        )
                        logger.info(
                            f"Объект найден: {neosintez_obj.Name} (ID: {neosintez_obj.Id})"
                        )
                        verified_objects.append(obj)
                    except Exception as e:
                        logger.error(
                            f"Объект не найден: {obj['name']} (ID: {obj['neosintez_id']}): {str(e)}"
                        )

            logger.info(
                f"Проверка завершена. Найдено: {len(verified_objects)} из {len(created_objects)} объектов"
            )

            # Сохраняем результат в файл
            result = {
                "objects": created_objects,
                "verified_objects": len(verified_objects),
                "test_mode": False,
                "timestamp": datetime.now().isoformat(),
            }
            self.save_result(result, "import_result.json")

            # Выводим статистику по созданным объектам
            class_stats = {}
            for obj in created_objects:
                class_name = obj["class_name"]
                if class_name not in class_stats:
                    class_stats[class_name] = 0
                class_stats[class_name] += 1

            logger.info("Сводка по импортированным объектам:")
            for class_name, count in class_stats.items():
                logger.info(f"  {class_name}: {count} объектов")

            # Выводим информацию о созданных объектах первого уровня
            root_level_objects = [obj for obj in created_objects if obj["level"] == 1]
            if root_level_objects:
                print("\n" + "=" * 80)
                print("СОЗДАННЫЕ КЛЮЧЕВЫЕ ОБЪЕКТЫ (уровень 1):")
                print("=" * 80)
                for obj in root_level_objects:
                    if "neosintez_id" in obj:
                        base_url = str(self.client.settings.base_url).rstrip("/")
                        object_url = f"{base_url}/objects?id={obj['neosintez_id']}"
                        print(f"► {obj['name']} (Класс: {obj['class_name']})")
                        print(f"  UUID: {obj['neosintez_id']}")
                        print(f"  Ссылка: {object_url}")
                        print("-" * 80)

            # Проверяем наличие созданных объектов еще раз
            logger.info("Проверка наличия созданных объектов путем запроса по ID")
            verified_count = 0
            for obj in created_objects:
                if "neosintez_id" in obj:
                    try:
                        neosintez_obj = await self.client.objects.get_by_id(
                            obj["neosintez_id"]
                        )
                        logger.info(
                            f"Объект найден: {neosintez_obj.Name} (ID: {neosintez_obj.Id})"
                        )
                        verified_count += 1
                    except Exception as e:
                        logger.error(
                            f"Объект не найден: {obj['name']} (ID: {obj['neosintez_id']}): {str(e)}"
                        )

            logger.info(
                f"Проверка завершена. Найдено: {verified_count} из {len(created_objects)} объектов"
            )

            return result

    async def create_object_with_attributes(
        self,
        name: str,
        entity_class_id: str,
        parent_id: str,
        attributes: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Создает объект с указанными атрибутами.

        Args:
            name: Имя объекта
            entity_class_id: ID класса объекта
            parent_id: ID родительского объекта
            attributes: Словарь атрибутов (имя -> значение)

        Returns:
            Dict[str, Any]: Созданный объект или None, если создание не удалось
        """
        logger.info(
            f"Создание объекта '{name}' класса '{entity_class_id}' с родителем {parent_id}"
        )

        try:
            # Создаем словарь с данными объекта
            data = {
                "Name": name,
                "Entity": {
                    "Id": entity_class_id,
                    "Name": "Класс объекта",  # Добавляем обязательное поле Name
                },
                "Description": "",
            }

            # Создаем объект
            object_id = await self.client.objects.create(parent_id=parent_id, data=data)

            if object_id:
                logger.info(f"Объект '{name}' успешно создан с ID {object_id}")

                # Если есть атрибуты, устанавливаем их
                if attributes:
                    await self.set_object_attributes_direct(object_id, attributes)

                # Получаем созданный объект
                obj = await self.client.objects.get_by_id(object_id)
                return obj.dict()
            else:
                logger.error(f"Не удалось создать объект '{name}'")
                return None
        except Exception as e:
            logger.error(f"Ошибка при создании объекта '{name}': {e}")
            return None

    def save_result(self, result: Dict[str, Any], filename: str) -> None:
        """
        Сохраняет результат импорта в JSON-файл.

        Args:
            result: Результаты импорта
            filename: Имя файла для сохранения
        """

        data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
            logger.info(f"Создана директория {data_dir}")

        file_path = os.path.join(data_dir, filename)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2, cls=UUIDEncoder)

        logger.info(f"Результат сохранен в {file_path}")


async def main():
    """
    Основная функция для запуска импорта данных.
    """
    try:
        # Загрузка настроек из переменных окружения
        settings = load_settings()
        logger.info(f"Загружены настройки для подключения к {settings.base_url}")

        # Определяем режим работы (тестовый или реальный импорт)
        import argparse

        parser = argparse.ArgumentParser(
            description="Импорт данных из Excel в Neosintez"
        )
        parser.add_argument(
            "--test",
            action="store_true",
            help="Запуск в тестовом режиме без создания объектов",
        )
        parser.add_argument(
            "--file",
            default="simple_import.xlsx",
            help="Имя Excel файла в папке data (по умолчанию: simple_import.xlsx)",
        )
        parser.add_argument(
            "--parent",
            default="a7928b22-5a25-f011-91dd-005056b6948b",
            help="ID родительского объекта (по умолчанию: a7928b22-5a25-f011-91dd-005056b6948b)",
        )
        args = parser.parse_args()

        # Проверяем наличие файла
        import os

        data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
            logger.info(f"Создана директория {data_dir}")

        excel_path = os.path.join(data_dir, args.file)
        if not os.path.exists(excel_path):
            logger.error(f"Файл {excel_path} не найден")
            return

        logger.info(f"Используется файл {excel_path}")
        logger.info(f"ID родительского объекта: {args.parent}")
        logger.info(f"Тестовый режим: {args.test}")

        # Создаем клиент API
        async with NeosintezClient(settings) as client:
            # Проверяем существование родительского объекта
            try:
                parent_object = await client.objects.get_by_id(args.parent)
                logger.info(
                    f"Родительский объект: {parent_object.Name} (ID: {parent_object.Id})"
                )
            except Exception as e:
                logger.error(f"Ошибка при получении родительского объекта: {str(e)}")
                return

            # Создаем импортер и запускаем импорт
            importer = NeosintezExcelImporter(
                client=client, excel_path=excel_path, target_object_id=args.parent
            )
            result = await importer.process_import(test_mode=args.test)

            # Выводим сводку об импорте
            if args.test:
                logger.info(
                    "Тестовый режим завершен. Объекты не были созданы в Neosintez."
                )

                # Выводим сводку по объектам
                classes_count = {}
                for obj in result["objects"]:
                    class_name = obj["class_name"]
                    if class_name not in classes_count:
                        classes_count[class_name] = 0
                    classes_count[class_name] += 1

                logger.info("Сводка по объектам:")
                for class_name, count in classes_count.items():
                    logger.info(f"  {class_name}: {count} объектов")
            else:
                logger.info(
                    "Импорт завершен. Результат сохранен в data/import_result.json"
                )

                # Выводим сводку по созданным объектам
                classes_count = {}
                for obj in result["objects"]:
                    class_name = obj["class_name"]
                    if class_name not in classes_count:
                        classes_count[class_name] = 0
                    classes_count[class_name] += 1

                logger.info("Сводка по импортированным объектам:")
                for class_name, count in classes_count.items():
                    logger.info(f"  {class_name}: {count} объектов")

                # Выводим информацию о созданных объектах первого уровня
                root_level_objects = [
                    obj for obj in result["objects"] if obj["level"] == 1
                ]
                if root_level_objects:
                    print("\n" + "=" * 80)
                    print("СОЗДАННЫЕ КЛЮЧЕВЫЕ ОБЪЕКТЫ (уровень 1):")
                    print("=" * 80)
                    for obj in root_level_objects:
                        if "neosintez_id" in obj:
                            base_url = str(settings.base_url).rstrip("/")
                            object_url = f"{base_url}/objects?id={obj['neosintez_id']}"
                            print(f"► {obj['name']} (Класс: {obj['class_name']})")
                            print(f"  UUID: {obj['neosintez_id']}")
                            print(f"  Ссылка: {object_url}")
                            print("-" * 80)

    except Exception as e:
        logger.error(f"Ошибка при выполнении импорта: {str(e)}")
        traceback.print_exc(file=sys.stderr)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Прервано пользователем")
    except Exception:
        logger.error(f"Критическая ошибка: {traceback.format_exc()}")
        sys.exit(1)
