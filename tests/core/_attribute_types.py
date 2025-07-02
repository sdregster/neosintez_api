"""
Тесты для проверки работы с различными типами атрибутов в API Неосинтеза.
"""

import datetime
import unittest
from typing import Any

from neosintez_api.core.enums import WioAttributeType
from neosintez_api.utils import (
    build_attribute_body,
    convert_value_to_wio_format,
    get_wio_attribute_type,
    neosintez_type_to_python_type,
)


class TestAttributeTypes(unittest.TestCase):
    """Тестирование работы с типами атрибутов."""

    def test_neosintez_type_to_python_type(self):
        """Тестирование конвертации типа атрибута из Неосинтеза в тип Python."""
        # Проверяем соответствие всех типов
        self.assertEqual(neosintez_type_to_python_type(WioAttributeType.NUMBER), float)
        self.assertEqual(neosintez_type_to_python_type(WioAttributeType.STRING), str)
        self.assertEqual(neosintez_type_to_python_type(WioAttributeType.DATE), datetime.date)
        self.assertEqual(neosintez_type_to_python_type(WioAttributeType.TIME), datetime.time)
        self.assertEqual(neosintez_type_to_python_type(WioAttributeType.DATETIME), datetime.datetime)
        self.assertEqual(neosintez_type_to_python_type(WioAttributeType.BOOLEAN), bool)
        self.assertEqual(neosintez_type_to_python_type(WioAttributeType.TEXT), str)
        self.assertEqual(neosintez_type_to_python_type(WioAttributeType.OBJECT_LINK), str)
        self.assertEqual(neosintez_type_to_python_type(WioAttributeType.COLLECTION), list)
        self.assertEqual(neosintez_type_to_python_type(WioAttributeType.FILE), dict)
        self.assertEqual(neosintez_type_to_python_type(WioAttributeType.TEMPLATE), Any)
        self.assertEqual(neosintez_type_to_python_type(None), Any)
        # Проверяем числовое значение типа
        self.assertEqual(neosintez_type_to_python_type(1), float)
        self.assertEqual(neosintez_type_to_python_type(2), str)
        self.assertEqual(neosintez_type_to_python_type(3), datetime.date)
        self.assertEqual(neosintez_type_to_python_type(4), bool)
        self.assertEqual(neosintez_type_to_python_type(5), datetime.time)
        self.assertEqual(neosintez_type_to_python_type(6), datetime.datetime)
        self.assertEqual(neosintez_type_to_python_type(7), str)
        self.assertEqual(neosintez_type_to_python_type(8), dict)
        self.assertEqual(neosintez_type_to_python_type(9), str)
        self.assertEqual(neosintez_type_to_python_type(10), list)
        self.assertEqual(neosintez_type_to_python_type(11), list)
        self.assertEqual(neosintez_type_to_python_type(15), Any)
        # Проверяем некорректный тип
        self.assertEqual(neosintez_type_to_python_type(999), Any)

    def test_get_wio_attribute_type(self):
        """Тестирование определения типа атрибута по типу Python."""
        # Проверяем соответствие типов Python типам Неосинтеза
        self.assertEqual(get_wio_attribute_type(int), WioAttributeType.NUMBER)
        self.assertEqual(get_wio_attribute_type(float), WioAttributeType.NUMBER)
        self.assertEqual(get_wio_attribute_type(str), WioAttributeType.STRING)
        self.assertEqual(get_wio_attribute_type(datetime.date), WioAttributeType.DATE)
        self.assertEqual(get_wio_attribute_type(datetime.time), WioAttributeType.TIME)
        self.assertEqual(get_wio_attribute_type(datetime.datetime), WioAttributeType.DATETIME)
        self.assertEqual(get_wio_attribute_type(bool), WioAttributeType.BOOLEAN)
        self.assertEqual(get_wio_attribute_type(list), WioAttributeType.COLLECTION)
        self.assertEqual(get_wio_attribute_type(dict), WioAttributeType.OBJECT_LINK)
        # Проверяем сложный или некорректный тип
        self.assertEqual(get_wio_attribute_type(Any), WioAttributeType.STRING)
        self.assertEqual(get_wio_attribute_type(complex), WioAttributeType.STRING)

    def test_convert_value_to_wio_format(self):
        """Тестирование конвертации значения для формата API Неосинтеза."""
        # Проверяем конвертацию для разных типов
        self.assertEqual(convert_value_to_wio_format(10, WioAttributeType.NUMBER), 10)
        self.assertEqual(convert_value_to_wio_format(10.5, WioAttributeType.NUMBER), 10.5)
        self.assertEqual(convert_value_to_wio_format("test", WioAttributeType.STRING), "test")
        self.assertEqual(convert_value_to_wio_format(True, WioAttributeType.BOOLEAN), True)
        self.assertEqual(convert_value_to_wio_format(False, WioAttributeType.BOOLEAN), False)
        # Проверяем конвертацию дат и времени
        today = datetime.date.today()
        self.assertEqual(convert_value_to_wio_format(today, WioAttributeType.DATE), today.isoformat())
        now = datetime.datetime.now()
        self.assertEqual(convert_value_to_wio_format(now, WioAttributeType.DATETIME), now.isoformat())
        current_time = datetime.time(10, 15, 30)
        self.assertEqual(convert_value_to_wio_format(current_time, WioAttributeType.TIME), current_time.isoformat())
        # Проверяем преобразование ссылок и специальных типов
        object_id = "123e4567-e89b-12d3-a456-426614174000"
        self.assertEqual(convert_value_to_wio_format(object_id, WioAttributeType.OBJECT_LINK), object_id)
        self.assertEqual(convert_value_to_wio_format([1, 2, 3], WioAttributeType.COLLECTION), [1, 2, 3])
        file_dict = {"name": "test.txt", "size": 1024}
        self.assertEqual(convert_value_to_wio_format(file_dict, WioAttributeType.FILE), file_dict)

    def test_build_attribute_body(self):
        """Тестирование создания тела атрибута для API."""
        # Подготовка метаданных атрибута
        attr_meta = {"Id": "attr-123", "Type": WioAttributeType.STRING}

        # Проверка формирования тела для строкового атрибута
        body = build_attribute_body(attr_meta, "test")
        expected = {"Id": "attr-123", "Value": "test", "Type": WioAttributeType.STRING}
        self.assertEqual(body, expected)

        # Проверка для числового атрибута
        attr_meta = {"Id": "attr-456", "Type": WioAttributeType.NUMBER}
        body = build_attribute_body(attr_meta, 42)
        expected = {"Id": "attr-456", "Value": 42, "Type": WioAttributeType.NUMBER}
        self.assertEqual(body, expected)

        # Проверка для булевого атрибута
        attr_meta = {"Id": "attr-789", "Type": WioAttributeType.BOOLEAN}
        body = build_attribute_body(attr_meta, True)
        expected = {"Id": "attr-789", "Value": True, "Type": WioAttributeType.BOOLEAN}
        self.assertEqual(body, expected)

        # Проверка с явным указанием типа атрибута
        attr_meta = {"Id": "attr-101"}
        body = build_attribute_body(attr_meta, "test", WioAttributeType.STRING)
        expected = {"Id": "attr-101", "Value": "test", "Type": WioAttributeType.STRING}
        self.assertEqual(body, expected)

        # Проверка с None значением
        attr_meta = {"Id": "attr-102", "Type": WioAttributeType.STRING}
        body = build_attribute_body(attr_meta, None)
        expected = {"Id": "attr-102", "Value": None, "Type": WioAttributeType.STRING}
        self.assertEqual(body, expected)
