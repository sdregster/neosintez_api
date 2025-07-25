import uuid

import pytest
import pytest_asyncio
from pydantic import ValidationError

from neosintez_api.core.client import NeosintezClient
from neosintez_api.services.class_service import ClassService
from neosintez_api.services.factories import DynamicModelFactory


@pytest_asyncio.fixture
async def factory(real_client: NeosintezClient) -> DynamicModelFactory:
    """Фикстура для создания экземпляра DynamicModelFactory."""
    class_service = ClassService(real_client)
    return DynamicModelFactory(
        client=real_client,
        class_service=class_service,
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
        "Класс": "Объект капитальных вложений",
        "Имя объекта": f"Тестовая стройка {uuid.uuid4()}",
        "ИР Адепт - Primavera": "Да",
    }
    class_name = user_data["Класс"]
    target_link_value = user_data["ИР Адепт - Primavera"]

    # 2. Динамически определяем ожидаемый ID для сравнения
    #    Этот блок симулирует то, что должна сделать фабрика, чтобы мы могли
    #    сравнить её результат с независимо полученным эталоном.
    from neosintez_api.services.object_search_service import ObjectSearchService

    class_info = (await real_client.classes.get_classes_by_name(class_name))[0]
    class_attributes = await real_client.classes.get_attributes(class_info["id"])
    attr_meta = next(
        (attr for attr in class_attributes if attr.Name == "ИР Адепт - Primavera"),
        None,
    )
    assert attr_meta, "Не найдены метаданные для атрибута 'ИР Адепт - Primavera'"

    linked_class_id, parent_id = None, None
    for constraint in attr_meta.Constraints:
        if constraint.Type == 1 and constraint.EntityId:
            linked_class_id = str(constraint.EntityId)
        elif constraint.Type == 3 and constraint.ObjectRootId:
            parent_id = str(constraint.ObjectRootId)
    assert linked_class_id, "Не удалось извлечь ID класса справочника из Constraints"

    search_service = ObjectSearchService(real_client)
    directory_options = await search_service.find_objects_by_class(class_id=linked_class_id, parent_id=parent_id)
    expected_object_raw = next(
        (opt for opt in directory_options if opt.Name.lower() == target_link_value.lower()),
        None,
    )
    assert expected_object_raw, f"Не удалось динамически найти объект '{target_link_value}' в справочнике"

    expected_link_object = {
        "Id": str(expected_object_raw.Id),
        "Name": expected_object_raw.Name,
    }

    # 3. Выполняем тестируемый метод
    blueprint = await factory.create(user_data)

    # 4. Проверяем результат
    assert blueprint is not None

    # Получаем ожидаемое имя поля и проверяем значение
    from neosintez_api.utils import generate_field_name

    expected_field_name = generate_field_name("ИР Адепт - Primavera")

    actual_link_value = getattr(blueprint.model_instance, expected_field_name)
    assert actual_link_value == expected_link_object


@pytest.mark.asyncio
async def test_create_raises_validation_error_for_bad_data(factory: DynamicModelFactory):
    """
    Тестирует, что фабрика вызывает ValidationError при некорректных данных,
    например, когда тип значения атрибута не соответствует ожидаемому.
    """
    user_data = {
        "Класс": "Объект капитальных вложений",
        "Имя объекта": "Тестовая стройка с невалидным атрибутом",
        "ID стройки Адепт": "это-не-число",  # Атрибут ожидает число
    }

    with pytest.raises(ValidationError) as excinfo:
        await factory.create(user_data)

    # Проверяем, что ошибка содержит информацию о проблеме с парсингом
    assert "ID стройки Адепт" in str(excinfo.value)
    assert "unable to parse string as a number" in str(excinfo.value)
