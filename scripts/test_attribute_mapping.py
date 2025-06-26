#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Тестирование маппинга атрибутов и конвертации типов.

Этот скрипт демонстрирует:
1. Маппинг типов Python в типы атрибутов Неосинтеза
2. Конвертацию значений различных типов
3. Использование Field(alias=...) для маппинга полей
4. Работу с функцией build_attribute_body
"""

import asyncio
import logging
import os
import sys
from datetime import date, time, datetime
from decimal import Decimal
from uuid import UUID, uuid4
from typing import List, Dict, Any

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# Добавляем родительский каталог в путь импорта
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pydantic import BaseModel, Field
from neosintez_api.core.enums import WioAttributeType
from neosintez_api.utils import (
    get_wio_attribute_type,
    convert_value_to_wio_format,
    build_attribute_body,
    get_field_external_name,
)
from neosintez_api.models import EquipmentModel
from neosintez_api.exceptions import NeosintezValidationError


def test_type_mapping() -> None:
    """
    Тестирует маппинг типов Python в типы атрибутов Неосинтеза.
    """
    logger.info("=== Тестирование маппинга типов Python в WioAttributeType ===")
    
    # Формируем словарь "тип Python -> ожидаемый тип WioAttributeType"
    tests = {
        str: WioAttributeType.STRING,
        int: WioAttributeType.NUMBER,
        float: WioAttributeType.NUMBER,
        bool: WioAttributeType.NUMBER,
        datetime: WioAttributeType.DATETIME,
        date: WioAttributeType.DATE,
        time: WioAttributeType.TIME,
        UUID: WioAttributeType.STRING,
        List[str]: WioAttributeType.COLLECTION,
        List[UUID]: WioAttributeType.REFERENCE_COLLECTION,
    }
    
    # Проверяем маппинг для каждого типа
    for python_type, expected_wio_type in tests.items():
        try:
            actual_wio_type = get_wio_attribute_type(python_type)
            if actual_wio_type == expected_wio_type:
                logger.info(
                    f"✅ Тип {python_type} -> {expected_wio_type.name} (OK)"
                )
            else:
                logger.error(
                    f"❌ Тип {python_type}: ожидался {expected_wio_type.name}, "
                    f"получен {actual_wio_type.name}"
                )
        except Exception as e:
            logger.error(f"❌ Ошибка при маппинге типа {python_type}: {e}")
            
    logger.info("✓ Тестирование маппинга типов завершено")


def test_value_conversion() -> None:
    """
    Тестирует конвертацию значений различных типов.
    """
    logger.info("=== Тестирование конвертации значений ===")
    
    # Формируем список тестовых кейсов (значение, тип, ожидаемый результат)
    test_cases = [
        # Строковые типы
        ("тестовая строка", WioAttributeType.STRING, "тестовая строка"),
        (123, WioAttributeType.STRING, "123"),
        (
            UUID("12345678-1234-5678-1234-567812345678"),
            WioAttributeType.STRING,
            "12345678-1234-5678-1234-567812345678",
        ),
        
        # Числовые типы
        (123, WioAttributeType.NUMBER, 123.0),
        (123.45, WioAttributeType.NUMBER, 123.45),
        (Decimal("123.45"), WioAttributeType.NUMBER, 123.45),
        (True, WioAttributeType.NUMBER, 1),
        (False, WioAttributeType.NUMBER, 0),
        
        # Даты и время
        (
            date(2023, 1, 1),
            WioAttributeType.DATE,
            "2023-01-01",
        ),
        (
            datetime(2023, 1, 1, 12, 30, 45),
            WioAttributeType.DATE,
            "2023-01-01",
        ),
        (
            time(12, 30, 45),
            WioAttributeType.TIME,
            "12:30:45",
        ),
        (
            datetime(2023, 1, 1, 12, 30, 45),
            WioAttributeType.TIME,
            "12:30:45",
        ),
        (
            datetime(2023, 1, 1, 12, 30, 45),
            WioAttributeType.DATETIME,
            "2023-01-01T12:30:45",
        ),
        
        # Ссылочные типы
        (
            UUID("12345678-1234-5678-1234-567812345678"),
            WioAttributeType.OBJECT_LINK,
            "12345678-1234-5678-1234-567812345678",
        ),
        
        # Коллекции
        (
            ["a", "b", "c"],
            WioAttributeType.COLLECTION,
            ["a", "b", "c"],
        ),
        (
            "single value",
            WioAttributeType.COLLECTION,
            ["single value"],
        ),
        (
            [UUID("12345678-1234-5678-1234-567812345678"), UUID("87654321-8765-4321-8765-432187654321")],
            WioAttributeType.REFERENCE_COLLECTION,
            ["12345678-1234-5678-1234-567812345678", "87654321-8765-4321-8765-432187654321"],
        ),
    ]
    
    # Проверяем конвертацию для каждого кейса
    for value, wio_type, expected in test_cases:
        try:
            actual = convert_value_to_wio_format(value, wio_type)
            if actual == expected:
                logger.info(
                    f"✅ {value} ({type(value).__name__}) -> "
                    f"{wio_type.name} = {actual} (OK)"
                )
            else:
                logger.error(
                    f"❌ {value} ({type(value).__name__}) -> {wio_type.name}: "
                    f"ожидалось {expected}, получено {actual}"
                )
        except Exception as e:
            logger.error(
                f"❌ Ошибка при конвертации {value} ({type(value).__name__}) "
                f"в {wio_type.name}: {e}"
            )
            
    logger.info("✓ Тестирование конвертации значений завершено")


def test_field_alias() -> None:
    """
    Тестирует маппинг полей с использованием Field(alias=...).
    """
    logger.info("=== Тестирование маппинга полей с использованием Field(alias=...) ===")
    
    try:
        # Создаем тестовую модель
        equipment = EquipmentModel(
            name="Тестовое оборудование",
            model="XYZ-123",
            serial_number="SN-123456",
            installation_date=datetime(2023, 1, 1),
            is_active=True
        )
        
        # Проверяем атрибуты модели
        logger.info(f"Модель: {equipment}")
        
        # Проверяем алиасы полей
        expected_aliases = {
            "name": "Name",
            "model": "Модель оборудования",
            "serial_number": "Серийный номер",
            "installation_date": "Дата установки",
            "is_active": "Активен",
        }
        
        for field_name, expected_alias in expected_aliases.items():
            try:
                actual_alias = get_field_external_name(EquipmentModel, field_name)
                if actual_alias == expected_alias:
                    logger.info(f"✅ Поле {field_name} -> {actual_alias} (OK)")
                else:
                    logger.error(
                        f"❌ Поле {field_name}: ожидался {expected_alias}, получен {actual_alias}"
                    )
            except Exception as e:
                logger.error(f"❌ Ошибка при проверке поля {field_name}: {e}")
        
        logger.info("✓ Тестирование маппинга полей завершено")
    except Exception as e:
        import traceback
        logger.error(f"❌ Ошибка в test_field_alias: {e}")
        logger.error(traceback.format_exc())


def test_build_attribute_body() -> None:
    """
    Тестирует создание тела атрибута с использованием build_attribute_body.
    """
    logger.info("=== Тестирование функции build_attribute_body ===")
    
    # Создаем тестовые метаданные атрибутов
    attr_meta_string = {
        "Id": "12345678-1234-5678-1234-567812345678",
        "Name": "Название",
        "Type": WioAttributeType.STRING.value,
    }
    
    attr_meta_number = {
        "Id": "23456789-2345-6789-2345-678923456789",
        "Name": "Вес",
        "Type": WioAttributeType.NUMBER.value,
    }
    
    attr_meta_datetime = {
        "Id": "34567890-3456-7890-3456-789034567890",
        "Name": "Дата создания",
        "Type": WioAttributeType.DATETIME.value,
    }
    
    attr_meta_reference = {
        "Id": "45678901-4567-8901-4567-890145678901",
        "Name": "Ссылка на объект",
        "Type": WioAttributeType.OBJECT_LINK.value,
    }
    
    # Создаем тестовые значения
    test_cases = [
        (attr_meta_string, "Тестовое название", None),
        (attr_meta_string, 12345, None),
        (attr_meta_number, 123.45, None),
        (attr_meta_number, "123.45", None),
        (attr_meta_datetime, datetime(2023, 1, 1, 12, 30, 45), None),
        (attr_meta_reference, UUID("12345678-1234-5678-1234-567812345678"), None),
    ]
    
    # Тестируем функцию build_attribute_body для каждого кейса
    for attr_meta, value, explicit_type in test_cases:
        try:
            attr_body = build_attribute_body(attr_meta, value, explicit_type)
            
            logger.info(
                f"✅ {attr_meta['Name']} = {value} ({type(value).__name__}) -> "
                f"{attr_body['Value']} (Тип: {attr_body['Type']})"
            )
            
            # Проверяем корректность тела атрибута
            assert attr_body["Id"] == attr_meta["Id"]
            assert attr_body["Name"] == attr_meta["Name"]
            assert isinstance(attr_body["Type"], int)
            assert attr_body["Value"] is not None
            
        except Exception as e:
            logger.error(
                f"❌ Ошибка при создании тела атрибута для {attr_meta['Name']} = "
                f"{value}: {e}"
            )
            
    logger.info("✓ Тестирование функции build_attribute_body завершено")


async def main() -> None:
    """
    Запускает все тесты.
    """
    logger.info("🚀 Начало тестирования маппинга атрибутов")
    
    try:
        # Тестируем маппинг типов Python в типы атрибутов Неосинтеза
        test_type_mapping()
        logger.info("")
        
        # Тестируем конвертацию значений
        test_value_conversion()
        logger.info("")
        
        # Тестируем маппинг полей с использованием Field(alias=...)
        test_field_alias()
        logger.info("")
        
        # Тестируем функцию build_attribute_body
        test_build_attribute_body()
        logger.info("")
        
        logger.info("🎉 Тестирование маппинга атрибутов завершено успешно!")
        return 0
    except Exception as e:
        import traceback
        logger.error(f"❌ Произошла ошибка при выполнении тестов: {e}")
        logger.error(traceback.format_exc())
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("Прервано пользователем")
        sys.exit(130)
    except Exception as e:
        logger.critical(f"Критическая ошибка: {e}", exc_info=True)
        sys.exit(1) 