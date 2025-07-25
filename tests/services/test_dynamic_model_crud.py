"""
Интеграционные тесты для полного CRUD-цикла (Create, Read, Update, Delete)
с использованием DynamicModelFactory и ObjectService.

Тесты проверяют, что можно "на лету" создать Pydantic-модель из словаря,
а затем использовать её для создания, чтения, обновления и удаления объекта
в Неосинтезе.
"""

import pytest
import pytest_asyncio

from neosintez_api.config import settings
from neosintez_api.services import ObjectService
from neosintez_api.services.factories import DynamicModelFactory


pytestmark = pytest.mark.asyncio


@pytest.fixture(scope="module")
def user_defined_data() -> dict:
    """Тестовые данные в виде словаря, как если бы они пришли от пользователя."""
    return {
        "Класс": "Объект капитальных вложений",
        "Имя объекта": "Тестовая динамическая стройка",
        "МВЗ": "МВЗ_INITIAL_TEST",
        "ID стройки Адепт": 12345,
        "ИР Адепт - Primavera": "Да",
        "Процент комплектации": 55.5,
    }


@pytest_asyncio.fixture
async def managed_object(
    object_service: ObjectService,
    dynamic_model_factory: DynamicModelFactory,
    user_defined_data: dict,
):
    """
    Фикстура для управления жизненным циклом тестового объекта.

    Создает объект перед тестом и гарантированно удаляет его после,
    даже если тест упал.
    """
    blueprint = await dynamic_model_factory.create(user_defined_data)
    model_instance = blueprint.model_instance
    created_object = await object_service.create(model_instance, parent_id=settings.test_folder_id)
    assert created_object._id is not None, "Объект не был создан"

    yield {
        "id": created_object._id,
        "model_class": blueprint.model_class,
        "original_model": created_object,
    }

    # Очистка
    try:
        await object_service.delete(created_object._id)
        print(f"Тестовый объект {created_object._id} успешно удален.")
    except Exception as e:
        print(f"Ошибка при удалении тестового объекта {created_object._id}: {e}")


class TestDynamicModelCRUD:
    """Тестирование полного CRUD цикла с динамическими моделями."""

    async def test_create_object_with_invalid_reference(
        self,
        dynamic_model_factory: DynamicModelFactory,
        object_service: ObjectService,
        user_defined_data: dict,
        caplog,
    ):
        """
        Проверяет, что при некорректном значении ссылочного атрибута:
        - объект все равно создается
        - в лог пишется предупреждение
        - некорректный атрибут остается пустым
        """
        invalid_data = user_defined_data.copy()
        invalid_data["ИР Адепт - Primavera"] = "Хз"  # Несуществующее значение
        created_object_id = None

        try:
            blueprint = await dynamic_model_factory.create(invalid_data)
            DynamicModel = blueprint.model_class
            model_instance = blueprint.model_instance

            # Объект должен создаться без ошибок
            created_object = await object_service.create(model_instance, parent_id=settings.test_folder_id)
            created_object_id = created_object._id
            assert created_object_id is not None

            # Проверяем логи
            assert "Не удалось разрешить значение 'Хз'" in caplog.text
            assert "Атрибут будет пропущен" in caplog.text

            # Проверяем, что атрибут не установился
            read_object = await object_service.read(created_object_id, DynamicModel)
            assert read_object.ir_adept_primavera is None

        finally:
            if created_object_id:
                await object_service.delete(created_object_id)

    async def test_full_crud_cycle(
        self,
        object_service: ObjectService,
        managed_object: dict,
        user_defined_data: dict,
    ):
        """
        Тестирует полный цикл: CREATE, READ, UPDATE, DELETE (delete в фикстуре).
        """
        created_object_id = managed_object["id"]
        DynamicModel = managed_object["model_class"]

        # 1. READ: Проверяем, что созданный объект можно прочитать
        read_object = await object_service.read(created_object_id, DynamicModel)

        assert read_object.name == user_defined_data["Имя объекта"]
        assert read_object.mvz == user_defined_data["МВЗ"]
        assert read_object.id_stroyki_adept == user_defined_data["ID стройки Адепт"]
        assert isinstance(read_object.ir_adept_primavera, str)  # Проверяем, что "Да" разрешилось в ID
        assert read_object.protsent_komplektatsii == user_defined_data["Процент комплектации"]
        assert read_object._id == created_object_id
        assert read_object._parent_id == settings.test_folder_id

        # 2. UPDATE: Обновляем атрибуты и родителя
        read_object.name = "Динамическая стройка (обновлено)"
        read_object.mvz = "UPDATED_STATE"
        read_object.ir_adept_primavera = "Нет"
        read_object._parent_id = settings.test_folder_id_2

        updated_object = await object_service.update(read_object)

        # 3. VERIFY UPDATE: Проверяем, что изменения применились
        re_read_object = await object_service.read(created_object_id, DynamicModel)

        # Проверяем обновленные поля
        assert re_read_object.name == "Динамическая стройка (обновлено)"
        assert re_read_object.mvz == "UPDATED_STATE"
        assert re_read_object.ir_adept_primavera == "Нет"
        assert re_read_object._parent_id == settings.test_folder_id_2

        # Проверяем, что модель из ответа `update` соответствует данным в системе
        assert updated_object == re_read_object
