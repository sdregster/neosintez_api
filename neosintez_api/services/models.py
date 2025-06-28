"""
Модели данных для сервисного слоя.
"""

from typing import Any, Dict, Generic, List, TypeVar, Union
from uuid import UUID

from pydantic import BaseModel


# Определяем тип для динамических моделей
T = TypeVar("T", bound=BaseModel)


class CreateRequest(BaseModel, Generic[T]):
    """Запрос на создание одного объекта в массовой операции."""

    model: T
    class_id: str
    class_name: str
    attributes_meta: Dict[str, Any]
    parent_id: Union[str, UUID, None] = None


class BulkCreateResult(BaseModel, Generic[T]):
    """Результат массового создания объектов."""

    created_models: List[T] = []
    errors: List[str] = []
