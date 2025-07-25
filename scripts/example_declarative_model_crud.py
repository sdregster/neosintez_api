"""
Пример использования декларативной Pydantic-модели для работы с API.

Этот скрипт демонстрирует полный CRUD-цикл (создание, чтение, обновление,
удаление) для объектов Неосинтеза, используя декларативные модели.
Это скрывает сложность API за чистым, типизированным интерфейсом.
"""

import logging

from pydantic import Field

from neosintez_api import NeosintezClient
from neosintez_api.config import settings
from neosintez_api.models import NeosintezBaseModel
from neosintez_api.services.object_service import ObjectService


# Настройка логирования для отладки
logging.basicConfig(level=logging.INFO)
logging.getLogger("neosintez_api").setLevel(logging.DEBUG)


def print_header(title: str):
    """Печатает красивый заголовок для секции."""
    print(f"\n{'=' * 70}\n>>> {title.upper()}\n{'=' * 70}")


# 1. Определение декларативной модели
#    Пользователь наследуется от NeosintezBaseModel и описывает
#    поля своего объекта, используя стандартные механизмы Pydantic.
class StroykaModel(NeosintezBaseModel):
    """Модель для объекта 'Объект капитальных вложений'."""

    # Внутренний класс Neosintez используется для связи
    # этой модели с конкретным классом в Неосинтезе.
    class Neosintez:
        class_name = "Объект капитальных вложений"  # Указываем имя класса как в Неосинтезе

    # Поля модели. Алиасы - это названия атрибутов в Неосинтезе.
    # Это позволяет иметь в Python валидные имена полей.
    name: str = Field(..., description="Имя объекта")
    mvz: str = Field(..., alias="МВЗ")
    id_stroyki_adep: int = Field(..., alias="ID стройки Адепт")
    # Для ссылочного атрибута мы просто указываем строковый тип.
    # "Под капотом" сервис сам найдет нужный объект по имени.
    ir_adep_primavera: str = Field(..., alias="ИР Адепт - Primavera")
    procent_komplekta: float = Field(..., alias="Процент комплектации")


