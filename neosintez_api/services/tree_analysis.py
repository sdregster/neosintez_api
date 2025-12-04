"""
Сервисы и утилиты для анализа иерархии объектов (поиск пустующих веток).

Основная идея: для заданных корневых объектов определить, есть ли внутри
их поддеревьев «содержательные» объекты по настраиваемому критерию.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Awaitable, Callable, Collection, List, Optional, Sequence, Set, Tuple

from neosintez_api.core.exceptions import NeosintezAPIError


if TYPE_CHECKING:
    from neosintez_api.core.client import NeosintezClient
    from neosintez_api.models import NeoObject


logger = logging.getLogger("neosintez_api.services.tree_analysis")


NodePredicate = Callable[["NeoObject"], bool]


async def _walk_subtree_collect_empty(
    client: NeosintezClient,
    root_id: str,
    *,
    is_meaningful: Optional[NodePredicate],
    max_depth: Optional[int] = None,
) -> Tuple[bool, List[str]]:
    """
    Обходит поддерево от указанного корня и возвращает информацию о пустых узлах.

    Узел считается пустым, если в его поддереве (включая все уровни ниже)
    нет ни одного «содержательного» объекта по заданному предикату.

    Args:
        client: Клиент API Неосинтеза.
        root_id: Идентификатор корневого объекта.
        is_meaningful: Предикат, определяющий, является ли объект содержательным.
        max_depth: Максимальная глубина обхода (0 — только корень, None — без ограничения).

    Returns:
        Tuple[bool, List[str]]: Кортеж из:
            - has_meaningful: True, если в поддереве найден хотя бы один
              содержательный объект, иначе False.
            - empty_nodes: Список идентификаторов узлов, для которых их собственные
              поддеревья не содержат содержательных объектов.
    """
    effective_max_depth: int = max_depth if max_depth is not None else 1_000_000

    empty_nodes: List[str] = []

    async def _dfs(node_id: str, depth: int, node_obj: NeoObject | None) -> bool:
        """
        Рекурсивный обход в глубину.

        Returns:
            bool: True, если в поддереве от node_id есть содержательные объекты.
        """
        if depth > effective_max_depth:
            return False

        try:
            children = await client.objects.get_children(node_id)
        except NeosintezAPIError as exc:
            logger.warning("Ошибка API при получении дочерних объектов %s: %s", node_id, exc)
            return False
        except Exception as exc:  # noqa: BLE001
            logger.exception("Неожиданная ошибка при получении дочерних объектов %s: %s", node_id, exc)
            return False

        has_meaningful_here = False
        has_meaningful_in_children = False
        # Сначала проверяем текущий узел: если он сам «содержательный»,
        # он никогда не может считаться пустой веткой, даже без детей.
        if is_meaningful is not None and node_obj is not None and is_meaningful(node_obj):
            has_meaningful_here = True

        # Затем проверяем детей и их поддеревья
        if children:
            if is_meaningful is not None:
                for child in children:
                    if is_meaningful(child):
                        has_meaningful_here = True
                        break

            for child in children:
                child_has_meaningful = await _dfs(str(child.Id), depth + 1, child)
                if child_has_meaningful:
                    has_meaningful_in_children = True

        has_meaningful_total = has_meaningful_here or has_meaningful_in_children

        if not has_meaningful_total:
            empty_nodes.append(node_id)

        return has_meaningful_total

    # Для корня у нас нет объекта NeoObject (мы знаем только его ID),
    # поэтому node_obj передаём как None — корень будет оцениваться только
    # по своим дочерним объектам.
    has_meaningful_root = await _dfs(root_id, depth=0, node_obj=None)
    return has_meaningful_root, empty_nodes


def _build_meaningful_predicate(
    meaningful_class_ids: Optional[Collection[str]] = None,
) -> NodePredicate:
    """
    Строит предикат «содержательности» объекта.

    По умолчанию (если meaningful_class_ids не задан) любой встреченный
    объект в поддереве считается содержательным. Если список классов задан,
    то содержательными считаются только объекты с EntityId из этого списка.

    Args:
        meaningful_class_ids: Коллекция идентификаторов классов, которые
            считаются «содержательными».

    Returns:
        NodePredicate: Функция, принимающая NeoObject и возвращающая bool.
    """
    if meaningful_class_ids is None:

        def any_object(_: NeoObject) -> bool:
            return True

        return any_object

    class_id_set: Set[str] = {str(cid) for cid in meaningful_class_ids}

    def by_class_id(obj: NeoObject) -> bool:
        return str(obj.EntityId) in class_id_set

    return by_class_id


async def find_empty_subtrees(
    client: NeosintezClient,
    root_ids: Sequence[str],
    *,
    meaningful_class_ids: Optional[Collection[str]] = None,
    max_depth: Optional[int] = None,
    max_concurrent: int = 5,
) -> List[str]:
    """
    Находит все узлы в поддеревьях, которые не содержат «содержательных» объектов.

    Бизнес-смысл:
    - Вы передаёте массив корневых идентификаторов (например, верхние папки/узлы).
    - Для каждого корня обходится его поддерево через get_children.
    - Для каждого узла внутри поддерева проверяется, есть ли в нём или ниже
      хотя бы один «содержательный» объект (по предикату).
    - Если таких объектов нет, узел считается пустующей веткой и попадает
      в общий результирующий список.

    Args:
        client: Клиент API Неосинтеза.
        root_ids: Последовательность корневых идентификаторов для анализа.
        meaningful_class_ids: Необязательный список ID классов, которые считаются
            содержательными. Если None, то любой найденный объект считается содержательным.
        max_depth: Максимальная глубина обхода относительно корня. Если None — без ограничения.
        max_concurrent: Максимальное количество поддеревьев, анализируемых одновременно.

    Returns:
        List[str]: Список идентификаторов всех узлов (как совпадающих
        с переданными root_ids, так и внутренних), чьи поддеревья не
        содержат содержательных объектов.
    """
    if not root_ids:
        return []

    is_meaningful: NodePredicate = _build_meaningful_predicate(meaningful_class_ids)
    semaphore = asyncio.Semaphore(max_concurrent)
    empty_nodes: List[str] = []

    async def _collect_for_root(root_id: str) -> None:
        async with semaphore:
            try:
                _, local_empty_nodes = await _walk_subtree_collect_empty(
                    client=client,
                    root_id=root_id,
                    is_meaningful=is_meaningful,
                    max_depth=max_depth,
                )
            except Exception as exc:  # noqa: BLE001
                logger.error("Ошибка при анализе поддерева от корня %s: %s", root_id, exc)
                return

            empty_nodes.extend(local_empty_nodes)

    tasks: List[Awaitable[None]] = [_collect_for_root(root_id) for root_id in root_ids]
    await asyncio.gather(*tasks)

    # Убираем дубликаты, сохраняя порядок
    seen: Set[str] = set()
    unique_empty_nodes: List[str] = []
    for node_id in empty_nodes:
        if node_id not in seen:
            seen.add(node_id)
            unique_empty_nodes.append(node_id)

    # Если пустых узлов нет, можно сразу завершать
    if not unique_empty_nodes:
        return unique_empty_nodes

    # На этом этапе в unique_empty_nodes находятся все узлы, для которых
    # их собственные поддеревья не содержат содержательных объектов.
    # Однако среди них могут быть как верхние пустые ветки, так и их
    # дочерние пустые ветки. Для сценария «удалить структуру» обычно
    # интересны только верхнеуровневые пустые ветки, т.к. удаление
    # верхней автоматически удалит все вложенные.

    try:
        paths_map = await client.objects.get_paths_batch(unique_empty_nodes)
    except Exception as exc:  # noqa: BLE001
        logger.error("Не удалось получить пути для пустых узлов: %s", exc)
        # В случае ошибки возвращаем полный список, чтобы не терять данные
        return unique_empty_nodes

    empty_set: Set[str] = set(unique_empty_nodes)
    top_level_empty_nodes: List[str] = []

    for node_id in unique_empty_nodes:
        ancestors = paths_map.get(node_id) or []
        # Если среди предков (кроме самого узла) есть другой пустой узел,
        # значит текущий узел вложен в более высокую пустую ветку и его
        # можно опустить в выдаче.
        has_empty_ancestor = any(
            (str(ancestor.Id) in empty_set) and (str(ancestor.Id) != node_id) for ancestor in ancestors
        )
        if not has_empty_ancestor:
            top_level_empty_nodes.append(node_id)

    return top_level_empty_nodes
