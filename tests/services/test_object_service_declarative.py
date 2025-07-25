import uuid

import pytest
import pytest_asyncio
from pydantic import Field

from neosintez_api import NeosintezClient
from neosintez_api.config import settings
from neosintez_api.core.exceptions import NeosintezAPIError
from neosintez_api.models import NeosintezBaseModel
from neosintez_api.services.object_service import ObjectService


# 1. Определение тестовой декларативной модели
class StroykaTestModel(NeosintezBaseModel):
    """Тестовая модель для объекта 'Объект капитальных вложений'."""

    class Neosintez:
        class_name = "Объект капитальных вложений"

    name: str = Field(..., description="Имя объекта")
    mvz: str = Field(..., alias="МВЗ")
    id_stroyki_adep: int = Field(..., alias="ID стройки Адепт")
    ir_adep_primavera: str = Field(..., alias="ИР Адепт - Primavera")


@pytest_asyncio.fixture
async def object_service(real_client: NeosintezClient) -> ObjectService:
    """Фикстура для создания ObjectService."""
    return ObjectService(real_client)


@pytest.mark.asyncio
async def test_declarative_create_read_delete_cycle(object_service: ObjectService, real_client: NeosintezClient):
    """
    Тестирует полный цикл: создание, чтение и удаление объекта
    с использованием декларативной модели.
    """
    object_to_delete_id = None
    try:
        # 2. Создание экземпляра модели с уникальным именем
        unique_name = f"Тестовая стройка {uuid.uuid4()}"
        stroyka_instance = StroykaTestModel(
            name=unique_name,
            mvz="МВЗ_FOR_TEST",
            id_stroyki_adep=112233,
            ir_adep_primavera="Да",
        )

        # 3. Создание объекта
        created_object = await object_service.create(stroyka_instance, parent_id=settings.test_folder_id)
        object_to_delete_id = created_object._id

        # 4. Проверки после создания
        assert created_object._id is not None
        assert created_object.ir_adep_primavera == "Да"
        assert created_object.name == unique_name

        # 5. Чтение после записи (Read-after-write)
        # Получаем сырые данные напрямую из API, чтобы быть уверенными
        raw_read_data = await real_client.objects.get_by_id(created_object._id)

        assert raw_read_data["Name"] == unique_name

        # Находим ID атрибута "ИР Адепт - Primavera"
        class_meta = await object_service.class_service.find_by_name("Объект капитальных вложений")
        class_attrs = await object_service.class_service.get_attributes(str(class_meta[0].Id))
        link_attr_meta = next((attr for attr in class_attrs if attr.Name == "ИР Адепт - Primavera"), None)
        assert link_attr_meta is not None

        # Проверяем, что значение ссылочного атрибута в API - это объект с ID
        api_link_value = raw_read_data["Attributes"].get(str(link_attr_meta.Id))
        assert api_link_value is not None
        assert isinstance(api_link_value, dict)
        assert "Id" in api_link_value

        # 6. UPDATE
        updated_name = f"Обновленная тестовая стройка {uuid.uuid4()}"
        created_object.name = updated_name
        created_object.mvz = "МВЗ_UPDATED"

        update_result = await object_service.update(created_object)
        assert update_result.name == updated_name
        assert update_result.mvz == "МВЗ_UPDATED"

        # 7. Чтение после обновления
        reread_data = await object_service.read(created_object._id, StroykaTestModel)
        assert reread_data.name == updated_name
        assert reread_data.mvz == "МВЗ_UPDATED"

        # 8. Удаление объекта
        await object_service.delete(created_object._id)
        object_to_delete_id = None  # Предотвращаем повторное удаление

    finally:
        # 9. Очистка на случай падения теста до шага удаления
        if object_to_delete_id:
            try:
                await object_service.delete(object_to_delete_id)
                print(f"Тестовый объект {object_to_delete_id} успешно удален.")
            except NeosintezAPIError:
                # Игнорируем ошибку, если объект уже был удален
                pass
