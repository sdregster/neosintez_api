"""
Скрипт для импорта объектов из Excel файла в Неосинтез с учетом специфического формата файла.
"""

import asyncio
import json
import logging
import os
import sys
import traceback
from typing import Any, Dict, List

import pandas as pd

# Загрузка переменных окружения из .env файла
from dotenv import load_dotenv

from neosintez_api.client import NeosintezClient
from neosintez_api.config import load_settings
from neosintez_api.exceptions import NeosintezAuthError, NeosintezConnectionError
from neosintez_api.models import EntityClass


load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("neosintez_import")


class FixedExcelImporter:
    """
    Класс для импорта данных из Excel в Neosintez с учетом специфического формата файла.
    """

    def __init__(
        self,
        client: NeosintezClient,
        excel_path: str,
        target_object_id: str,
        worksheet_name: str = None,
    ):
        """
        Инициализация импортера.

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
        self.classes = {}  # Словарь классов: имя класса -> EntityClass
        self.class_attributes = {}  # Словарь атрибутов классов: id класса -> список атрибутов

    async def load_excel(self) -> pd.DataFrame:
        """
        Загружает данные из Excel файла.

        Returns:
            DataFrame с данными Excel
        """
        logger.info(f"Загрузка данных из файла {self.excel_path}")
        try:
            # Если имя листа не указано, берем первый лист
            if self.worksheet_name is None:
                self.df = pd.read_excel(self.excel_path)
            else:
                self.df = pd.read_excel(self.excel_path, sheet_name=self.worksheet_name)

            logger.info(f"Загружено {len(self.df)} строк данных")

            # Печатаем первые несколько строк для отладки
            logger.info(f"Первые строки данных:\n{self.df.head()}")
            logger.info(f"Столбцы: {self.df.columns.tolist()}")

            return self.df
        except Exception as e:
            logger.error(f"Ошибка при загрузке Excel файла: {e!s}")
            raise

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
            logger.error(f"Ошибка при получении классов: {e!s}")
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
            logger.error(f"Ошибка при получении атрибутов класса {class_id}: {e!s}")
            return []

    async def build_object_hierarchy(self) -> List[Dict[str, Any]]:
        """
        Строит иерархию объектов из загруженных данных Excel.

        Returns:
            Список объектов с атрибутами и иерархией
        """
        if self.df is None:
            await self.load_excel()

        # Загружаем классы из Neosintez, если еще не загружены
        if not self.classes:
            await self.load_neosintez_classes()

        # Получаем названия колонок
        if len(self.df.columns) < 3:
            logger.error(
                "В файле должно быть не менее трех колонок: Имя, Класс, Родитель"
            )
            return []

        # Предполагаем, что первые три колонки - это Имя, Класс, Родитель
        name_col = self.df.columns[0]
        class_col = self.df.columns[1]
        parent_col = self.df.columns[2]

        logger.info(
            f"Используем колонки: Имя={name_col}, Класс={class_col}, Родитель={parent_col}"
        )

        # Строим иерархию объектов
        objects = []
        object_dict = {}  # Словарь объектов по имени для быстрого поиска

        # Проходим по всем строкам DataFrame
        for idx, row in self.df.iterrows():
            name = row[name_col]
            class_name = row[class_col]
            parent_name = row[parent_col]

            if pd.isna(name) or pd.isna(class_name):
                logger.warning(f"Пропуск строки {idx}: пустое имя или класс")
                continue

            # Проверяем, есть ли класс в Neosintez
            class_id = None
            entity_class = None

            # Пробуем найти класс по имени
            if class_name in self.classes:
                entity_class = self.classes[class_name]
                class_id = entity_class.Id
            else:
                # Если точное совпадение не найдено, ищем частичное совпадение
                for existing_class_name, entity_class_obj in self.classes.items():
                    if class_name.lower() in existing_class_name.lower():
                        entity_class = entity_class_obj
                        class_id = entity_class.Id
                        logger.info(
                            f"Для класса '{class_name}' найдено частичное совпадение: '{existing_class_name}'"
                        )
                        break

            if class_id is None:
                logger.warning(
                    f"Класс '{class_name}' не найден в Neosintez. Пропуск строки {idx}."
                )
                continue

            # Создаем временный ID для объекта
            temp_id = f"row_{idx}"

            # Определяем родителя объекта
            parent_id = None
            if pd.isna(parent_name):
                parent_id = (
                    self.target_object_id
                )  # Если родитель не указан, используем корневой объект
            else:
                # Ищем родителя по имени в уже обработанных объектах
                parent_found = False
                for obj in objects:
                    if obj["name"] == parent_name:
                        parent_id = obj["id"]
                        parent_found = True
                        break

                if not parent_found:
                    logger.warning(
                        f"Родитель '{parent_name}' для объекта '{name}' не найден. Используем корневой объект."
                    )
                    parent_id = self.target_object_id

            # Создаем объект
            obj = {
                "id": temp_id,
                "name": name,
                "class_id": str(class_id),
                "class_name": class_name,
                "parent_id": parent_id,
                "row_index": idx,
                "attributes": {},
            }

            # Добавляем атрибуты из остальных колонок
            for col_name in self.df.columns[
                3:
            ]:  # Пропускаем первые три колонки (Имя, Класс, Родитель)
                value = row[col_name]
                if not pd.isna(value):
                    obj["attributes"][col_name] = value
                    logger.debug(
                        f"Добавлен атрибут '{col_name}' = '{value}' для объекта '{name}'"
                    )

            # Добавляем объект в список и словарь
            objects.append(obj)
            object_dict[name] = obj

        # Выводим информацию о построенной иерархии
        logger.info(f"Построена иерархия из {len(objects)} объектов")
        for obj in objects:
            attrs_info = ", ".join([f"{k}: {v}" for k, v in obj["attributes"].items()])
            logger.info(
                f"Объект: '{obj['name']}' (ID: {obj['id']}, Класс: {obj['class_name']}, "
                f"Родитель: {obj['parent_id']}, Атрибуты: {attrs_info})"
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

        # Создаем объекты, сохраняя порядок для правильной иерархии
        for obj in sorted(objects, key=lambda x: x["row_index"]):
            try:
                # Если родитель - временный ID, заменяем на реальный из созданных объектов
                parent_id = obj["parent_id"]
                if parent_id in created_objects:
                    parent_id = created_objects[parent_id]

                logger.info(
                    f"Создание объекта '{obj['name']}' класса '{obj['class_name']}' с родителем {parent_id}"
                )

                # Создаем данные для запроса
                data = {
                    "Name": obj["name"],
                    "Entity": {"Id": obj["class_id"], "Name": obj["class_name"]},
                    # Обязательные поля для WioObjectNode
                    "IsActualVersion": True,
                    "Version": 1,
                    "VersionTimestamp": "2023-01-01T00:00:00Z",
                }

                # Добавляем описание, если есть
                if "Описание" in obj["attributes"]:
                    data["Description"] = obj["attributes"]["Описание"]

                # Вызываем API для создания объекта
                try:
                    created_id = await self.client.objects.create(
                        parent_id=parent_id, data=data
                    )

                    # Сохраняем соответствие временного ID и реального ID в Neosintez
                    created_objects[obj["id"]] = created_id

                    # Добавляем информацию о созданном объекте в результат
                    obj["neosintez_id"] = created_id
                    result.append(obj)

                    logger.info(
                        f"Объект '{obj['name']}' создан успешно. ID: {created_id}"
                    )

                    # Устанавливаем атрибуты объекта, если они есть
                    if obj["attributes"]:
                        await self.set_object_attributes(created_id, obj["attributes"])

                except Exception as e:
                    logger.error(
                        f"Ошибка при создании объекта '{obj['name']}': {e!s}"
                    )

            except Exception as e:
                logger.error(
                    f"Общая ошибка при обработке объекта '{obj['name']}': {e!s}"
                )

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

            # Формируем словарь атрибутов для обновления
            attributes_data = {}

            for attr_name, attr_value in attributes.items():
                # Пропускаем описание, так как оно уже установлено при создании объекта
                if attr_name == "Описание":
                    continue

                # Ищем атрибут по имени
                attr_id = None
                for class_attr in class_attributes:
                    if class_attr.Name == attr_name:
                        attr_id = class_attr.Id
                        break

                if attr_id:
                    # Добавляем атрибут в словарь для обновления
                    attributes_data[str(attr_id)] = {"Value": attr_value}
                    logger.info(
                        f"Атрибут '{attr_name}' (ID: {attr_id}) будет установлен в '{attr_value}'"
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
                f"Ошибка при установке атрибутов объекта {object_id}: {e!s}"
            )
            return False

    async def verify_created_objects(
        self, created_objects: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Проверяет наличие созданных объектов.

        Args:
            created_objects: Список созданных объектов

        Returns:
            Dict[str, Any]: Результаты проверки
        """
        logger.info("Проверка наличия созданных объектов")

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
                        f"Объект не найден: {obj_name} (ID: {obj_id}), ошибка: {e!s}"
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
            "columns": list(self.df.columns),
            "data_sample": [],
        }

        # Добавляем примеры данных (до 5 строк с данными)
        for idx, row in self.df.head(5).iterrows():
            result["data_sample"].append(row.to_dict())

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
        await self.load_neosintez_classes()

        # Строим иерархию объектов
        objects = await self.build_object_hierarchy()

        # В тестовом режиме не создаем объекты, а только выводим информацию
        created_objects = []
        if test_mode:
            logger.info("Тестовый режим: объекты не создаются в Neosintez")
        else:
            # Создаем объекты в Neosintez
            created_objects = await self.create_objects_in_neosintez(objects)
            logger.info(f"Создано {len(created_objects)} объектов в Neosintez")

            # Проверяем созданные объекты
            verification_results = await self.verify_created_objects(created_objects)
            logger.info(
                f"Результаты верификации импорта: найдено {verification_results['found_objects']} из {verification_results['total_objects']} объектов"
            )

        # Собираем результаты импорта
        result = {
            "test_mode": test_mode,
            "excel_structure": await self.test_excel_structure(),
            "objects_hierarchy": objects,
            "created_objects": created_objects,
        }

        # Добавляем результаты верификации, если она была выполнена
        if not test_mode and created_objects:
            result["verification_results"] = await self.verify_created_objects(
                created_objects
            )

        return result


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
            default="objects_to_import.xlsx",
            help="Имя Excel файла в папке data (по умолчанию: objects_to_import.xlsx)",
        )
        parser.add_argument(
            "--parent",
            default="a7928b22-5a25-f011-91dd-005056b6948b",
            help="ID родительского объекта в Neosintez",
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

        # ID родительского объекта в Neosintez
        target_object_id = args.parent

        # Режим работы
        test_mode = args.test
        mode_str = (
            "тестовый режим (без создания объектов)"
            if test_mode
            else "режим создания объектов"
        )

        logger.info(f"Запуск в режиме: {mode_str}")

        # Инициализация клиента API
        async with NeosintezClient(settings) as client:
            try:
                # Аутентификация
                logger.info("Попытка аутентификации...")
                token = await client.auth()
                logger.info(f"Получен токен: {token[:10]}...")

                # Создаем импортер
                importer = FixedExcelImporter(
                    client=client,
                    excel_path=excel_path,
                    target_object_id=target_object_id,
                )

                # Выполняем импорт
                result = await importer.process_import(test_mode=test_mode)

                # Сохраняем результат в файл для анализа
                result_file = (
                    "import_test_result.json" if test_mode else "import_result.json"
                )
                with open(
                    os.path.join("data", result_file), "w", encoding="utf-8"
                ) as f:
                    json.dump(result, f, ensure_ascii=False, indent=4, default=str)

                logger.info(f"Импорт завершен. Результат сохранен в data/{result_file}")

                # Выводим сводку об импорте
                classes_count = {}
                for obj in result["objects_hierarchy"]:
                    class_name = obj["class_name"]
                    if class_name not in classes_count:
                        classes_count[class_name] = 0
                    classes_count[class_name] += 1

                logger.info("Сводка по импортированным объектам:")
                for class_name, count in classes_count.items():
                    logger.info(f"  {class_name}: {count} объектов")

            except NeosintezAuthError as e:
                logger.error(f"Ошибка аутентификации: {e!s}")
            except NeosintezConnectionError as e:
                logger.error(f"Ошибка соединения: {e!s}")
            except Exception:
                logger.error(f"Неожиданная ошибка: {traceback.format_exc()}")
    except Exception:
        logger.error(f"Ошибка при инициализации: {traceback.format_exc()}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Прервано пользователем")
    except Exception:
        logger.error(f"Критическая ошибка: {traceback.format_exc()}")
        sys.exit(1)
