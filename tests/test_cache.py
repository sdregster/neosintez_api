"""
Тесты для системы кэширования с TTL.
"""

import time
import asyncio
import pytest
from unittest.mock import Mock, patch

from neosintez_api.services.cache import TTLCache, cached


class TestTTLCache:
    """Тесты для TTL кэша."""
    
    def test_cache_initialization(self):
        """Тестирует инициализацию кэша."""
        cache = TTLCache(default_ttl=300, max_size=100)
        assert cache.default_ttl == 300
        assert cache.max_size == 100
        assert cache.size() == 0
    
    def test_set_and_get(self, ttl_cache):
        """Тестирует установку и получение значений."""
        ttl_cache.set("test_key", "test_value")
        
        result = ttl_cache.get("test_key")
        assert result == "test_value"
        assert ttl_cache.size() == 1
    
    def test_get_nonexistent_key(self, ttl_cache):
        """Тестирует получение несуществующего ключа."""
        result = ttl_cache.get("nonexistent")
        assert result is None
    
    def test_set_with_custom_ttl(self, ttl_cache):
        """Тестирует установку значения с кастомным TTL."""
        ttl_cache.set("custom_ttl", "value", ttl=1)
        
        # Сразу после установки значение должно быть доступно
        assert ttl_cache.get("custom_ttl") == "value"
        
        # Ждем истечения TTL
        time.sleep(1.1)
        
        # Значение должно быть удалено
        assert ttl_cache.get("custom_ttl") is None
        assert ttl_cache.size() == 0
    
    def test_ttl_expiration(self, ttl_cache):
        """Тестирует истечение времени жизни записей."""
        # Устанавливаем очень короткий TTL
        ttl_cache.set("expire_test", "value", ttl=0.1)
        
        # Сразу значение доступно
        assert ttl_cache.get("expire_test") == "value"
        
        # Ждем истечения TTL
        time.sleep(0.2)
        
        # Значение должно быть недоступно
        assert ttl_cache.get("expire_test") is None
    
    def test_max_size_limit(self):
        """Тестирует ограничение максимального размера."""
        cache = TTLCache(default_ttl=60, max_size=2)
        
        # Добавляем записи до лимита
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        assert cache.size() == 2
        
        # Добавляем третью запись - должна удалиться самая старая
        cache.set("key3", "value3")
        assert cache.size() == 2
        
        # Первая запись должна быть удалена
        assert cache.get("key1") is None
        assert cache.get("key2") == "value2"
        assert cache.get("key3") == "value3"
    
    def test_clear_cache(self, ttl_cache):
        """Тестирует очистку кэша."""
        ttl_cache.set("key1", "value1")
        ttl_cache.set("key2", "value2")
        assert ttl_cache.size() == 2
        
        ttl_cache.clear()
        assert ttl_cache.size() == 0
        assert ttl_cache.get("key1") is None
        assert ttl_cache.get("key2") is None
    
    def test_remove_key(self, ttl_cache):
        """Тестирует удаление конкретного ключа."""
        ttl_cache.set("key1", "value1")
        ttl_cache.set("key2", "value2")
        assert ttl_cache.size() == 2
        
        ttl_cache.remove("key1")
        assert ttl_cache.size() == 1
        assert ttl_cache.get("key1") is None
        assert ttl_cache.get("key2") == "value2"
    
    def test_remove_nonexistent_key(self, ttl_cache):
        """Тестирует удаление несуществующего ключа."""
        ttl_cache.set("key1", "value1")
        initial_size = ttl_cache.size()
        
        # Удаление несуществующего ключа не должно вызывать ошибку
        ttl_cache.remove("nonexistent")
        assert ttl_cache.size() == initial_size


class TestCachedDecorator:
    """Тесты для декоратора кэширования."""
    
    @pytest.fixture
    def mock_service(self):
        """Мок сервиса с кэшем для тестирования декоратора."""
        class MockService:
            def __init__(self):
                self._cache = TTLCache(default_ttl=60, max_size=100)
                self.call_count = 0
            
            @cached(ttl=30)
            async def cached_method(self, arg1, arg2=None):
                """Метод с кэшированием для тестирования."""
                self.call_count += 1
                return f"result_{arg1}_{arg2}_{self.call_count}"
            
            @cached()
            async def cached_method_default_ttl(self, value):
                """Метод с кэшированием и дефолтным TTL."""
                self.call_count += 1
                return f"default_{value}_{self.call_count}"
        
        return MockService()
    
    @pytest.mark.asyncio
    async def test_cached_decorator_basic(self, mock_service):
        """Тестирует базовую функциональность декоратора кэширования."""
        # Первый вызов - должен выполниться
        result1 = await mock_service.cached_method("test", arg2="value")
        assert result1 == "result_test_value_1"
        assert mock_service.call_count == 1
        
        # Второй вызов с теми же параметрами - должен вернуть из кэша
        result2 = await mock_service.cached_method("test", arg2="value")
        assert result2 == "result_test_value_1"  # Тот же результат
        assert mock_service.call_count == 1  # Метод не вызывался повторно
    
    @pytest.mark.asyncio
    async def test_cached_decorator_different_params(self, mock_service):
        """Тестирует кэширование для разных параметров."""
        # Вызовы с разными параметрами должны кэшироваться отдельно
        result1 = await mock_service.cached_method("test1")
        result2 = await mock_service.cached_method("test2")
        result3 = await mock_service.cached_method("test1")  # Повторный вызов
        
        assert result1 == "result_test1_None_1"
        assert result2 == "result_test2_None_2"
        assert result3 == "result_test1_None_1"  # Из кэша
        assert mock_service.call_count == 2  # Только два реальных вызова
    
    @pytest.mark.asyncio
    async def test_cached_decorator_default_ttl(self, mock_service):
        """Тестирует декоратор с дефолтным TTL."""
        result1 = await mock_service.cached_method_default_ttl("test")
        result2 = await mock_service.cached_method_default_ttl("test")
        
        assert result1 == result2
        assert mock_service.call_count == 1
    
    @pytest.mark.asyncio
    async def test_cached_decorator_without_cache(self):
        """Тестирует поведение декоратора без кэша."""
        class ServiceWithoutCache:
            def __init__(self):
                self.call_count = 0
            
            @cached()
            async def method(self, value):
                self.call_count += 1
                return f"result_{value}_{self.call_count}"
        
        service = ServiceWithoutCache()
        
        # Без кэша каждый вызов должен выполняться
        result1 = await service.method("test")
        result2 = await service.method("test")
        
        assert result1 == "result_test_1"
        assert result2 == "result_test_2"
        assert service.call_count == 2
    
    @pytest.mark.asyncio
    async def test_cached_decorator_ttl_expiration(self):
        """Тестирует истечение TTL в декораторе."""
        class ShortTTLService:
            def __init__(self):
                self._cache = TTLCache(default_ttl=60, max_size=100)
                self.call_count = 0
            
            @cached(ttl=0.1)  # Очень короткий TTL
            async def method(self, value):
                self.call_count += 1
                return f"result_{value}_{self.call_count}"
        
        service = ShortTTLService()
        
        # Первый вызов
        result1 = await service.method("test")
        assert result1 == "result_test_1"
        assert service.call_count == 1
        
        # Повторный вызов сразу - из кэша
        result2 = await service.method("test")
        assert result2 == "result_test_1"
        assert service.call_count == 1
        
        # Ждем истечения TTL
        time.sleep(0.2)
        
        # Вызов после истечения TTL - должен выполниться заново
        result3 = await service.method("test")
        assert result3 == "result_test_2"
        assert service.call_count == 2 