"""
Скрипт для импорта данных из Excel в Неосинтез с использованием Pydantic-моделей.
Объединяет функциональность парсинга Excel и создания объектов через Pydantic.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Type, TypeVar
from uuid import UUID

import pandas as pd

# Загрузка переменных окружения из .env файла
from dotenv import load_dotenv
from pydantic import BaseModel, Field, create_model

from neosintez_api.client import NeosintezClient
from neosintez_api.models import EntityClass


load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("neosintez_import_pydantic")

# Определяем тип для динамических моделей
T = TypeVar("T", bound=BaseModel)


# ────────────────────────────
#  1. Базовые модели
# ────────────────────────────


class NeosintezBaseModel(BaseModel):
    """
    Базовая Pydantic-модель для объектов Неосинтеза.
    """

    Name: str
    # Класс будет указываться через аннотацию __class_name__ в дочерних классах


class UUIDEncoder(json.JSONEncoder):
    """
    JSON-encoder для сериализации UUID и datetime.
    """

    def default(self, obj):
        if isinstance(obj, UUID):
            return str(obj)
        elif hasattr(obj, "isoformat"):
            return obj.isoformat()
        return super().default(obj)


# ────────────────────────────
#  2. Вспомогательные функции и классы
# ────────────────────────────

# Глобальный кэш для метаданных сущностей
ENTITY_CACHE: Dict[str, Dict] = {}


async def get_entity_meta(
    client: NeosintezClient,
    class_name: Optional[str] = None,
    class_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Получает метаданные класса по имени или ID, используя кэширование.

    Args:
        client: Клиент API Neosintez
        class_name: Имя класса для поиска (опционально, если указан class_id)
        class_id: ID класса для поиска (опционально, если указан class_name)

    Returns:
        Dict[str, Any]: Метаданные класса с атрибутами
    """
    global ENTITY_CACHE

    # Проверяем наличие хотя бы одного идентификатора
    if class_name is None and class_id is None:
        raise ValueError("Необходимо указать либо class_name, либо class_id")

    # Формируем ключ кэша
    cache_key = class_id if class_name is None else class_name

    # Если класс уже в кэше, возвращаем его
    if cache_key in ENTITY_CACHE:
        logger.debug(f"Используем кэшированные метаданные класса '{cache_key}'")
        return ENTITY_CACHE[cache_key]

    logger.info(f"Загрузка метаданных класса '{cache_key}' из API...")

    try:
        # Получаем классы вместе с атрибутами одним запросом
        logger.info("Запрашиваем классы вместе с атрибутами...")
        endpoint = "api/structure/entities"
        params = {"only": "false"}  # Явно запрашиваем с атрибутами

        all_classes_with_attrs = await client._request("GET", endpoint, params=params)
        if isinstance(all_classes_with_attrs, list):
            logger.info(f"Получено {len(all_classes_with_attrs)} классов с атрибутами")
        else:
            logger.warning("Получен неожиданный формат ответа при запросе классов")
            all_classes_with_attrs = []

        # Ищем нужный класс по имени или ID
        target_class = None
        for cls in all_classes_with_attrs:
            if (class_name and cls.get("Name") == class_name) or (
                class_id and str(cls.get("Id")) == str(class_id)
            ):
                target_class = cls
                break

        if not target_class:
            logger.warning(
                f"Класс '{cache_key}' не найден в списке классов с атрибутами"
            )
            # Пробуем стандартный метод
            logger.info("Пробуем получить классы стандартным методом...")
            classes = await client.classes.get_all()
            logger.info(f"Получено {len(classes)} классов из API")

            # Ищем нужный класс по имени или ID
            for cls in classes:
                if (class_name and cls.Name == class_name) or (
                    class_id and str(cls.Id) == str(class_id)
                ):
                    target_class_obj = cls
                    target_class = target_class_obj.model_dump()
                    break

            if not target_class:
                search_term = class_name if class_name else f"с ID {class_id}"
                raise ValueError(
                    f"Класс {search_term} не найден в списке классов API Neosintez"
                )

            logger.info(
                f"Найден класс '{target_class['Name']}' (ID: {target_class['Id']})"
            )

            # Получаем атрибуты отдельно
            attributes = await client.classes.get_attributes(target_class["Id"])
            logger.info(
                f"Получено {len(attributes)} атрибутов для класса '{target_class['Name']}'"
            )

            if len(attributes) == 0:
                logger.warning(
                    f"Внимание: класс '{target_class['Name']}' не имеет атрибутов!"
                )

            # Собираем информацию в словарь
            target_class["Attributes"] = [attr.model_dump() for attr in attributes]
        else:
            logger.info(
                f"Найден класс '{target_class['Name']}' (ID: {target_class['Id']}) с атрибутами"
            )

            # Превращаем атрибуты из словаря {id: data} в список атрибутов для совместимости
            attributes_list = []
            if target_class.get("Attributes"):
                if isinstance(target_class["Attributes"], dict):
                    # Если атрибуты в формате словаря {id: data}
                    for attr_id, attr_data in target_class["Attributes"].items():
                        try:
                            # Создаем базовую структуру атрибута
                            attr_dict = {"Id": attr_id}

                            # Если attr_data - словарь, копируем все его поля
                            if isinstance(attr_data, dict):
                                attr_dict.update(attr_data)
                            # Если attr_data - число (скорее всего тип атрибута), сохраняем как Type
                            elif isinstance(attr_data, (int, float)):
                                attr_dict["Type"] = int(attr_data)
                                attr_dict["Name"] = f"Attribute {attr_id}"

                            # Добавляем в список атрибутов
                            attributes_list.append(attr_dict)
                        except Exception as e:
                            logger.error(
                                f"Ошибка при обработке атрибута {attr_id}: {e!s}"
                            )
                elif isinstance(target_class["Attributes"], list):
                    # Если атрибуты уже в формате списка
                    attributes_list = target_class["Attributes"]

            target_class["Attributes"] = attributes_list
            logger.info(
                f"Обработано {len(attributes_list)} атрибутов для класса '{target_class['Name']}'"
            )

        # Сохраняем класс в кэше
        ENTITY_CACHE[cache_key] = target_class
        # Также сохраняем по другому ключу для удобства поиска
        if class_name is None and "Name" in target_class:
            ENTITY_CACHE[target_class["Name"]] = target_class
        if class_id is None and "Id" in target_class:
            ENTITY_CACHE[str(target_class["Id"])] = target_class

    except Exception as e:
        logger.error(f"Ошибка при получении метаданных класса '{cache_key}': {e!s}")
        raise

    return ENTITY_CACHE[cache_key]


