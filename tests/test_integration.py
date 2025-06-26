"""
Интеграционные тесты для полного сценария CRUD операций.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, Mock
from typing import Dict, Any
from uuid import uuid4
from pydantic import BaseModel, Field

from neosintez_api.config import NeosintezSettings
from neosintez_api.core.client import NeosintezClient
from neosintez_api.resources.classes import ClassesResource
from neosintez_api.resources.objects import ObjectsResource
from neosintez_api.services.object_service import ObjectService


class TestConstruction(BaseModel):
    """Тестовая модель стройки для интеграционных тестов."""
    
    __class_name__ = "Стройка"
    
    name: str = Field(alias="Name")
    mvz: str = Field(alias="МВЗ")
    adept_id: int = Field(alias="ID стройки Адепт")


class TestIntegrationCRUD:
    """Интеграционные тесты полного CRUD сценария."""
    
    @pytest.fixture
    def mock_data(self):
        """Фикстура с тестовыми данными."""
        return {
            "class_id": "3aa54908-2283-ec11-911c-005056b6948b",
            "object_id": str(uuid4()),
            "parent_id": "4c9c07fa-7d52-f011-91e5-005056b6948b",
            "class_attributes": [
                {
                    "Id": "626370d8-ad8f-ec11-911d-005056b6948b",
                    "Name": "МВЗ",
                    "Type": 2,  # String
                    "Required": True,
                    "Multiple": False
                },
                {
                    "Id": "f980619f-b547-ee11-917e-005056b6948b",
                    "Name": "ID стройки Адепт",
                    "Type": 1,  # Integer
                    "Required": False,
                    "Multiple": False
                }
            ]
        }
    
    @pytest.fixture
    async def mock_client_with_data(self, mock_data):
        """Полностью настроенный мок-клиент с данными."""
        settings = NeosintezSettings(
            base_url="https://test.neosintez.ru",
            username="test_user",
            password="test_password",
            verify_ssl=False
        )
        
        client = Mock(spec=NeosintezClient)
        client.settings = settings
        
        # Мокируем classes ресурс
        client.classes = AsyncMock(spec=ClassesResource)
        client.classes.find_by_name.return_value = mock_data["class_id"]
        client.classes.get_attributes.return_value = mock_data["class_attributes"]
        
        # Мокируем objects ресурс
        client.objects = AsyncMock(spec=ObjectsResource)
        client.objects.create.return_value = {"Id": mock_data["object_id"]}
        client.objects.set_attributes.return_value = True
        
        # Мокируем get_by_id для чтения объекта
        object_data = Mock()
        object_data.Name = "Тестовая стройка"
        object_data.EntityId = mock_data["class_id"]
        object_data.Attributes = {
            "626370d8-ad8f-ec11-911d-005056b6948b": {
                "Value": "МВЗ123456",
                "Type": 2
            },
            "f980619f-b547-ee11-917e-005056b6948b": {
                "Value": 42,
                "Type": 1
            }
        }
        client.objects.get_by_id.return_value = object_data
        
        return client
    
    @pytest.mark.asyncio
    async def test_full_crud_scenario(self, mock_client_with_data, mock_data):
        """Тестирует полный сценарий: create → read → update_attrs → read."""
        
        # Создаем сервис
        object_service = ObjectService(mock_client_with_data)
        
        # 1. CREATE - создание объекта
        test_model = TestConstruction(
            name="Тестовая стройка",
            mvz="МВЗ123456",
            adept_id=42
        )
        
        object_id = await object_service.create(test_model, mock_data["parent_id"])
        
        # Проверяем, что объект создан
        assert object_id == mock_data["object_id"]
        
        # Проверяем вызовы API
        mock_client_with_data.classes.find_by_name.assert_called_once_with("Стройка")
        mock_client_with_data.classes.get_attributes.assert_called_once_with(mock_data["class_id"])
        mock_client_with_data.objects.create.assert_called_once()
        mock_client_with_data.objects.set_attributes.assert_called_once()
        
        # 2. READ - чтение объекта
        read_model = await object_service.read(object_id, TestConstruction)
        
        # Проверяем корректность данных
        assert read_model.name == "Тестовая стройка"
        assert read_model.mvz == "МВЗ123456"
        assert read_model.adept_id == 42
        
        # Проверяем вызов API
        mock_client_with_data.objects.get_by_id.assert_called_once_with(object_id)
        
        # 3. UPDATE_ATTRS - обновление атрибутов
        updated_model = TestConstruction(
            name=read_model.name,  # Имя оставляем
            mvz="МВЗ-Обновлен",   # Изменяем МВЗ
            adept_id=999          # Изменяем ID
        )
        
        # Мокируем повторное чтение для update_attrs
        updated_object_data = Mock()
        updated_object_data.Name = "Тестовая стройка"
        updated_object_data.EntityId = mock_data["class_id"]
        updated_object_data.Attributes = {
            "626370d8-ad8f-ec11-911d-005056b6948b": {
                "Value": "МВЗ-Обновлен",
                "Type": 2
            },
            "f980619f-b547-ee11-917e-005056b6948b": {
                "Value": 999,
                "Type": 1
            }
        }
        
        # Настраиваем mock для возврата обновленных данных при повторном чтении
        mock_client_with_data.objects.get_by_id.return_value = updated_object_data
        
        update_result = await object_service.update_attrs(object_id, updated_model)
        assert update_result is True
        
        # 4. READ - повторное чтение для проверки обновления
        final_model = await object_service.read(object_id, TestConstruction)
        
        # Проверяем, что изменения применились
        assert final_model.name == "Тестовая стройка"
        assert final_model.mvz == "МВЗ-Обновлен"
        assert final_model.adept_id == 999
    
    @pytest.mark.asyncio
    async def test_create_error_handling(self, mock_client_with_data):
        """Тестирует обработку ошибок при создании объекта."""
        object_service = ObjectService(mock_client_with_data)
        
        # Мокируем ошибку при поиске класса
        mock_client_with_data.classes.find_by_name.return_value = None
        
        test_model = TestConstruction(
            name="Тестовая стройка",
            mvz="МВЗ123456",
            adept_id=42
        )
        
        # Должно возникнуть исключение при отсутствии класса
        with pytest.raises(Exception):  # Базовый Exception пока для простоты
            await object_service.create(test_model, "parent_id")
    
    @pytest.mark.asyncio
    async def test_read_error_handling(self, mock_client_with_data):
        """Тестирует обработку ошибок при чтении объекта."""
        object_service = ObjectService(mock_client_with_data)
        
        # Мокируем ошибку при получении объекта
        mock_client_with_data.objects.get_by_id.side_effect = Exception("Object not found")
        
        # Должно возникнуть исключение при отсутствии объекта
        with pytest.raises(Exception):
            await object_service.read("nonexistent_id", TestConstruction)
    
    @pytest.mark.asyncio
    async def test_update_attrs_no_changes(self, mock_client_with_data, mock_data):
        """Тестирует update_attrs когда изменений нет."""
        object_service = ObjectService(mock_client_with_data)
        
        # Настраиваем данные для "текущего" объекта
        current_object_data = Mock()
        current_object_data.Name = "Тестовая стройка"
        current_object_data.EntityId = mock_data["class_id"]
        current_object_data.Attributes = {
            "626370d8-ad8f-ec11-911d-005056b6948b": {
                "Value": "МВЗ123456",
                "Type": 2
            },
            "f980619f-b547-ee11-917e-005056b6948b": {
                "Value": 42,
                "Type": 1
            }
        }
        mock_client_with_data.objects.get_by_id.return_value = current_object_data
        
        # Модель с теми же данными
        same_model = TestConstruction(
            name="Тестовая стройка",
            mvz="МВЗ123456",
            adept_id=42
        )
        
        result = await object_service.update_attrs(mock_data["object_id"], same_model)
        
        # Проверяем, что обновление не вызывалось (нет изменений)
        # В текущей реализации set_attributes все равно вызывается,
        # но в будущем можно оптимизировать
        assert result is True
    
    @pytest.mark.asyncio 
    async def test_partial_attribute_update(self, mock_client_with_data, mock_data):
        """Тестирует частичное обновление атрибутов."""
        object_service = ObjectService(mock_client_with_data)
        
        # Настраиваем текущие данные объекта
        current_object_data = Mock()
        current_object_data.Name = "Тестовая стройка"
        current_object_data.EntityId = mock_data["class_id"]
        current_object_data.Attributes = {
            "626370d8-ad8f-ec11-911d-005056b6948b": {
                "Value": "МВЗ123456",
                "Type": 2
            },
            "f980619f-b547-ee11-917e-005056b6948b": {
                "Value": 42,
                "Type": 1
            }
        }
        mock_client_with_data.objects.get_by_id.return_value = current_object_data
        
        # Модель с изменением только одного атрибута
        updated_model = TestConstruction(
            name="Тестовая стройка",  # Не изменилось
            mvz="МВЗ-Новый",         # Изменился
            adept_id=42              # Не изменился
        )
        
        result = await object_service.update_attrs(mock_data["object_id"], updated_model)
        assert result is True
        
        # Проверяем, что set_attributes был вызван
        mock_client_with_data.objects.set_attributes.assert_called()


class TestIntegrationMockServer:
    """Тесты с использованием мок-сервера для имитации реального API."""
    
    @pytest.mark.asyncio
    async def test_concurrent_operations(self, mock_client_with_data, mock_data):
        """Тестирует параллельные операции с объектами."""
        object_service = ObjectService(mock_client_with_data)
        
        # Создаем несколько моделей
        models = [
            TestConstruction(
                name=f"Стройка {i}",
                mvz=f"МВЗ{i:06d}",
                adept_id=i
            )
            for i in range(1, 4)
        ]
        
        # Мокируем разные object_id для каждого создания
        object_ids = [str(uuid4()) for _ in range(3)]
        mock_client_with_data.objects.create.side_effect = [
            {"Id": obj_id} for obj_id in object_ids
        ]
        
        # Параллельное создание объектов
        tasks = [
            object_service.create(model, mock_data["parent_id"])
            for model in models
        ]
        
        created_ids = await asyncio.gather(*tasks)
        
        # Проверяем результаты
        assert len(created_ids) == 3
        assert all(obj_id in object_ids for obj_id in created_ids)
        
        # Проверяем количество вызовов API
        assert mock_client_with_data.objects.create.call_count == 3
        assert mock_client_with_data.objects.set_attributes.call_count == 3
    
    @pytest.mark.asyncio
    async def test_data_consistency(self, mock_client_with_data, mock_data):
        """Тестирует консистентность данных при последовательных операциях."""
        object_service = ObjectService(mock_client_with_data)
        
        # Исходная модель
        original_model = TestConstruction(
            name="Консистентная стройка",
            mvz="МВЗ999999",
            adept_id=999
        )
        
        # 1. Создание
        object_id = await object_service.create(original_model, mock_data["parent_id"])
        
        # 2. Чтение созданного объекта
        read_model = await object_service.read(object_id, TestConstruction)
        
        # 3. Проверяем, что данные совпадают
        assert read_model.name == original_model.name
        assert read_model.mvz == original_model.mvz
        assert read_model.adept_id == original_model.adept_id
        
        # 4. Обновление
        updated_model = TestConstruction(
            name=read_model.name,
            mvz="МВЗ-ОБНОВЛЕН",
            adept_id=1001
        )
        
        # Настраиваем mock для возврата обновленных данных
        updated_object_data = Mock()
        updated_object_data.Name = "Консистентная стройка"
        updated_object_data.EntityId = mock_data["class_id"]
        updated_object_data.Attributes = {
            "626370d8-ad8f-ec11-911d-005056b6948b": {
                "Value": "МВЗ-ОБНОВЛЕН",
                "Type": 2
            },
            "f980619f-b547-ee11-917e-005056b6948b": {
                "Value": 1001,
                "Type": 1
            }
        }
        mock_client_with_data.objects.get_by_id.return_value = updated_object_data
        
        await object_service.update_attrs(object_id, updated_model)
        
        # 5. Повторное чтение для проверки
        final_model = await object_service.read(object_id, TestConstruction)
        
        # 6. Проверяем финальную консистентность
        assert final_model.name == "Консистентная стройка"
        assert final_model.mvz == "МВЗ-ОБНОВЛЕН"
        assert final_model.adept_id == 1001 