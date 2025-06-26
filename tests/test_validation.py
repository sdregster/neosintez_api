"""
Тесты для валидации данных и Pydantic моделей.
"""

import pytest
from typing import Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, ValidationError

from neosintez_api.exceptions import ModelValidationError
from neosintez_api.services.mappers.object_mapper import ObjectMapper


class TestModel(BaseModel):
    """Тестовая Pydantic модель для проверки валидации."""
    
    __class_name__ = "ТестовыйКласс"
    
    name: str = Field(alias="Name")
    mvz: str = Field(alias="МВЗ")
    adept_id: int = Field(alias="ID стройки Адепт")
    optional_field: Optional[str] = Field(default=None, alias="Опциональное поле")


class InvalidTestModel(BaseModel):
    """Модель без обязательного атрибута __class_name__."""
    
    name: str = Field(alias="Name")
    value: int


class TestPydanticValidation:
    """Тесты валидации Pydantic моделей."""
    
    def test_valid_model_creation(self):
        """Тестирует создание валидной модели."""
        model = TestModel(
            name="Тест объект",
            mvz="МВЗ123456",
            adept_id=42
        )
        
        assert model.name == "Тест объект"
        assert model.mvz == "МВЗ123456"
        assert model.adept_id == 42
        assert model.optional_field is None
    
    def test_model_creation_with_aliases(self):
        """Тестирует создание модели с использованием алиасов."""
        model = TestModel(
            Name="Тест объект",
            **{"МВЗ": "МВЗ123456", "ID стройки Адепт": 42}
        )
        
        assert model.name == "Тест объект"
        assert model.mvz == "МВЗ123456"
        assert model.adept_id == 42
    
    def test_model_creation_with_optional_field(self):
        """Тестирует создание модели с опциональным полем."""
        model = TestModel(
            name="Тест объект",
            mvz="МВЗ123456",
            adept_id=42,
            optional_field="Дополнительное значение"
        )
        
        assert model.optional_field == "Дополнительное значение"
    
    def test_model_validation_missing_required_field(self):
        """Тестирует валидацию при отсутствии обязательного поля."""
        with pytest.raises(ValidationError) as exc_info:
            TestModel(
                name="Тест объект",
                mvz="МВЗ123456"
                # Отсутствует adept_id
            )
        
        error = exc_info.value
        assert "adept_id" in str(error) or "ID стройки Адепт" in str(error)
    
    def test_model_validation_wrong_type(self):
        """Тестирует валидацию при неправильном типе данных."""
        with pytest.raises(ValidationError) as exc_info:
            TestModel(
                name="Тест объект",
                mvz="МВЗ123456",
                adept_id="неправильный_тип"  # Должно быть int
            )
        
        error = exc_info.value
        assert "type" in str(error).lower()
    
    def test_model_dict_export(self):
        """Тестирует экспорт модели в словарь."""
        model = TestModel(
            name="Тест объект",
            mvz="МВЗ123456",
            adept_id=42
        )
        
        # Экспорт с использованием алиасов
        model_dict = model.model_dump(by_alias=True)
        
        expected = {
            "Name": "Тест объект",
            "МВЗ": "МВЗ123456",
            "ID стройки Адепт": 42,
            "Опциональное поле": None
        }
        
        assert model_dict == expected
    
    def test_model_dict_exclude_none(self):
        """Тестирует экспорт модели с исключением None значений."""
        model = TestModel(
            name="Тест объект",
            mvz="МВЗ123456",
            adept_id=42
        )
        
        model_dict = model.model_dump(by_alias=True, exclude_none=True)
        
        expected = {
            "Name": "Тест объект",
            "МВЗ": "МВЗ123456",
            "ID стройки Адепт": 42
        }
        
        assert model_dict == expected
    
    def test_model_has_class_name_attribute(self):
        """Тестирует наличие атрибута __class_name__."""
        assert hasattr(TestModel, "__class_name__")
        assert TestModel.__class_name__ == "ТестовыйКласс"
    
    def test_model_without_class_name_attribute(self):
        """Тестирует модель без атрибута __class_name__."""
        assert not hasattr(InvalidTestModel, "__class_name__")


