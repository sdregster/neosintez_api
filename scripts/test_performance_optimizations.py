"""
Автоматический тест производительности оптимизированного импорта Excel.
"""

import asyncio
import logging
import time
from pathlib import Path

from neosintez_api.core.client import NeosintezClient
from neosintez_api.services.excel_importer import ExcelImporter


# Настройка логирования
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Конфигурация
EXCEL_FILE_PATH = "data/Neosintez_Template_06-13 Сети канализации (смета к договору).xlsx"
PARENT_OBJECT_ID = "001847f9-f044-f011-91e3-005056b6948b"


async def test_performance():
    """Тестирует производительность оптимизированного импорта"""

    if not Path(EXCEL_FILE_PATH).exists():
        print(f"❌ Файл не найден: {EXCEL_FILE_PATH}")
        return

    print("🚀 Запуск теста производительности оптимизированного импорта...")
    print("=" * 80)

    client = NeosintezClient()
    try:
        importer = ExcelImporter(client)

        # Этап 1: Предварительный просмотр
        print("📋 Этап 1: Предварительный просмотр импорта...")
        start_time = time.time()

        preview = await importer.preview_import(EXCEL_FILE_PATH, PARENT_OBJECT_ID)

        preview_time = time.time() - start_time
        print(f"✅ Предварительный просмотр завершен за {preview_time:.2f} сек")
        print(f"   📊 Объектов для создания: {preview.estimated_objects}")
        print(f"   📊 Классов найдено: {len(preview.structure.classes_found)}")

        if preview.validation_errors:
            print("❌ Обнаружены ошибки валидации:")
            for error in preview.validation_errors[:3]:  # Показываем первые 3 ошибки
                print(f"   - {error}")
            return

        # Этап 2: Импорт с оптимизациями
        print("\n🔥 Этап 2: ОПТИМИЗИРОВАННЫЙ импорт...")
        print("   🚀 Используем параллельную обработку")
        print("   🚀 Используем предварительное кэширование классов")
        print("   🚀 Используем batch установку атрибутов")

        import_start = time.time()

        result = await importer.import_from_excel(EXCEL_FILE_PATH, PARENT_OBJECT_ID)

        import_time = time.time() - import_start
        total_time = time.time() - start_time

        # Результаты
        print("\n" + "=" * 80)
        print("📈 РЕЗУЛЬТАТЫ ОПТИМИЗИРОВАННОГО ИМПОРТА:")
        print("=" * 80)
        print(f"✅ Создано объектов: {result.total_created}")
        print(f"⏱️  Время импорта: {import_time:.2f} сек")
        print(f"⏱️  Общее время: {total_time:.2f} сек")

        if result.total_created > 0:
            avg_time = import_time / result.total_created
            print(f"📊 Среднее время на объект: {avg_time:.3f} сек")

            # Сравнение с предыдущими результатами
            old_avg_time = 0.43  # Из предыдущих измерений
            improvement = ((old_avg_time - avg_time) / old_avg_time) * 100
            print(f"🚀 Улучшение производительности: {improvement:.1f}%")

            if improvement > 0:
                print(f"🎉 ОПТИМИЗАЦИЯ УСПЕШНА! Ускорение в {old_avg_time / avg_time:.1f}x раз")

        print("\n📊 Объектов по уровням:")
        for level, count in sorted(result.created_by_level.items()):
            print(f"   - Уровень {level}: {count} объектов")

        if result.errors:
            print(f"\n❌ Ошибки ({len(result.errors)}):")
            for error in result.errors[:5]:  # Показываем первые 5 ошибок
                print(f"   - {error}")

        if result.warnings:
            print(f"\n⚠️  Предупреждения ({len(result.warnings)}):")
            for warning in result.warnings[:3]:  # Показываем первые 3 предупреждения
                print(f"   - {warning}")

    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        import traceback

        traceback.print_exc()
    finally:
        await client.close()
        print("\n🔒 Соединение с API закрыто")


if __name__ == "__main__":
    asyncio.run(test_performance())
