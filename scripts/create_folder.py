"""
Скрипт для создания объекта типа "Папка МВЗ" в Neosintez.
"""

import asyncio
import argparse
import logging
import sys
import traceback
from uuid import UUID

# Загрузка переменных окружения из .env файла
from dotenv import load_dotenv

from neosintez_api.client import NeosintezClient
from neosintez_api.config import load_settings
from neosintez_api.exceptions import NeosintezAuthError, NeosintezConnectionError

load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("neosintez_create_folder")


async def create_folder(parent_id: str, folder_name: str):
    """
    Создает объект типа "Папка МВЗ" с указанным именем.
    
    Args:
        parent_id: ID родительского объекта
        folder_name: Имя создаваемой папки
        
    Returns:
        str: ID созданного объекта
    """
    # Загрузка настроек из переменных окружения
    settings = load_settings()
    logger.info(f"Загружены настройки для подключения к {settings.base_url}")
    
    # Инициализация клиента API
    async with NeosintezClient(settings) as client:
        try:
            # Аутентификация
            logger.info("Попытка аутентификации...")
            token = await client.auth()
            logger.info(f"Получен токен: {token[:10]}...")
            
            # Получение объекта класса "Папка МВЗ" из списка всех классов
            logger.info("Получение списка классов объектов из Neosintez")
            entities = await client.classes.get_all()
            
            # Поиск класса "Папка МВЗ"
            folder_class = None
            for entity in entities:
                if entity.Name == "Папка МВЗ":
                    folder_class = entity
                    break
                
            if not folder_class:
                logger.error("Класс 'Папка МВЗ' не найден в Neosintez")
                return None
                
            logger.info(f"Найден класс 'Папка МВЗ' (ID: {folder_class.Id})")
            
            # Создаем данные для запроса
            data = {
                "Name": folder_name,
                "Entity": {
                    "Id": str(folder_class.Id), 
                    "Name": folder_class.Name
                },
                # Обязательные поля для WioObjectNode
                "IsActualVersion": True,
                "Version": 1,
                "VersionTimestamp": "2023-01-01T00:00:00Z",
            }
            
            # Вызываем API для создания объекта
            logger.info(f"Создание папки '{folder_name}' в родительском объекте {parent_id}")
            created_id = await client.objects.create(parent_id=parent_id, data=data)
            
            logger.info(f"Папка МВЗ успешно создана. ID: {created_id}")
            
            # Проверяем, что объект действительно создан
            try:
                created_obj = await client.objects.get_by_id(created_id)
                logger.info(f"Объект проверен: {created_obj.Name} (ID: {created_obj.Id})")
            except Exception as e:
                logger.error(f"Ошибка при проверке созданного объекта: {str(e)}")
                
            return created_id
            
        except NeosintezAuthError as e:
            logger.error(f"Ошибка аутентификации: {str(e)}")
        except NeosintezConnectionError as e:
            logger.error(f"Ошибка соединения: {str(e)}")
        except Exception:
            logger.error(f"Неожиданная ошибка: {traceback.format_exc()}")
            
    return None


async def main():
    """
    Основная функция для запуска создания папки.
    """
    try:
        # Парсим аргументы командной строки
        parser = argparse.ArgumentParser(description="Создание объекта типа 'Папка МВЗ' в Neosintez")
        parser.add_argument("--name", default="Новая папка", help="Имя создаваемой папки (по умолчанию: 'Новая папка')")
        parser.add_argument("--parent", default="e8ca0ee1-e750-f011-91e5-005056b6948b", 
                            help="ID родительского объекта (по умолчанию: e8ca0ee1-e750-f011-91e5-005056b6948b)")
        args = parser.parse_args()
        
        # ID родительского объекта и имя папки
        parent_id = args.parent
        folder_name = args.name
        
        logger.info(f"Запуск создания папки '{folder_name}' в родительском объекте {parent_id}")
        
        # Создаем папку
        created_id = await create_folder(parent_id, folder_name)
        
        if created_id:
            logger.info(f"Папка МВЗ '{folder_name}' успешно создана с ID: {created_id}")
        else:
            logger.error("Не удалось создать папку")
            sys.exit(1)
            
    except Exception:
        logger.error(f"Ошибка при выполнении скрипта: {traceback.format_exc()}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Прервано пользователем")
    except Exception:
        logger.error(f"Критическая ошибка: {traceback.format_exc()}")
        sys.exit(1)
