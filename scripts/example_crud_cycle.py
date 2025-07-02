"""
Тестовый скрипт для демонстрации полного CRUD-цикла
(Create, Read, Update, Delete) с использованием DynamicModelFactory и ObjectService.
"""

import asyncio
import logging
import traceback
from uuid import uuid4

from neosintez_api.config import NeosintezConfig
from neosintez_api.core.client import NeosintezClient
from neosintez_api.services import DynamicModelFactory, ObjectService


# Настройка логирования для вывода детальной информации
logging.basicConfig(level=logging.INFO)
logging.getLogger("neosintez_api").setLevel(logging.INFO)


async def main():
    """
    Основной сценарий:
    1.  Определяем пользовательские данные для создания объекта.
    2.  Создаем "чертеж" (blueprint) и Pydantic-модель с помощью фабрики.
    3.  CREATE: Создаем объект в Неосинтезе.
    4.  READ: Читаем созданный объект и проверяем данные.
    5.  UPDATE: Обновляем атрибуты объекта.
    6.  READ (verify): Снова читаем объект для проверки обновления.
    7.  DELETE: Удаляем объект.
    8.  READ (verify): Пытаемся прочитать удаленный объект и убеждаемся, что его нет.
    """
    # Уникальный идентификатор для тестового объекта, чтобы избежать конфликтов
    test_id = str(uuid4())[:8]

    # 1. Определяем пользовательские данные
    user_defined_data = {
        "Класс": "Стройка",
        "Имя объекта": f"Тестовая стройка (CRUD) {test_id}",
        "МВЗ": f"МВЗ_PUBLIC_{test_id}",
        "ID стройки Адепт": 12345,
    }
    print(f"--- Исходные данные ---\n{user_defined_data}\n")

    # Инициализируем сервисы
    settings = NeosintezConfig()
    client = NeosintezClient(settings)
    factory = DynamicModelFactory(
        name_aliases=["Имя объекта", "Наименование"],
        class_name_aliases=["Класс", "Имя класса"],
    )
    object_service = ObjectService(client)

    created_object: any = None
    try:
        # 2. Создаем "чертеж" (blueprint) с помощью фабрики
        print("--- Этап 1: Создание Pydantic-модели ---")

        # Получаем метаданные для класса перед вызовом фабрики
        class_name_to_find = user_defined_data["Класс"]
        class_info_list = await client.classes.get_classes_by_name(class_name_to_find)
        if not class_info_list:
            raise ValueError(f"Класс '{class_name_to_find}' не найден")

        class_info = next(c for c in class_info_list if c["name"].lower() == class_name_to_find.lower())
        class_id = class_info["id"]
        class_attributes = await client.classes.get_attributes(class_id)
        attributes_meta_map = {attr.Name: attr for attr in class_attributes}

        blueprint = await factory.create_from_user_data(
            user_data=user_defined_data,
            class_name=class_name_to_find,
            class_id=class_id,
            attributes_meta=attributes_meta_map,
        )
        print("Pydantic-модель для создания:")
        print(blueprint.model_instance.model_dump_json(indent=2))
        print("-" * 20 + "\n")

        # 3. CREATE: Создаем объект в Неосинтезе
        print("--- Этап 2: CREATE ---")
        created_object = await object_service.create(
            model=blueprint.model_instance,
            class_id=blueprint.class_id,
            class_name=blueprint.class_name,
            attributes_meta=blueprint.attributes_meta,
            parent_id=settings.test_folder_id,
        )
        print(f"Объект успешно создан. ID: {created_object.id}\n")

        # 4. READ: Читаем созданный объект
        print("--- Этап 3: READ ---")
        read_object = await object_service.read(created_object.id, blueprint.model_class)
        print("Прочитанный объект:")
        print(read_object.model_dump_json(indent=2))
        # Проверка
        assert read_object.name == user_defined_data["Имя объекта"]
        assert read_object.id_stroyki_adept == user_defined_data["ID стройки Адепт"]
        print("Данные прочитанного объекта соответствуют исходным.\n")

        # 5. UPDATE: Обновляем имя, атрибуты и родителя
        print("--- Этап 4: UPDATE ---")
        read_object.name = f"ОБНОВЛЕННАЯ стройка (CRUD) {test_id}"
        read_object.mvz = f"МВЗ_NEW_{test_id}"
        read_object.id_stroyki_adept = 99999
        # Перемещаем объект в другую папку
        read_object.parent_id = settings.test_folder_id_2

        await object_service.update(read_object, attributes_meta=blueprint.attributes_meta)
        print("Отправлен запрос на обновление и перемещение объекта.\n")

        # 6. READ (verify): Снова читаем объект для проверки обновления
        print("--- Этап 5: READ (проверка обновления) ---")
        reread_object = await object_service.read(created_object.id, blueprint.model_class)
        print("Повторно прочитанный объект после обновления:")
        print(reread_object.model_dump_json(indent=2))
        # Проверка
        assert reread_object.name == read_object.name
        assert reread_object.mvz == read_object.mvz
        assert reread_object.id_stroyki_adept == read_object.id_stroyki_adept
        assert reread_object.parent_id == settings.test_folder_id_2
        print("Данные объекта и его расположение успешно обновлены.\n")

    except Exception as e:
        print(f"\nОшибка при выполнении: {e}")
        traceback.print_exc()

    finally:
        # 7. DELETE: Удаляем объект в любом случае (если он был создан)
        if created_object and created_object.id:
            print("--- Этап 6: DELETE ---")
            delete_success = await object_service.delete(created_object.id)
            if delete_success:
                print(f"Объект {created_object.id} успешно удален.\n")

                # 8. READ (verify): Пытаемся прочитать удаленный объект
                print("\n--- Этап 7: READ (проверка удаления) ---")
                try:
                    await object_service.read(created_object.id, blueprint.model_class)
                    # Если мы дошли сюда, значит, объект не удалился. Это ошибка.
                    print(f"ОШИБКА: Объект {created_object.id} все еще существует после удаления.")
                except Exception as e:
                    # Мы ожидаем ошибку, которая будет указывать на отсутствие объекта.
                    # В идеале это должна быть специфичная ошибка API (например, 404 Not Found),
                    # но для простоты примера ловим общее исключение.
                    print(f"Проверка удаления прошла успешно: объект не найден (получена ошибка: {e})")

        await client.close()
        print("\nСоединение с клиентом закрыто.")


if __name__ == "__main__":
    asyncio.run(main())
