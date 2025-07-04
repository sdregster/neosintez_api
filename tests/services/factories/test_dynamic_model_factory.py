import pytest
import pytest_asyncio
from unittest.mock import MagicMock

from neosintez_api.core.client import NeosintezClient
from neosintez_api.services.factories.model_factory import DynamicModelFactory


@pytest_asyncio.fixture
async def factory(real_client: NeosintezClient) -> DynamicModelFactory:
    """Фикстура для создания экземпляра DynamicModelFactory."""
    return DynamicModelFactory(
        client=real_client,
        name_aliases=["Имя объекта"],
        class_name_aliases=["Класс"],
    )


@pytest.mark.asyncio
async def test_create_from_user_data_with_link_attribute(
    factory: DynamicModelFactory,
    real_client: NeosintezClient,
):
    """
    Тестирует корректную обработку ссылочного атрибута (тип 8).
    Фабрика должна найти объект "Да" в справочнике и подставить его ID.
    Этот тест является интеграционным и использует реальные вызовы API.
    Он динамически находит ожидаемый ID, чтобы быть устойчивым к изменениям данных.
    """
    # 1. Готовим тестовые данные от пользователя
    user_data = {
        "Класс": "Стройка",
        "Имя объекта": "Тестовая стройка для проверки динамической ссылки",
        "ИР Адепт - Primavera": "Да",
    }
    class_name = user_data["Класс"]
    target_link_value = user_data["ИР Адепт - Primavera"]

    # 2. Получаем реальные метаданные для класса "Стройка"
    class_info_list = await real_client.classes.get_classes_by_name(class_name)
    assert class_info_list, f"Класс '{class_name}' не найден"
    class_info = next(
        (c for c in class_info_list if c["name"].lower() == class_name.lower()), None
    )
    assert class_info, f"Точное совпадение для класса '{class_name}' не найдено"
    class_id = class_info["id"]

    class_attributes = await real_client.classes.get_attributes(class_id)
    attributes_meta = {attr.Name: attr for attr in class_attributes}

    # 3. Динамически определяем ожидаемый ID
    #    Этот блок симулирует то, что должна сделать фабрика, чтобы мы могли
    #    сравнить её результат с независимо полученным эталоном.
    from neosintez_api.services.object_search_service import ObjectSearchService

    attr_meta = attributes_meta.get("ИР Адепт - Primavera")
    assert attr_meta, "Не найдены метаданные для атрибута 'ИР Адепт - Primavera'"

    linked_class_id, parent_id = None, None
    for constraint in attr_meta.Constraints:
        if constraint.Type == 1 and constraint.EntityId:
            linked_class_id = str(constraint.EntityId)
        elif constraint.Type == 3 and constraint.ObjectRootId:
            parent_id = str(constraint.ObjectRootId)

    assert linked_class_id, "Не удалось извлечь ID класса справочника из Constraints"

    search_service = ObjectSearchService(real_client)
    directory_options = await search_service.find_objects_by_class(
        class_id=linked_class_id, parent_id=parent_id
    )
    expected_object = next(
        (
            opt
            for opt in directory_options
            if opt.Name.lower() == target_link_value.lower()
        ),
        None,
    )
    assert (
        expected_object
    ), f"Не удалось динамически найти объект '{target_link_value}' в справочнике для проверки"
    
    # Теперь мы ожидаем получить целый объект, а не только ID
    expected_link_object = {
        "Id": str(expected_object.Id),
        "Name": expected_object.Name,
    }

    # 4. Выполняем тестируемый метод
    blueprint = await factory.create_from_user_data(
        user_data=user_data,
        class_name=class_name,
        class_id=class_id,
        attributes_meta=attributes_meta,
    )

    # 5. Проверяем результат
    assert blueprint is not None
    assert blueprint.user_data == user_data
    assert not blueprint.errors

    # Проверяем, что в display_representation сохранилось оригинальное значение
    assert (
        blueprint.display_representation.get("ИР Адепт - Primavera") == target_link_value
    ), "В display_representation должно было сохраниться исходное строковое значение"

    # Проверяем, что в итоговой модели значение преобразовано в ОБЪЕКТ
    instance = blueprint.model_instance
    from neosintez_api.utils import generate_field_name

    field_name = generate_field_name("ИР Адепт - Primavera")
    actual_value = getattr(instance, field_name)

    assert (
        actual_value == expected_link_object
    ), f"Ожидался объект '{expected_link_object}', но был получен '{actual_value}'" 