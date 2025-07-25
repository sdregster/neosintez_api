import pytest

from neosintez_api.core.client import NeosintezClient
from neosintez_api.models import AttributeConstraint


@pytest.mark.asyncio
async def test_get_and_inspect_link_attribute_constraints(real_client: NeosintezClient):
    """
    Тест-исследование для получения и проверки реальной структуры
    ограничений (Constraints) у ссылочного атрибута.
    """
    CLASS_NAME_TO_FIND = "Объект капитальных вложений"
    ATTRIBUTE_NAME_TO_FIND = "ИР Адепт - Primavera"

    # 1. Находим класс "Объект капитальных вложений"
    class_info_list = await real_client.classes.get_classes_by_name(CLASS_NAME_TO_FIND)
    assert class_info_list, f"Класс '{CLASS_NAME_TO_FIND}' не найден"

    class_info = next((c for c in class_info_list if c["name"].lower() == CLASS_NAME_TO_FIND.lower()), None)
    assert class_info, f"Точное совпадение для класса '{CLASS_NAME_TO_FIND}' не найдено"
    class_id = class_info["id"]
    print(f"\\nНайден класс '{CLASS_NAME_TO_FIND}' с ID: {class_id}")

    # 2. Получаем все его атрибуты
    class_attributes = await real_client.classes.get_attributes(class_id)
    assert class_attributes, "Не удалось получить атрибуты для класса"

    # 3. Находим нужный атрибут
    found_attribute = next((attr for attr in class_attributes if attr.Name == ATTRIBUTE_NAME_TO_FIND), None)
    assert found_attribute, f"Атрибут '{ATTRIBUTE_NAME_TO_FIND}' не найден"
    print(f"Найден атрибут '{ATTRIBUTE_NAME_TO_FIND}'")

    # 4. Выводим его метаданные, особенно Constraints, для анализа
    print("\\n" + "=" * 80)
    print("ПОЛНЫЕ МЕТАДАННЫЕ АТРИБУТА:")
    print(found_attribute.model_dump_json(indent=4))
    print("=" * 80)

    # 5. Ключевые проверки-гипотезы.
    # Проверяем, что Constraints - это список объектов AttributeConstraint.
    assert isinstance(found_attribute.Constraints, list), "Ожидалось, что Constraints будет списком!"
    print("\\nПроверка 'isinstance(Constraints, list)' прошла успешно.")

    # Проверяем, что список не пустой
    assert found_attribute.Constraints, "Список Constraints не должен быть пустым для этого атрибута."

    # Проверяем тип первого элемента в списке
    first_constraint = found_attribute.Constraints[0]
    assert isinstance(first_constraint, AttributeConstraint), (
        f"Элемент в Constraints должен быть типа AttributeConstraint, а не {type(first_constraint)}"
    )
    print("Проверка типа элемента в Constraints прошла успешно.")

    # Проверяем, что поля внутри объекта ограничения распарсились корректно
    assert first_constraint.Type is not None, "Type в ограничении не должен быть None"
    assert first_constraint.EntityId is not None, "EntityId в ограничении не должен быть None"
    print(
        f"Данные первого ограничения успешно распознаны: Type={first_constraint.Type}, EntityId={first_constraint.EntityId}"
    )
