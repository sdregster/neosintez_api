"""
Тестовый скрипт для демонстрации работы DynamicModelFactory.

Скрипт показывает, как фабрика на лету создает типизированную
Pydantic-модель из словаря с данными, а затем использует эту модель
для создания, чтения и удаления объекта в Неосинтезе через ObjectService.
"""

import asyncio
import logging
import traceback
from uuid import UUID

from neosintez_api.config import settings
from neosintez_api.core.client import NeosintezClient
from neosintez_api.services import ClassService, DynamicModelFactory, ObjectService


# Настройка логирования для отладки
logging.basicConfig(level=logging.INFO)
logging.getLogger("neosintez_api").setLevel(logging.DEBUG)


def print_header(title: str):
    """Печатает красивый заголовок для секции."""
    print(f"\n{'=' * 70}\n>>> {title.upper()}\n{'=' * 70}")


async def main():
    """
    Основной сценарий:
    1. Определяем пользовательские данные в виде словаря.
    2. Используем DynamicModelFactory для создания Pydantic-модели.
    3. Используем ObjectService для создания объекта из этой модели (CREATE).
    4. Читаем созданный объект обратно в модель (READ).
    5. Удаляем тестовый объект (DELETE).
    """
    user_defined_data = {
        "Класс": "Стройка",
        "Имя объекта": "Динамическая стройка из фабрики",
        "МВЗ": "МВЗ_DYNAMIC_999",
        "ID стройки Адепт": 98765,
        "ИР Адепт - Primavera": "Да",  # Это значение будет разрешено в ID
    }

    client = NeosintezClient()
    object_service = ObjectService(client)
    class_service = ClassService(client)  # Создаем сервис для работы с кэшем
    created_object_id: UUID | None = None

    def wait_for_user_input(object_id: UUID | None, step_name: str):
        """Формирует ссылку на объект и ждет ввода от пользователя."""
        if object_id:
            # Убираем возможный слэш в конце, чтобы избежать двойных //
            base_url = str(settings.base_url).rstrip("/")
            object_url = f"{base_url}/objects?id={object_id}"
            print(f"\n--- Шаг '{step_name}' завершен ---")
            print(f"Ссылка на объект для проверки: {object_url}")
            input(">>> Нажмите Enter для перехода к следующему шагу...")

    # Инициализируем фабрику с клиентом и возможными названиями ключевых полей
    factory = DynamicModelFactory(
        client=client,
        class_service=class_service,  # Передаем сервис с кэшем
        name_aliases=["Имя объекта", "Наименование", "Name"],
        class_name_aliases=["Класс", "Имя класса", "className"],
    )

    try:
        # ======================================================================
        # 1. DYNAMIC MODEL CREATION: Создание модели "на лету"
        # ======================================================================
        print_header("1. Создание динамической модели из словаря")

        # Используем фабрику для получения "чертежа" объекта.
        # Вся "магия" (поиск класса, получение атрибутов) скрыта внутри.
        blueprint = await factory.create(user_defined_data)

        model_instance = blueprint.model_instance
        DynamicModel = blueprint.model_class

        print("Фабрика успешно создала Pydantic-модель:")
        print(f"  - Имя класса: {DynamicModel.Neosintez.class_name}")
        print("  - Сгенерированная модель:")
        print(model_instance.model_dump_json(by_alias=True, indent=4))
        print("✓ Модель готова к использованию в ObjectService.")

        # ======================================================================
        # 2. CREATE: Создание объекта в Неосинтезе
        # ======================================================================
        print_header("2. CREATE: Создание объекта с помощью динамической модели")
        created_object = await object_service.create(model_instance, parent_id=settings.test_folder_id)
        created_object_id = created_object._id
        print("\nОбъект успешно создан:")
        print(created_object.model_dump_json(indent=2, by_alias=True))

        print("\n--- Проверка CREATE ---")
        assert created_object._id is not None
        assert created_object.name == user_defined_data["Имя объекта"]
        assert created_object.mvz == user_defined_data["МВЗ"]
        print("✓ Проверка CREATE пройдена.")

        wait_for_user_input(created_object_id, "CREATE")

        # ======================================================================
        # 3. READ: Чтение созданного объекта
        # ======================================================================
        print_header("3. READ: Чтение созданного объекта")
        read_object = await object_service.read(created_object_id, DynamicModel)
        print("Объект успешно прочитан:")
        print(read_object.model_dump_json(indent=2, by_alias=True))

        print("\n--- Проверка READ ---")
        assert read_object.name == user_defined_data["Имя объекта"]
        assert read_object.mvz == user_defined_data["МВЗ"]
        assert read_object._id == created_object_id
        # Ссылочный атрибут должен быть не строкой, а ID (str(UUID))
        assert isinstance(read_object.ir_adept_primavera, str)
        print("✓ Проверка READ пройдена.")

        # ======================================================================
        # 4. UPDATE: Обновление атрибутов и родителя
        # ======================================================================
        print_header("4. UPDATE: Обновление атрибутов и родителя")

        read_object.name = "Динамическая стройка (обновлено)"
        read_object.mvz = "NEW_DYNAMIC_MVZ_000"
        read_object.ir_adept_primavera = "Нет"  # Проверяем разрешение строки в ID
        read_object._parent_id = settings.test_folder_id_2  # Обновляем родителя

        print("Модель для обновления:")
        print(read_object.model_dump_json(by_alias=True, indent=2))

        updated_object = await object_service.update(read_object)
        print("\nОбъект успешно обновлен. Ответ от сервиса:")
        print(updated_object.model_dump_json(by_alias=True, indent=2))

        print("\n--- Проверка UPDATE ---")
        re_read_object = await object_service.read(created_object_id, DynamicModel)
        assert re_read_object.name == "Динамическая стройка (обновлено)"
        assert re_read_object.mvz == "NEW_DYNAMIC_MVZ_000"
        assert re_read_object.ir_adept_primavera == "Нет"
        assert re_read_object._parent_id == settings.test_folder_id_2
        # Убеждаемся, что модель из ответа `update` соответствует данным в системе
        assert updated_object == re_read_object
        print("✓ Проверка UPDATE пройдена: имя, атрибуты и родитель обновлены.")

        wait_for_user_input(created_object_id, "UPDATE (1/2)")

        # ======================================================================
        # 5. UPDATE (CHAINED): Повторное обновление
        # ======================================================================
        print_header("5. UPDATE (цепочка): Повторное обновление")
        print("Используем модель, возвращенную после первого обновления.")

        updated_object.name = "Финальное имя после второго обновления"
        updated_object.mvz = "FINAL_MVZ"

        print("\nМодель для второго обновления:")
        print(updated_object.model_dump_json(indent=2, by_alias=True))

        final_updated_object = await object_service.update(updated_object)
        print("\nОбъект успешно обновлен во второй раз. Финальная модель от сервиса:")
        print(final_updated_object.model_dump_json(indent=2, by_alias=True))

        print("\n--- Финальная проверка ---")
        final_read_object = await object_service.read(created_object_id, DynamicModel)

        # Сверяем заданные значения с прочитанными из системы
        assert final_read_object.name == "Финальное имя после второго обновления"
        assert final_read_object.mvz == "FINAL_MVZ"
        assert final_read_object._parent_id == settings.test_folder_id_2

        # Сверяем значения, возвращенные методом update, с заданными
        assert final_updated_object.name == "Финальное имя после второго обновления"
        assert final_updated_object.mvz == "FINAL_MVZ"

        # Убеждаемся, что модель из update и модель из read идентичны
        assert final_read_object == final_updated_object

        print("✓ Проверка второго UPDATE пройдена: финальное имя и атрибут корректны.")
        print("✓ Ответ от `update` полностью соответствует данным в системе.")

        wait_for_user_input(created_object_id, "UPDATE (2/2)")

    except Exception as e:
        print(f"\nПроизошла фатальная ошибка: {e}")
        traceback.print_exc()
    finally:
        # ======================================================================
        # FINALLY: Очистка
        # ======================================================================
        print_header("Очистка")
        if created_object_id:
            try:
                print(f"Попытка удаления тестового объекта {created_object_id}...")
                await object_service.delete(created_object_id)
                print(f"✓ Тестовый объект {created_object_id} успешно удален.")
            except Exception as e:
                print(f"Ошибка при удалении объекта {created_object_id}: {e}")
        else:
            print("Нечего удалять, тестовый объект не был создан.")

        await client.close()
        print("\nКлиент закрыт. Скрипт завершен.")


if __name__ == "__main__":
    asyncio.run(main())
