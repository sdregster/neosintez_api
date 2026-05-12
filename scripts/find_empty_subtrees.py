"""
Скрипт для поиска «пустующих» веток иерархии объектов в Неосинтезе.

Идея:
- На вход подаётся список корневых идентификаторов (например, верхние папки).
- Для каждого корня анализируется его поддерево через метод get_children.
- Если внутри поддерева не найдено ни одного «содержательного» объекта,
  такой корень считается пустующей веткой и попадает в результирующий список.

По умолчанию любой найденный объект считается «содержательным». При необходимости
можно ограничить анализ только объектами определённых классов.
"""

from __future__ import annotations

import asyncio
from typing import List, Optional

from neosintez_api.config import NeosintezConfig
from neosintez_api.core.client import NeosintezClient
from neosintez_api.core.exceptions import NeosintezAPIError
from neosintez_api.services.tree_analysis import find_empty_subtrees


async def run_analysis(
    client: NeosintezClient,
    root_ids: List[str],
    meaningful_class_ids: Optional[List[str]] = None,
) -> None:
    """
    Запускает анализ поддеревьев и печатает пустующие ветки.

    Args:
        client: Инициализированный клиент API Неосинтеза.
        root_ids: Список корневых идентификаторов для анализа.
        meaningful_class_ids: Необязательный список ID классов, которые
            считаются «содержательными» объектами. Если не указан, любая
            найденная сущность будет считаться содержательной.
    """
    if not root_ids:
        print("⚠️ Список корневых идентификаторов пуст — нечего анализировать.")
        return

    print("--- Анализ пустующих веток иерархии объектов ---")
    print(f"Количество корневых узлов для проверки: {len(root_ids)}")

    if meaningful_class_ids:
        print("Будут учитываться только объекты следующих классов (EntityId):")
        for cid in meaningful_class_ids:
            print(f"  - {cid}")
    else:
        print("Любой найденный объект в поддереве считается содержательным.")

    try:
        empty_roots = await find_empty_subtrees(
            client=client,
            root_ids=root_ids,
            meaningful_class_ids=meaningful_class_ids,
        )
    except NeosintezAPIError as exc:
        print(f"❌ Ошибка API при анализе пустующих веток: {exc}")
        return
    except Exception as exc:  # noqa: BLE001
        print(f"❌ Неожиданная ошибка при анализе пустующих веток: {exc}")
        return

    print("\n=== Результаты анализа ===")
    if not empty_roots:
        print("✅ Пустующих веток не найдено.")
        return

    print(f"Найдено пустующих веток: {len(empty_roots)}")
    for idx, root_id in enumerate(empty_roots, start=1):
        print(f"  {idx}. {root_id}")


async def main() -> None:
    """
    Точка входа для скрипта.

    Здесь инициализируется конфигурация и клиент, задаётся список
    корневых идентификаторов и опциональный список «содержательных» классов.
    """
    settings = NeosintezConfig()
    settings.base_url = "https://operation.irkutskoil.ru/"
    client = NeosintezClient(settings)

    # Пример: список корневых идентификаторов для анализа.
    # Значения следует заменить на реальные ID из вашей иерархии.
    # root_ids: List[str] = ["4fe5e4a5-9ece-f011-91fd-005056b6948b"]
    root_ids: List[str] = ["7b888f47-89c3-f011-91fb-005056b6948b"]

    # Необязательный список классов, которые считаются «содержательными».
    # Если оставить пустым (None), любой найденный объект в поддереве
    # будет считаться содержательным.
    meaningful_class_ids: Optional[List[str]] = ["379086c1-575b-ed11-914d-005056b6948b"]

    try:
        await run_analysis(client, root_ids=root_ids, meaningful_class_ids=meaningful_class_ids)
    finally:
        await client.close()
        print("\nСоединение с API закрыто.")


if __name__ == "__main__":
    asyncio.run(main())
