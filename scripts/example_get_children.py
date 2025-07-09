"""
Пример использования метода get_children для работы с иерархией объектов в Неосинтезе.
Демонстрирует получение дочерних объектов и обход иерархического дерева.
"""

import asyncio
import traceback

from neosintez_api.config import NeosintezConfig
from neosintez_api.core.client import NeosintezClient
from neosintez_api.core.exceptions import NeosintezAPIError
from neosintez_api.services import ClassService


async def get_children_info(
    client: NeosintezClient, parent_id: str, max_depth: int = 2, current_depth: int = 0
) -> None:
    """
    Рекурсивно получает информацию о дочерних объектах с ограничением глубины.

    Args:
        client: Клиент API Неосинтеза
        parent_id: ID родительского объекта
        max_depth: Максимальная глубина обхода
        current_depth: Текущая глубина (для отступов)
    """
    if current_depth >= max_depth:
        return

    indent = "  " * current_depth

    try:
        # Получаем дочерние объекты
        children = await client.objects.get_children(parent_id)

        if not children:
            print(f"{indent}└─ (нет дочерних объектов)")
            return

        print(f"{indent}└─ Найдено {len(children)} дочерних объектов:")

        # Показываем первые 5 дочерних объектов
        for i, child in enumerate(children[:5]):
            child_marker = "├─" if i < min(4, len(children) - 1) else "└─"
            print(f"{indent}  {child_marker} [{i + 1}] {child.Name}")
            print(f"{indent}     ID: {child.Id}")
            print(f"{indent}     EntityId: {child.EntityId}")

            # Рекурсивно обходим дочерние объекты (ограничиваем глубину)
            if current_depth < max_depth - 1:
                await get_children_info(client, str(child.Id), max_depth, current_depth + 1)

        if len(children) > 5:
            print(f"{indent}  └─ ... и еще {len(children) - 5} объектов")

    except NeosintezAPIError as e:
        print(f"{indent}└─ ❌ Ошибка API при получении дочерних объектов: {e}")
    except Exception as e:
        print(f"{indent}└─ ❌ Неожиданная ошибка: {e}")


async def demonstrate_children_with_class_info(client: NeosintezClient, parent_id: str) -> None:
    """
    Демонстрирует получение дочерних объектов с дополнительной информацией о классах.

    Args:
        client: Клиент API Неосинтеза
        parent_id: ID родительского объекта
    """
    print("\n▶️ Демонстрация получения дочерних объектов с информацией о классах...")

    try:
        children = await client.objects.get_children(parent_id)

        if not children:
            print("  └─ Дочерние объекты не найдены")
            return

        # Создаем сервис для работы с классами
        class_service = ClassService(client)

        # Группируем объекты по классам
        class_groups = {}
        for child in children:
            class_id = str(child.EntityId)
            if class_id not in class_groups:
                class_groups[class_id] = []
            class_groups[class_id].append(child)

        print(f"  └─ Дочерние объекты сгруппированы по {len(class_groups)} классам:")

        for class_id, objects in class_groups.items():
            try:
                # Получаем информацию о классе
                class_info = await class_service.get_by_id(class_id)
                class_name = class_info.Name if class_info else "Неизвестный класс"

                print(f"\n    📁 Класс: {class_name} (ID: {class_id})")
                print(f"       Количество объектов: {len(objects)}")

                # Показываем первые 3 объекта этого класса
                for i, obj in enumerate(objects[:3]):
                    marker = "├─" if i < min(2, len(objects) - 1) else "└─"
                    print(f"       {marker} {obj.Name}")

                if len(objects) > 3:
                    print(f"       └─ ... и еще {len(objects) - 3} объектов этого класса")

            except Exception as e:
                print(f"    ❌ Ошибка получения информации о классе {class_id}: {e}")

    except Exception as e:
        print(f"  ❌ Ошибка при группировке по классам: {e}")


async def main():
    """
    Основной сценарий демонстрации работы с методом get_children:
    1. Простое получение дочерних объектов
    2. Иерархический обход с ограничением глубины
    3. Группировка по классам с дополнительной информацией
    """
    # ID родительского объекта для тестирования
    # Используем тот же ID, что тестировали ранее
    test_parent_id = "46303b37-eefd-ee11-91a4-005056b6948b"

    print("--- Демонстрация работы с методом get_children ---")
    print(f"Родительский объект ID: {test_parent_id}\n")

    settings = NeosintezConfig()
    client = NeosintezClient(settings)

    try:
        # --- Этап 1: Простое получение дочерних объектов ---
        print("▶️ Этап 1: Простое получение дочерних объектов...")

        children = await client.objects.get_children(test_parent_id)

        print(f"✅ Найдено {len(children)} дочерних объектов")

        if children:
            print("\n📋 Первые 5 дочерних объектов:")
            for i, child in enumerate(children[:5]):
                print(f"  {i + 1}. {child.Name}")
                print(f"     ID: {child.Id}")
                print(f"     EntityId: {child.EntityId}")
                print()

        # --- Этап 2: Иерархический обход ---
        print("\n▶️ Этап 2: Иерархический обход дерева объектов (глубина: 2 уровня)...")

        print(f"🌳 Структура дерева от объекта {test_parent_id}:")
        await get_children_info(client, test_parent_id, max_depth=2)

        # --- Этап 3: Группировка по классам ---
        await demonstrate_children_with_class_info(client, test_parent_id)

        print("\n🎉 Демонстрация метода get_children завершена успешно!")

    except NeosintezAPIError as e:
        print(f"\n❌ Ошибка API Неосинтез: {e}")
        print("\nВозможные причины:")
        print("  - Объект с указанным ID не существует")
        print("  - У пользователя нет прав на просмотр объекта или его дочерних элементов")
        print("  - Проблемы с сетевым соединением")

    except Exception as e:
        print(f"\n❌ Неожиданная ошибка: {e}")
        print("\n--- Полный Traceback ---")
        traceback.print_exc()

    finally:
        await client.close()
        print("\nСоединение закрыто.")


if __name__ == "__main__":
    asyncio.run(main())
