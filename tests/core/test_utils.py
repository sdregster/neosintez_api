import uuid

from neosintez_api.models import Attribute
from neosintez_api.utils import build_attribute_body


def test_build_attribute_body_for_link_attribute():
    """
    Тестирует, что для ссылочного атрибута (Type=8) тело запроса
    формируется корректно, включая правильный Type.
    """
    # 1. Готовим мок метаданных для атрибута "ИР Адепт - Primavera"
    attr_id = uuid.uuid4()
    linked_object_id = uuid.uuid4()
    linked_object_name = "Да"

    mock_attr_meta = Attribute(
        Id=attr_id,
        Name="ИР Адепт - Primavera",
        Type=8,  # Ссылка на объект
        Constraints=[],
    )

    # 2. Вызываем тестируемую функцию
    # Значением теперь является СЛОВАРЬ, который вернул бы AttributeResolver
    link_value_obj = {"Id": str(linked_object_id), "Name": linked_object_name}
    result = build_attribute_body(mock_attr_meta, link_value_obj)

    # 3. Проверяем результат
    expected = {
        "Id": str(attr_id),
        "Value": link_value_obj,
        "Type": 8,
    }
    assert result == expected


def test_build_attribute_body_for_string_attribute():
    """
    Тестирует корректное формирование тела для простого строкового атрибута (Type=2).
    """
    attr_id = uuid.uuid4()
    mock_attr_meta = Attribute(Id=attr_id, Name="МВЗ", Type=2)

    result = build_attribute_body(mock_attr_meta, "TEST_MVZ")

    expected = {
        "Id": str(attr_id),
        "Value": "TEST_MVZ",
        "Type": 2,
    }
    assert result == expected


def test_build_attribute_body_for_int_attribute():
    """
    Тестирует корректное формирование тела для числового атрибута (Type=1).
    """
    attr_id = uuid.uuid4()
    mock_attr_meta = Attribute(Id=attr_id, Name="ID стройки", Type=1)

    result = build_attribute_body(mock_attr_meta, 12345)

    expected = {
        "Id": str(attr_id),
        "Value": 12345,
        "Type": 1,
    }
    assert result == expected