class PydanticExcelParser:
    """
    Класс для парсинга Excel файла и создания Pydantic-моделей.
    """

    # Ключевые заголовки колонок для автоопределения
    LEVEL_COLUMN_NAMES = ["Уровень", "Level", "Вложенность"]
    CLASS_COLUMN_NAMES = ["Класс", "Class", "Тип объекта"]
    NAME_COLUMN_NAMES = ["Имя объекта", "Name", "Название объекта", "Наименование"]

    def __init__(
        self, client: NeosintezClient, excel_path: str, worksheet_name: str = None
    ):
        """
        Инициализация парсера Excel.

        Args:
            client: Инициализированный клиент API Neosintez
            excel_path: Путь к Excel файлу с данными для импорта
            worksheet_name: Имя листа в Excel файле (если None, берется первый лист)
        """
        self.client = client
        self.excel_path = excel_path
        self.worksheet_name = worksheet_name

        self.df = None  # DataFrame с данными из Excel
        self.headers = None  # Заголовки столбцов
        self.level_column = None  # Индекс колонки с уровнями
        self.class_column = None  # Индекс колонки с классами
        self.name_column = None  # Индекс колонки с именами объектов

        # Информация о найденных колонках для отладки
        self.columns_info = {}

        # Флаг, указывающий, что первая строка - это заголовки
        self.has_headers = True

        # Маппинг классов в Неосинтезе по имени
        self.classes_map = {}

        # Результаты парсинга - словарь объектов по уровням
        self.parsed_objects = {}

        # Динамически созданные модели по имени класса
        self.class_models = {}

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
            logger.error(f"Ошибка при загрузке Excel файла: {e!s}")
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
            self.classes_map = {entity.Name: entity for entity in entities}
            logger.info(f"Получено {len(entities)} классов")
            return self.classes_map
        except Exception as e:
            logger.error(f"Ошибка при получении классов: {e!s}")
            raise

    async def create_pydantic_model_for_class(
        self, class_name: str
    ) -> Type[NeosintezBaseModel]:
        """
        Создает Pydantic-модель для заданного класса с учетом его атрибутов.

        Args:
            class_name: Имя класса в Неосинтезе

        Returns:
            Type[NeosintezBaseModel]: Динамически созданный класс модели
        """
        # Проверяем кэш моделей
        if class_name in self.class_models:
            return self.class_models[class_name]

        logger.info(f"Создание Pydantic-модели для класса '{class_name}'")

        # Получаем метаданные класса
        entity = None
        if class_name in self.classes_map:
            entity_class = self.classes_map[class_name]
            entity = await get_entity_meta(self.client, class_name=class_name)
        else:
            # Ищем класс по частичному совпадению
            for existing_class_name, entity_class_obj in self.classes_map.items():
                if class_name.lower() in existing_class_name.lower():
                    entity_class = entity_class_obj
                    entity = await get_entity_meta(
                        self.client, class_name=existing_class_name
                    )
                    logger.info(
                        f"Для класса '{class_name}' найдено частичное совпадение: '{existing_class_name}'"
                    )
                    # Обновляем класс для единообразия
                    class_name = existing_class_name
                    break

        if entity is None:
            logger.warning(
                f"Не найден класс '{class_name}' для создания Pydantic-модели"
            )
            # Создаем базовую модель без атрибутов
            model = create_model(
                f"{class_name}Model",
                __base__=NeosintezBaseModel,
                __module__=__name__,
                # Добавляем скрытое поле для хранения имени класса
                __class_name__=(class_name, ...),
            )
            # Сохраняем в кэше
            self.class_models[class_name] = model
            return model

        # Создаем словарь полей для модели
        fields = {}
        for attr in entity["Attributes"]:
            attr_name = attr["Name"]
            attr_type = attr.get("Type", 0)

            # Определяем тип поля в зависимости от типа атрибута
            field_type = self._get_field_type_for_attribute(attr_type)
            # Создаем поле с правильным алиасом
            fields[attr_name] = (field_type, Field(default=None, alias=attr_name))

        # Создаем новый класс модели
        model = create_model(
            f"{class_name}Model",
            __base__=NeosintezBaseModel,
            __module__=__name__,
            # Добавляем скрытое поле для хранения имени класса
            __class_name__=(class_name, ...),
            **fields,
        )

        # Сохраняем в кэше
        self.class_models[class_name] = model
        logger.info(
            f"Создана модель {model.__name__} с {len(fields)} атрибутами для класса '{class_name}'"
        )

        return model

    def _get_field_type_for_attribute(self, attr_type: int) -> Type:
        """
        Определяет тип поля Pydantic на основе типа атрибута в Neosintez.

        Args:
            attr_type: Тип атрибута в Neosintez

        Returns:
            Type: Тип для поля Pydantic
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

        if attr_type == 1:
            return Optional[float]
        elif attr_type == 2:
            return Optional[str]
        elif attr_type == 3:
            return Optional[datetime]
        elif attr_type == 4:
            return Optional[Dict[str, Any]]  # Ссылка как словарь {Id, Name}
        elif attr_type == 5:
            return Optional[Dict[str, Any]]  # Файл как словарь
        elif attr_type == 6:
            return Optional[str]  # Текст как строка
        elif attr_type == 7:
            return Optional[bool]  # Флаг как bool
        elif attr_type == 8:
            return Optional[Dict[str, Any]]  # Справочник как словарь {Id, Name}
        else:
            return Optional[Any]  # По умолчанию Any

    async def parse_excel_to_models(self) -> Dict[int, List[NeosintezBaseModel]]:
        """
        Парсит данные из Excel и создает соответствующие Pydantic-модели,
        группируя их по уровням.

        Returns:
            Dict[int, List[NeosintezBaseModel]]: Словарь моделей объектов по уровням
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
                "Не все необходимые колонки определены. Невозможно распарсить данные."
            )
            return {}

        # Загружаем классы из Neosintez, если они еще не загружены
        if not self.classes_map:
            await self.load_neosintez_classes()

        models_by_level = {}

        # Определяем, с какой строки начинаются данные
        start_row = 1 if self.has_headers else 0

        # Проходим по всем строкам DataFrame (пропускаем заголовки, если они есть)
        for idx, row in self.df.iloc[start_row:].iterrows():
            try:
                # Получаем значения из ключевых колонок
                level_value = row.iloc[self.level_column]
                if pd.isna(level_value):
                    continue

                level = int(level_value)
                class_name = str(row.iloc[self.class_column])
                if pd.isna(class_name):
                    continue

                name = str(row.iloc[self.name_column])
                if pd.isna(name):
                    name = f"{class_name} #{idx + 1}"

                logger.debug(
                    f"Обработка строки {idx}: уровень {level}, класс '{class_name}', имя '{name}'"
                )

                # Создаем или получаем модель для класса
                model_class = await self.create_pydantic_model_for_class(class_name)

                # Подготавливаем данные для модели
                model_data = {"Name": name}

                # Получаем все поля модели
                model_fields = model_class.__annotations__.keys()

                # Обрабатываем атрибуты из строки
                for col_idx, col_name in enumerate(self.headers):
                    if col_idx not in (
                        self.level_column,
                        self.class_column,
                        self.name_column,
                    ):
                        value = row.iloc[col_idx]
                        if not pd.isna(value):
                            # Ищем соответствующее поле в модели
                            field_name_in_model = None
                            for field_name in model_fields:
                                field_info = model_class.model_fields.get(field_name)
                                if field_name == col_name or (
                                    field_info and field_info.alias == col_name
                                ):
                                    field_name_in_model = field_name
                                    break

                            if field_name_in_model:
                                model_data[field_name_in_model] = value
                                logger.debug(
                                    f"Атрибут '{col_name}' = '{value}' добавлен в модель"
                                )
                            else:
                                logger.debug(
                                    f"Атрибут '{col_name}' не найден в модели для класса '{class_name}'"
                                )

                # Создаем экземпляр модели
                try:
                    instance = model_class(**model_data)

                    # Добавляем в словарь моделей по уровням
                    if level not in models_by_level:
                        models_by_level[level] = []
                    models_by_level[level].append(instance)

                    logger.debug(f"Создана модель для объекта '{name}' уровня {level}")
                except Exception as e:
                    logger.error(
                        f"Ошибка при создании модели для объекта '{name}': {e!s}"
                    )
                    continue

            except Exception as e:
                logger.error(f"Ошибка обработки строки {idx}: {e!s}")
                continue

        # Выводим статистику по созданным моделям
        total_models = sum(len(models) for models in models_by_level.values())
        logger.info(f"Создано {total_models} моделей по {len(models_by_level)} уровням")
        for level, models in sorted(models_by_level.items()):
            logger.info(f"Уровень {level}: {len(models)} моделей")

        return models_by_level