async def main():
    """Основная функция."""
    client = NeosintezClient()
    object_service = ObjectService(client)
    created_object_id = None

    def wait_for_user_input(object_id: str | None, step_name: str):
        """Формирует ссылку на объект и ждет ввода от пользователя."""
        if object_id:
            # Убираем возможный слэш в конце, чтобы избежать двойных //
            base_url = str(settings.base_url).rstrip("/")
            object_url = f"{base_url}/objects?id={object_id}"
            print(f"\n--- Шаг '{step_name}' завершен ---")
            print(f"Ссылка на объект для проверки: {object_url}")
            input(">>> Нажмите Enter для перехода к следующему шагу...")

    try:
        # ======================================================================
        # 1. CREATE: Создание объекта в Неосинтезе
        # ======================================================================
        print_header("1. CREATE: Создание объекта")
        stroyka_instance = StroykaModel(
            name="Тестовая стройка CRUD",
            mvz="МВЗ_PUBLIC_123",
            id_stroyki_adep=12345,
            ir_adep_primavera="Да",  # Указываем человекочитаемое значение
            procent_komplekta=80.5,
        )
        print("Модель для создания:")
        print(stroyka_instance.model_dump_json(indent=2, by_alias=True))

        created_object = await object_service.create(stroyka_instance, parent_id=settings.test_folder_id)
        created_object_id = created_object._id
        print("\nОбъект успешно создан:")
        print(created_object.model_dump_json(indent=2, by_alias=True))

        print("\n--- Проверка CREATE ---")
        assert created_object._id is not None
        assert created_object.name == stroyka_instance.name
        assert created_object.mvz == stroyka_instance.mvz
        assert created_object.ir_adep_primavera == "Да"
        assert created_object.procent_komplekta == 80.5
        print("✓ Проверка CREATE пройдена.")

        wait_for_user_input(created_object_id, "CREATE")

        # ======================================================================
        # 2. READ: Чтение созданного объекта
        # ======================================================================
        print_header("2. READ: Чтение созданного объекта")
        read_object = await object_service.read(created_object_id, StroykaModel)
        print("Объект успешно прочитан:")
        print(read_object.model_dump_json(indent=2, by_alias=True))

        print("\n--- Проверка READ ---")
        assert read_object.name == "Тестовая стройка CRUD"
        assert read_object.mvz == "МВЗ_PUBLIC_123"
        assert read_object._id == created_object_id
        assert read_object.procent_komplekta == 80.5
        print("✓ Проверка READ пройдена.")

        # ======================================================================
        # 3. UPDATE: Обновление атрибутов и родителя
        # ======================================================================
        print_header("3. UPDATE: Обновление атрибутов и родителя")
        read_object.name = "Новое имя объекта"
        read_object.mvz = "NEW_MVZ_ABC"
        read_object.ir_adep_primavera = "Нет"
        read_object._parent_id = settings.test_folder_id_2

        print("Модель для обновления:")
        print(read_object.model_dump_json(indent=2, by_alias=True))

        updated_object = await object_service.update(read_object)
        print("\nОбъект успешно обновлен. Ответ от сервиса:")
        print(updated_object.model_dump_json(indent=2, by_alias=True))

        print("\n--- Проверка UPDATE ---")
        re_read_object = await object_service.read(created_object_id, StroykaModel)
        assert re_read_object.name == "Новое имя объекта"
        assert re_read_object.mvz == "NEW_MVZ_ABC"
        assert re_read_object.ir_adep_primavera == "Нет"
        assert re_read_object._parent_id == settings.test_folder_id_2
        assert updated_object == re_read_object
        assert re_read_object.procent_komplekta == 80.5
        print("✓ Проверка UPDATE пройдена: имя, атрибут и родитель обновлены.")
        print("✓ Ответ от `update` соответствует данным в системе.")

        wait_for_user_input(created_object_id, "UPDATE (1/2)")

        # ======================================================================
        # 4. UPDATE (CHAINED): Повторное обновление
        # ======================================================================
        print_header("4. UPDATE (цепочка): Повторное обновление")
        print("Используем модель, возвращенную после первого обновления.")

        updated_object.name = "Финальное имя после второго обновления"
        updated_object.mvz = "FINAL_MVZ"

        print("\nМодель для второго обновления:")
        print(updated_object.model_dump_json(indent=2, by_alias=True))

        final_updated_object = await object_service.update(updated_object)
        print("\nОбъект успешно обновлен во второй раз. Финальная модель от сервиса:")
        print(final_updated_object.model_dump_json(indent=2, by_alias=True))

        print("\n--- Финальная проверка ---")
        final_read_object = await object_service.read(created_object_id, StroykaModel)

        # Сверяем заданные значения с прочитанными из системы
        assert final_read_object.name == "Финальное имя после второго обновления"
        assert final_read_object.mvz == "FINAL_MVZ"
        assert final_read_object._parent_id == settings.test_folder_id_2
        assert final_read_object.procent_komplekta == 80.5

        # Сверяем значения, возвращенные методом update, с заданными
        assert final_updated_object.name == "Финальное имя после второго обновления"
        assert final_updated_object.mvz == "FINAL_MVZ"
        assert final_updated_object.procent_komplekta == 80.5
        # Убеждаемся, что модель из update и модель из read идентичны
        assert final_read_object == final_updated_object

        print("✓ Проверка второго UPDATE пройдена: финальное имя и атрибут корректны.")
        print("✓ Ответ от `update` полностью соответствует данным в системе.")

        wait_for_user_input(created_object_id, "UPDATE (2/2)")

        # ======================================================================
        # 5. DELETE
        # ======================================================================
        print_header("5. DELETE: Перемещение в корзину")
        await object_service.delete(created_object_id)
        print(f"Объект с ID {created_object_id} успешно перемещен в корзину.")

    except Exception as e:
        logging.error(f"Произошла фатальная ошибка в процессе выполнения: {e}", exc_info=True)

    finally:
        # ======================================================================
        # FINALLY: Очистка
        # ======================================================================
        print_header("Очистка")
        if created_object_id:
            await object_service.delete(created_object_id)
        await client.close()
        print("\nКлиент закрыт. Скрипт завершен.")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
