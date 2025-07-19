"""
Скрипт для оптимизированной очистки корзины Неосинтеза

Назначение:
    Данный скрипт реализует стратегию безопасного удаления объектов из корзины
    Неосинтеза с минимальным влиянием на производительность системы.

Проблема:
    Hard удаление объектов в Неосинтезе является ресурсоемкой операцией,
    которая блокирует деятельность системы и может привести к временной
    недоступности сервиса. Это особенно критично в рабочее время.

Решение:
    Используется подход soft удаления - объекты перемещаются в корзину
    (условный отдельный объект) вместо немедленного физического удаления.
    Данный скрипт выполняет контролируемое hard удаление в оптимальное время.

Алгоритм работы:
    1. Выбор одного объекта верхнего уровня иерархии в корзине
    2. Перемещение всех остальных объектов верхнего уровня в выбранный объект
    3. Hard удаление объекта верхнего уровня с его содержимым
    4. Повторение процесса для следующих групп объектов

Параметры:
    - MAX_OBJECTS_PER_GROUP: максимальное количество объектов в группе (по умолчанию: 100)
    - IMPORTANCE_MARKERS: список маркеров важности для исключения объектов из обработки
    - Можно настроить для оптимизации под конкретную систему

Маркеры важности:
    - "Не удалять", "НЕ УДАЛЯТЬ", "не удалять" - явные запреты удаления
    - "!" - маркер важности (любой объект с восклицательным знаком считается важным)
    - Регистронезависимый поиск маркеров

Безопасность:
    - Объекты с названиями, содержащими маркеры важности,
      автоматически исключаются из процесса очистки
    - Валидация входных данных для предотвращения ошибок
    - Подробное логирование процесса исключения объектов

Преимущества:
    - Прогнозируемое время выполнения операций
    - Минимальное влияние на производительность системы
    - Возможность выполнения в нерабочее время (ночные часы, выходные)
    - Отсутствие блокировки деятельности пользователей
    - Контролируемая нагрузка на систему
    - Учет реального количества объектов (включая вложенные)

Использование:
    Рекомендуется запускать в периоды минимальной нагрузки на систему
    (например, в ночные часы выходных дней) для обеспечения стабильной работы.

Настройка таймаутов:
    Для объектов с большим количеством вложенных элементов может потребоваться
    увеличение таймаутов через переменные окружения:

    - NEOSINTEZ_TIMEOUT=60 (базовый таймаут, 10-3600 секунд)
    - NEOSINTEZ_DELETE_TIMEOUT=300 (5 минут для удаления, 60-3600 секунд)
    - NEOSINTEZ_LARGE_OPERATION_TIMEOUT=600 (10 минут для больших операций, 300-7200 секунд)

    Пример запуска с увеличенным таймаутом:
    NEOSINTEZ_DELETE_TIMEOUT=600 python scripts/trashcan_cleanup.py

    Рекомендации по таймаутам:
    - Для объектов с <1000 вложенных элементов: 300 секунд
    - Для объектов с 1000-5000 вложенных элементов: 600 секунд
    - Для объектов с >5000 вложенных элементов: 900 секунд
"""

import asyncio
import logging
import traceback
from typing import Any, Dict, List, Optional

from neosintez_api.config import NeosintezConfig
from neosintez_api.core.client import NeosintezClient
from neosintez_api.core.exceptions import NeosintezAPIError
from neosintez_api.services import ObjectService


# Настройка логирования
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Маркеры важности объектов (не удалять)
IMPORTANCE_MARKERS = [
    "Не удалять",  # Явный запрет удаления
    "НЕ УДАЛЯТЬ",  # Вариант с заглавными буквами
    "не удалять",  # Вариант с маленькими буквами
    "!",  # Маркер важности (любой объект с ! считается важным)
]