class TestObjectMapperValidation:
    """Тесты валидации в ObjectMapper."""
    
    def test_model_to_attributes_validation(self):
        """Тестирует валидацию при преобразовании модели в атрибуты."""
        mapper = ObjectMapper()
        
        model = TestModel(
            name="Тест объект",
            mvz="МВЗ123456",
            adept_id=42
        )
        
        attr_meta_by_name = {
            "МВЗ": {
                "Id": "attr1",
                "Name": "МВЗ",
                "Type": 2,  # String
                "Required": True
            },
            "ID стройки Адепт": {
                "Id": "attr2", 
                "Name": "ID стройки Адепт",
                "Type": 1,  # Integer
                "Required": False
            }
        }
        
        # Должно работать без ошибок
        result = mapper.model_to_attributes_sync(model, attr_meta_by_name)
        
        assert len(result) == 2
        assert result[0]["AttributeId"] == "attr1"
        assert result[0]["Value"] == "МВЗ123456"
        assert result[1]["AttributeId"] == "attr2" 
        assert result[1]["Value"] == 42
    
    def test_model_to_attributes_missing_metadata(self):
        """Тестирует обработку отсутствующих метаданных атрибутов."""
        mapper = ObjectMapper()
        
        model = TestModel(
            name="Тест объект",
            mvz="МВЗ123456",
            adept_id=42
        )
        
        # Неполные метаданные - отсутствует информация об одном атрибуте
        attr_meta_by_name = {
            "МВЗ": {
                "Id": "attr1",
                "Name": "МВЗ",
                "Type": 2,
                "Required": True
            }
            # Отсутствует "ID стройки Адепт"
        }
        
        # Должно обработать только доступные атрибуты
        result = mapper.model_to_attributes_sync(model, attr_meta_by_name)
        
        assert len(result) == 1
        assert result[0]["AttributeId"] == "attr1"
        assert result[0]["Value"] == "МВЗ123456"
    
    def test_attributes_to_model_validation(self):
        """Тестирует валидацию при преобразовании атрибутов в модель."""
        mapper = ObjectMapper()
        
        attributes = [
            {
                "Id": "attr1",
                "Name": "МВЗ",
                "Value": "МВЗ123456",
                "Type": 2
            },
            {
                "Id": "attr2",
                "Name": "ID стройки Адепт", 
                "Value": 42,
                "Type": 1
            }
        ]
        
        # Должно создать валидную модель
        model_data = mapper.attributes_to_model_data_sync(attributes)
        
        # Добавляем имя объекта для валидации
        model_data["Name"] = "Тест объект"
        
        model = TestModel(**model_data)
        
        assert model.name == "Тест объект"
        assert model.mvz == "МВЗ123456"
        assert model.adept_id == 42
    
    def test_attributes_to_model_type_conversion(self):
        """Тестирует автоматическое преобразование типов."""
        mapper = ObjectMapper()
        
        attributes = [
            {
                "Id": "attr1",
                "Name": "МВЗ",
                "Value": "МВЗ123456",
                "Type": 2
            },
            {
                "Id": "attr2",
                "Name": "ID стройки Адепт",
                "Value": "42",  # Строка вместо числа
                "Type": 1
            }
        ]
        
        model_data = mapper.attributes_to_model_data_sync(attributes)
        model_data["Name"] = "Тест объект"
        
        # Pydantic должен автоматически преобразовать "42" в 42
        model = TestModel(**model_data)
        
        assert model.adept_id == 42
        assert isinstance(model.adept_id, int)


class TestDataValidation:
    """Тесты валидации входных данных."""
    
    def test_uuid_validation(self):
        """Тестирует валидацию UUID."""
        valid_uuid = str(uuid4())
        
        # Валидный UUID не должен вызывать ошибок
        uuid_obj = UUID(valid_uuid)
        assert str(uuid_obj) == valid_uuid
    
    def test_invalid_uuid_validation(self):
        """Тестирует валидацию невалидного UUID."""
        invalid_uuid = "не-uuid"
        
        with pytest.raises(ValueError):
            UUID(invalid_uuid)
    
    def test_empty_string_validation(self):
        """Тестирует валидацию пустых строк."""
        with pytest.raises(ValidationError):
            TestModel(
                name="",  # Пустое имя
                mvz="МВЗ123456",
                adept_id=42
            )
    
    def test_negative_integer_validation(self):
        """Тестирует валидацию отрицательных чисел."""
        # Отрицательные числа должны быть допустимы
        model = TestModel(
            name="Тест объект",
            mvz="МВЗ123456",
            adept_id=-1
        )
        
        assert model.adept_id == -1
    
    def test_large_integer_validation(self):
        """Тестирует валидацию больших чисел."""
        large_number = 2**31
        
        model = TestModel(
            name="Тест объект",
            mvz="МВЗ123456",
            adept_id=large_number
        )
        
        assert model.adept_id == large_number 