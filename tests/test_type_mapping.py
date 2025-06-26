"""
Тесты для маппинга типов данных Python -> WioAttributeType.
"""

import pytest
from datetime import datetime, date, time
from decimal import Decimal
from uuid import UUID

from neosintez_api.core.enums import WioAttributeType
from neosintez_api.utils import (
    get_wio_attribute_type,
    convert_value_to_wio_format,
    format_attribute_value,
    build_attribute_body
)


class TestWioAttributeTypeMapping:
    """Тесты маппинга Python типов на WioAttributeType."""
    
    def test_string_type_mapping(self):
        """Тестирует маппинг строковых типов."""
        assert get_wio_attribute_type(str) == WioAttributeType.STRING
    
    def test_integer_type_mapping(self):
        """Тестирует маппинг целочисленных типов."""
        assert get_wio_attribute_type(int) == WioAttributeType.INTEGER
    
    def test_float_type_mapping(self):
        """Тестирует маппинг типов с плавающей точкой."""
        assert get_wio_attribute_type(float) == WioAttributeType.DECIMAL
    
    def test_decimal_type_mapping(self):
        """Тестирует маппинг Decimal типов."""
        assert get_wio_attribute_type(Decimal) == WioAttributeType.DECIMAL
    
    def test_boolean_type_mapping(self):
        """Тестирует маппинг булевых типов."""
        assert get_wio_attribute_type(bool) == WioAttributeType.BOOLEAN
    
    def test_datetime_type_mapping(self):
        """Тестирует маппинг datetime типов."""
        assert get_wio_attribute_type(datetime) == WioAttributeType.DATETIME
    
    def test_date_type_mapping(self):
        """Тестирует маппинг date типов."""
        assert get_wio_attribute_type(date) == WioAttributeType.DATE
    
    def test_time_type_mapping(self):
        """Тестирует маппинг time типов."""
        assert get_wio_attribute_type(time) == WioAttributeType.TIME
    
    def test_uuid_type_mapping(self):
        """Тестирует маппинг UUID типов."""
        assert get_wio_attribute_type(UUID) == WioAttributeType.STRING
    
    def test_unsupported_type_mapping(self):
        """Тестирует маппинг неподдерживаемых типов."""
        assert get_wio_attribute_type(list) == WioAttributeType.STRING


class TestValueConversion:
    """Тесты конвертации значений в формат WIO."""
    
    def test_string_conversion(self):
        """Тестирует конвертацию строковых значений."""
        result = convert_value_to_wio_format("test", WioAttributeType.STRING)
        assert result == "test"
    
    def test_integer_conversion(self):
        """Тестирует конвертацию целочисленных значений."""
        result = convert_value_to_wio_format(42, WioAttributeType.INTEGER)
        assert result == 42
    
    def test_decimal_conversion(self):
        """Тестирует конвертацию десятичных значений."""
        result = convert_value_to_wio_format(3.14, WioAttributeType.DECIMAL)
        assert result == 3.14
    
    def test_boolean_conversion(self):
        """Тестирует конвертацию булевых значений."""
        assert convert_value_to_wio_format(True, WioAttributeType.BOOLEAN) is True
        assert convert_value_to_wio_format(False, WioAttributeType.BOOLEAN) is False
    
    def test_datetime_conversion(self):
        """Тестирует конвертацию datetime в ISO формат."""
        dt = datetime(2024, 1, 15, 10, 30, 45)
        result = convert_value_to_wio_format(dt, WioAttributeType.DATETIME)
        assert result == "2024-01-15T10:30:45"
    
    def test_date_conversion(self):
        """Тестирует конвертацию date в ISO формат."""
        d = date(2024, 1, 15)
        result = convert_value_to_wio_format(d, WioAttributeType.DATE)
        assert result == "2024-01-15"
    
    def test_time_conversion(self):
        """Тестирует конвертацию time в строковый формат."""
        t = time(10, 30, 45)
        result = convert_value_to_wio_format(t, WioAttributeType.TIME)
        assert result == "10:30:45"
    
    def test_uuid_conversion(self):
        """Тестирует конвертацию UUID в строку."""
        uuid_obj = UUID("12345678-1234-5678-9abc-123456789def")
        result = convert_value_to_wio_format(uuid_obj, WioAttributeType.STRING)
        assert result == "12345678-1234-5678-9abc-123456789def"


