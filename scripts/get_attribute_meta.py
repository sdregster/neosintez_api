import asyncio
import json

from neosintez_api.core.client import NeosintezClient


async def main():
    """
    Этот скрипт получает и выводит метаданные для конкретного атрибута класса.
    """
    CLASS_NAME_TO_FIND = "Стройка"
    ATTRIBUTE_NAME_TO_FIND = "ИР Адепт - Primavera"

    client = NeosintezClient()
    try:
        print(f"Поиск класса '{CLASS_NAME_TO_FIND}'...")
        class_info_list = await client.classes.get_classes_by_name(CLASS_NAME_TO_FIND)
        if not class_info_list:
            raise ValueError(f"Класс '{CLASS_NAME_TO_FIND}' не найден")

        class_info = next(
            c for c in class_info_list if c["name"].lower() == CLASS_NAME_TO_FIND.lower()
        )
        class_id = class_info["id"]
        print(f"Класс найден, ID: {class_id}")

        print(f"Получение атрибутов для класса...")
        class_attributes = await client.classes.get_attributes(class_id)

        found_attribute = None
        for attr in class_attributes:
            if attr.Name == ATTRIBUTE_NAME_TO_FIND:
                found_attribute = attr
                break
        
        if not found_attribute:
            raise ValueError(f"Атрибут '{ATTRIBUTE_NAME_TO_FIND}' не найден в классе '{CLASS_NAME_TO_FIND}'")

        print("\\n" + "="*80)
        print(f"МЕТАДАННЫЕ АТРИБУТА: '{ATTRIBUTE_NAME_TO_FIND}'")
        print("="*80)
        # Выводим в формате JSON для наглядности
        print(json.dumps(found_attribute.model_dump(), indent=4, ensure_ascii=False))
        print("="*80 + "\\n")

    except Exception as e:
        print(f"\\nОшибка: {e}")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main()) 