class TrashcanCleanupService:
    """
    Сервис для оптимизированной очистки корзины Неосинтеза.
    """

    def __init__(self, client: NeosintezClient, max_objects_per_group: int = 100, exclude_keywords: Optional[List[str]] = None):
        """
        Инициализирует сервис очистки корзины.

        Args:
            client: Клиент API Неосинтеза
            max_objects_per_group: Максимальное количество объектов в группе (уменьшено с 500 до 100)
            exclude_keywords: Список ключевых слов для исключения объектов (регистронезависимый поиск)
        """
        self.client = client
        self.object_service: ObjectService = ObjectService(client)
        self.max_objects_per_group = max_objects_per_group

        # Валидация и установка маркеров важности
        if exclude_keywords is None:
            self.exclude_keywords = IMPORTANCE_MARKERS
        else:
            # Валидация входных данных
            if not isinstance(exclude_keywords, list):
                raise ValueError("exclude_keywords должен быть списком строк")
            if not all(isinstance(kw, str) and kw.strip() for kw in exclude_keywords):
                raise ValueError("Все элементы exclude_keywords должны быть непустыми строками")
            self.exclude_keywords = exclude_keywords

        logger.info(f"Используются маркеры важности: {', '.join(self.exclude_keywords)}")

        self.settings = NeosintezConfig()

        if not self.settings.trash_folder_id:
            raise ValueError("Не задан ID папки корзины в конфигурации")

    def _should_exclude_object(self, object_name: str) -> bool:
        """
        Проверяет, должен ли объект быть исключен из обработки.

        Args:
            object_name: Название объекта

        Returns:
            bool: True, если объект должен быть исключен
        """
        object_name_lower = object_name.lower()
        for keyword in self.exclude_keywords:
            if keyword.lower() in object_name_lower:
                logger.info(f"Объект '{object_name}' исключен по маркеру важности '{keyword}'")
                return True
        return False

    async def get_object_total_count(self, object_id: str) -> int:
        """
        Получает общее количество объектов с учетом зависимостей.

        Args:
            object_id: ID объекта

        Returns:
            int: Общее количество объектов (включая вложенные)
        """
        try:
            dependencies = await self.client.objects.get_dependencies(object_id)
            return dependencies.get("Objects", 0) + 1  # +1 для самого объекта
        except Exception as e:
            logger.warning(f"Не удалось получить зависимости для объекта {object_id}: {e}")
            return 1  # Возвращаем 1, если не удалось получить зависимости

    async def get_top_level_objects(self) -> List[Any]:
        """
        Получает объекты верхнего уровня в корзине с фильтрацией по ключевым словам.

        Returns:
            List[dict]: Список объектов верхнего уровня (исключены объекты с ключевыми словами)
        """
        logger.info("Получение объектов верхнего уровня в корзине...")

        try:
            children = await self.client.objects.get_children(self.settings.trash_folder_id)
            logger.info(f"Найдено {len(children)} объектов верхнего уровня в корзине")

            # Фильтруем объекты по ключевым словам
            filtered_objects = []
            excluded_objects = []

            for obj in children:
                if self._should_exclude_object(obj.Name):
                    excluded_objects.append(obj.Name)
                else:
                    filtered_objects.append(obj)

            if excluded_objects:
                if len(excluded_objects) <= 3:
                    # Если исключенных объектов мало, показываем все
                    excluded_list = ", ".join(excluded_objects)
                    logger.info(f"Исключено {len(excluded_objects)} объектов с ключевыми словами: {excluded_list}")
                else:
                    # Если много объектов, показываем первые 3 и общее количество
                    first_three = ", ".join(excluded_objects[:3])
                    remaining_count = len(excluded_objects) - 3
                    logger.info(
                        f"Исключено {len(excluded_objects)} объектов с ключевыми словами: {first_three} и ещё {remaining_count} других"
                    )

            logger.info(f"Для обработки доступно {len(filtered_objects)} объектов")
            return filtered_objects

        except NeosintezAPIError as e:
            logger.error(f"Ошибка при получении объектов корзины: {e}")
            raise

    async def group_objects(self, objects: List[Any]) -> List[List[Any]]:
        """
        Группирует объекты по размеру группы с учетом реального количества объектов.

        Args:
            objects: Список объектов для группировки

        Returns:
            List[List[dict]]: Список групп объектов
        """
        logger.info(f"Группировка {len(objects)} объектов верхнего уровня...")

        groups: List[List[Any]] = []
        current_group: List[Any] = []
        current_group_total_objects = 0

        for obj in objects:
            # Получаем общее количество объектов для текущего объекта
            obj_total_count = await self.get_object_total_count(str(obj.Id))

            # Проверяем, не превысит ли добавление этого объекта лимит группы
            if current_group_total_objects + obj_total_count > self.max_objects_per_group and current_group:
                # Если превысит, завершаем текущую группу
                groups.append(current_group)
                logger.info(
                    f"Создана группа из {len(current_group)} объектов верхнего уровня (всего ~{current_group_total_objects} объектов)"
                )
                current_group = [obj]
                current_group_total_objects = obj_total_count
            else:
                # Добавляем объект в текущую группу
                current_group.append(obj)
                current_group_total_objects += obj_total_count

        # Добавляем последнюю группу, если она не пустая
        if current_group:
            groups.append(current_group)
            logger.info(
                f"Создана группа из {len(current_group)} объектов верхнего уровня (всего ~{current_group_total_objects} объектов)"
            )

        logger.info(f"Создано {len(groups)} групп объектов")
        return groups

    async def process_group(self, group: List[Any]) -> bool:
        """
        Обрабатывает одну группу объектов.

        Args:
            group: Группа объектов для обработки

        Returns:
            bool: True, если группа успешно обработана
        """
        if not group:
            logger.warning("Получена пустая группа для обработки")
            return True

        logger.info(f"Обработка группы из {len(group)} объектов")

        try:
            # Выбираем первый объект как контейнер для остальных
            container_object = group[0]
            objects_to_move = group[1:]

            logger.info(f"Выбран объект-контейнер: {container_object.Name} (ID: {container_object.Id})")
            logger.info(f"Перемещение {len(objects_to_move)} объектов в контейнер...")

            # Перемещаем все объекты в контейнер параллельно
            if objects_to_move:
                object_ids = [str(obj.Id) for obj in objects_to_move]
                await self.client.objects.move_batch(object_ids, str(container_object.Id))
                logger.info(f"Все {len(objects_to_move)} объектов успешно перемещены в контейнер параллельно")
            else:
                logger.info("Нет объектов для перемещения")

            # Выполняем hard удаление контейнера со всем содержимым
            logger.info(f"Выполнение hard удаления контейнера {container_object.Name}...")

            # Используем увеличенный таймаут для удаления
            try:
                logger.info(
                    f"Начинаем удаление контейнера {container_object.Name} (это может занять несколько минут)..."
                )
                await self.client.objects.delete(str(container_object.Id))
                logger.info(f"✅ Контейнер {container_object.Name} успешно удален")
            except Exception as e:
                logger.error(f"❌ Ошибка при удалении контейнера {container_object.Name}: {e}")
                logger.error("Возможные причины:")
                logger.error("  - Слишком много вложенных объектов (>10,000)")
                logger.error("  - Сетевые проблемы или медленное соединение")
                logger.error("  - Недостаточный таймаут (попробуйте увеличить NEOSINTEZ_DELETE_TIMEOUT)")
                return False

            logger.info(f"Группа из {len(group)} объектов успешно обработана")
            return True

        except NeosintezAPIError as e:
            logger.error(f"Ошибка API при обработке группы: {e}")
            return False
        except Exception as e:
            logger.error(f"Неожиданная ошибка при обработке группы: {e}")
            return False

    async def cleanup_trashcan(self) -> Dict[str, Any]:
        """
        Выполняет полную очистку корзины.

        Returns:
            dict: Результат очистки с статистикой
        """
        logger.info("Начало процесса очистки корзины")

        result: Dict[str, Any] = {"total_objects": 0, "processed_groups": 0, "successful_groups": 0, "failed_groups": 0, "errors": []}

        try:
            # Получаем объекты верхнего уровня
            top_level_objects = await self.get_top_level_objects()
            result["total_objects"] = len(top_level_objects)

            if not top_level_objects:
                logger.info("Корзина пуста, очистка не требуется")
                return result

            # Предварительная оценка нагрузки
            logger.info("Оценка общей нагрузки...")
            total_estimated_objects = 0
            for obj in top_level_objects:
                obj_count = await self.get_object_total_count(str(obj.Id))
                total_estimated_objects += obj_count
                logger.info(f"Объект '{obj.Name}': ~{obj_count} объектов")

            logger.info(f"Общая оценка: ~{total_estimated_objects} объектов для удаления")

            if total_estimated_objects > 10000:
                logger.warning(f"⚠️ ВНИМАНИЕ: Большая нагрузка! Предстоит удалить ~{total_estimated_objects} объектов")
                logger.warning("Рекомендуется запускать в нерабочее время")

            # Группируем объекты
            groups = await self.group_objects(top_level_objects)

            # Обрабатываем каждую группу
            for i, group in enumerate(groups, 1):
                logger.info(f"Обработка группы {i}/{len(groups)}")

                success = await self.process_group(group)
                result["processed_groups"] += 1

                if success:
                    result["successful_groups"] += 1
                else:
                    result["failed_groups"] += 1
                    result["errors"].append(f"Ошибка при обработке группы {i}")

            logger.info("Процесс очистки корзины завершен")
            return result

        except Exception as e:
            logger.error(f"Критическая ошибка при очистке корзины: {e}")
            result["errors"].append(f"Критическая ошибка: {e}")
            return result


