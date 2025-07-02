"""
Тестовый скрипт для демонстрации работы DynamicModelFactory.

Скрипт показывает, как фабрика обрабатывает простые типы данных (строки, числа)
и разрешает ссылочные атрибуты, превращая текстовые значения ("Да")
в реальные идентификаторы объектов (GUID) из связанных справочников.
"""

import asyncio
import traceback

from neosintez_api.core.client import NeosintezClient
from neosintez_api.services import DynamicModelFactory
from neosintez_api.utils import generate_field_name


async def main():
    """
    Основной сценарий:
    1. Определяем пользовательские данные.
    2. Создаем и настраиваем фабрику.
    3. Используем фабрику для получения "чертежа" объекта.
    4. Выводим результат.
    """
    user_defined_data = {
        "Класс": "Стройка",
        "Имя объекта": "Тестовая стройка из API со ссылкой",
        "МВЗ": "МВЗ_PUBLIC_777",
        "ID стройки Адепт": 54321,
        "ИР Адепт - Primavera": "Да",
    }

    """
    StroykaModel:
    _class_id: "c56370d8-ad8f-ec11-911d-005056b6948b"
    _class_name: "Стройка"
    _attributes_meta: ...

    name: "Тестовая стройка из API со ссылкой"
    mvz: "МВЗ_PUBLIC_777"
    id_stroyki_adep: 54321
    ir_adep_primavera: "Да"
    """

    client = NeosintezClient()

    # Инициализируем фабрику с клиентом и возможными названиями ключевых полей
    factory = DynamicModelFactory(
        client=client,
        name_aliases=["Имя объекта", "Наименование", "Name"],
        class_name_aliases=["Класс", "Имя класса", "className"],
    )

    try:
        # Получаем метаданные для класса перед вызовом фабрики
        class_name_to_find = user_defined_data["Класс"]
        class_info_list = await client.classes.get_classes_by_name(class_name_to_find)
        if not class_info_list:
            raise ValueError(f"Класс '{class_name_to_find}' не найден")

        class_info = next(c for c in class_info_list if c["name"].lower() == class_name_to_find.lower())
        class_id = class_info["id"]
        class_attributes = await client.classes.get_attributes(class_id)
        attributes_meta_map = {attr.Name: attr for attr in class_attributes}

        # Используем фабрику для получения "чертежа" объекта
        blueprint = await factory.create_from_user_data(
            user_data=user_defined_data,
            class_name=class_name_to_find,
            class_id=class_id,
            attributes_meta=attributes_meta_map,
        )

        print("\n--- Итог ---")
        print(f"Класс для создания в Неосинтез: '{blueprint.class_name}'")
        print(f"Имя объекта для создания: '{blueprint.model_instance.name}'")
        print("\nГотовая Pydantic-модель с атрибутами:")
        print(blueprint.model_instance.model_dump_json(by_alias=True, indent=4))

        print("\nПроверка доступа к полю 'МВЗ':")
        mvz_field_name = generate_field_name("МВЗ")
        print(f"  - blueprint.model_instance.{mvz_field_name} = {getattr(blueprint.model_instance, mvz_field_name)}")

        print("\nПроверка доступа к ссылочному полю 'ИР Адепт - Primavera':")
        primavera_field_name = generate_field_name("ИР Адепт - Primavera")
        primavera_value = getattr(blueprint.model_instance, primavera_field_name)
        print(f"  - blueprint.model_instance.{primavera_field_name} = {primavera_value}")
        print(f"  - Обратите внимание, что строковое значение 'Да' было преобразовано в ID объекта: {primavera_value}")

    except Exception as e:
        print(f"\nОшибка при выполнении: {e}")
        traceback.print_exc()
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