class TestAttributeFormatting:
    """Тесты форматирования атрибутов."""
    
    def test_format_string_attribute(self):
        """Тестирует форматирование строкового атрибута."""
        attr_meta = {"Type": 2, "Name": "TestAttr"}
        result = format_attribute_value(attr_meta, "test value")
        assert result == "test value"
    
    def test_format_integer_attribute(self):
        """Тестирует форматирование целочисленного атрибута."""
        attr_meta = {"Type": 1, "Name": "TestAttr"}
        result = format_attribute_value(attr_meta, 42)
        assert result == 42
    
    def test_format_decimal_attribute(self):
        """Тестирует форматирование десятичного атрибута."""
        attr_meta = {"Type": 3, "Name": "TestAttr"}
        result = format_attribute_value(attr_meta, 3.14159)
        assert result == 3.14159
    
    def test_format_boolean_attribute(self):
        """Тестирует форматирование булевого атрибута."""
        attr_meta = {"Type": 4, "Name": "TestAttr"}
        assert format_attribute_value(attr_meta, True) is True
        assert format_attribute_value(attr_meta, False) is False
    
    def test_format_datetime_attribute(self):
        """Тестирует форматирование datetime атрибута."""
        attr_meta = {"Type": 5, "Name": "TestAttr"}
        dt = datetime(2024, 1, 15, 10, 30, 45)
        result = format_attribute_value(attr_meta, dt)
        assert result == "2024-01-15T10:30:45"


class TestAttributeBodyBuilding:
    """Тесты построения тела атрибута для API."""
    
    def test_build_string_attribute_body(self):
        """Тестирует построение тела для строкового атрибута."""
        attr_meta = {
            "Id": "test-id",
            "Name": "TestAttr", 
            "Type": 2
        }
        result = build_attribute_body(attr_meta, "test value")
        
        expected = {
            "AttributeId": "test-id",
            "Value": "test value"
        }
        assert result == expected
    
    def test_build_integer_attribute_body(self):
        """Тестирует построение тела для целочисленного атрибута."""
        attr_meta = {
            "Id": "test-id",
            "Name": "TestAttr",
            "Type": 1
        }
        result = build_attribute_body(attr_meta, 42)
        
        expected = {
            "AttributeId": "test-id", 
            "Value": 42
        }
        assert result == expected
    
    def test_build_boolean_attribute_body(self):
        """Тестирует построение тела для булевого атрибута."""
        attr_meta = {
            "Id": "test-id",
            "Name": "TestAttr",
            "Type": 4
        }
        result = build_attribute_body(attr_meta, True)
        
        expected = {
            "AttributeId": "test-id",
            "Value": True
        }
        assert result == expected
    
    def test_build_datetime_attribute_body(self):
        """Тестирует построение тела для datetime атрибута."""
        attr_meta = {
            "Id": "test-id",
            "Name": "TestAttr", 
            "Type": 5
        }
        dt = datetime(2024, 1, 15, 10, 30, 45)
        result = build_attribute_body(attr_meta, dt)
        
        expected = {
            "AttributeId": "test-id",
            "Value": "2024-01-15T10:30:45"
        }
        assert result == expected
    
    def test_build_attribute_body_with_explicit_type(self):
        """Тестирует построение тела атрибута с явно указанным типом."""
        attr_meta = {
            "Id": "test-id",
            "Name": "TestAttr",
            "Type": 1  # Integer в мета, но передаем как String
        }
        result = build_attribute_body(attr_meta, "42", WioAttributeType.STRING)
        
        expected = {
            "AttributeId": "test-id",
            "Value": "42"
        }
        assert result == expected 