async def main() -> None:
    """
    Основная функция для выполнения очистки корзины.
    """
    logger.info("--- Запуск скрипта очистки корзины Неосинтеза ---")

    # Настройка с возможностью переопределения таймаутов
    settings = NeosintezConfig()

    # Логируем настройки таймаутов
    logger.info(f"Таймаут для обычных операций: {settings.timeout} секунд")
    logger.info(f"Таймаут для удаления: {settings.delete_timeout} секунд")
    logger.info(f"Таймаут для больших операций: {settings.large_operation_timeout} секунд")

    # Проверяем корректность настроек
    if not settings.trash_folder_id:
        logger.error("❌ Не задан ID папки корзины в настройках!")
        logger.error("Установите переменную NEOSINTEZ_TRASH_FOLDER_ID в .env файле")
        return

    client = NeosintezClient(settings)

    try:
        # Создаем сервис очистки с настройкой исключений
        cleanup_service = TrashcanCleanupService(client, max_objects_per_group=100)

        # Выполняем очистку
        result = await cleanup_service.cleanup_trashcan()

        # Выводим результаты
        logger.info("\n--- Результаты очистки корзины ---")
        logger.info(f"Всего объектов: {result['total_objects']}")
        logger.info(f"Обработано групп: {result['processed_groups']}")
        logger.info(f"Успешных групп: {result['successful_groups']}")
        logger.info(f"Неудачных групп: {result['failed_groups']}")

        if result["errors"]:
            logger.error("Ошибки при очистке:")
            for error in result["errors"]:
                logger.error(f"  - {error}")

        if result["successful_groups"] == result["processed_groups"]:
            logger.info("✅ Очистка корзины завершена успешно!")
        else:
            logger.warning("⚠️ Очистка завершена с ошибками")

    except NeosintezAPIError as e:
        logger.error(f"❌ Ошибка API Неосинтез: {e}")
        logger.error("\nВозможные причины:")
        logger.error("  - Неверные настройки подключения")
        logger.error("  - Отсутствие прав доступа к корзине")
        logger.error("  - Проблемы с сетевым соединением")
        logger.error("  - Недостаточный таймаут для операции")
        logger.error("\nРекомендации:")
        logger.error("  - Проверьте настройки в .env файле")
        logger.error("  - Увеличьте таймауты через переменные окружения")
        logger.error("  - Убедитесь в наличии прав доступа к системе")

    except Exception as e:
        logger.error(f"❌ Неожиданная ошибка: {e}")
        logger.error("\n--- Полный Traceback ---")
        traceback.print_exc()

    finally:
        await client.close()
        logger.info("Соединение закрыто.")


if __name__ == "__main__":
    asyncio.run(main())
