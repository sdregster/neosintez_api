#!/usr/bin/env python
"""
Скрипт для локального запуска тестов neosintez_api.
"""

import argparse
import subprocess
import sys
from pathlib import Path


def run_command(cmd, description):
    """Запускает команду и выводит результат."""
    print(f"\n{'=' * 60}")
    print(f"🔄 {description}")
    print(f"{'=' * 60}")

    try:
        result = subprocess.run(cmd, shell=True, check=True, capture_output=False)
        print(f"✅ {description} - успешно")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} - ошибка (код {e.returncode})")
        return False


def main():
    parser = argparse.ArgumentParser(description="Запуск тестов neosintez_api")
    parser.add_argument(
        "--type",
        choices=["all", "unit", "integration", "coverage"],
        default="all",
        help="Тип тестов для запуска",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Подробный вывод")
    parser.add_argument(
        "--fail-fast", "-x", action="store_true", help="Остановиться при первой ошибке"
    )

    args = parser.parse_args()

    # Проверяем, что мы в корне проекта
    if not Path("neosintez_api").exists():
        print("❌ Запустите скрипт из корня проекта")
        sys.exit(1)

    print("🧪 Запуск тестов neosintez_api")
    print(f"📁 Рабочая директория: {Path.cwd()}")

    verbose_flag = "-v" if args.verbose else ""
    fail_fast_flag = "-x" if args.fail_fast else ""

    success = True

    if args.type in ["all", "unit"]:
        # Unit тесты
        success &= run_command(
            f"python -m pytest tests/test_type_mapping.py {verbose_flag} {fail_fast_flag}",
            "Unit тесты - маппинг типов",
        )

        success &= run_command(
            f"python -m pytest tests/test_cache.py {verbose_flag} {fail_fast_flag}",
            "Unit тесты - кэширование",
        )

        success &= run_command(
            f"python -m pytest tests/test_validation.py {verbose_flag} {fail_fast_flag}",
            "Unit тесты - валидация",
        )

    if args.type in ["all", "integration"]:
        # Интеграционные тесты
        success &= run_command(
            f"python -m pytest tests/test_integration.py {verbose_flag} {fail_fast_flag}",
            "Интеграционные тесты",
        )

    if args.type in ["all", "coverage"]:
        # Тесты с покрытием
        success &= run_command(
            f"python -m pytest tests/ --cov=neosintez_api --cov-report=term-missing --cov-report=html {verbose_flag}",
            "Все тесты с покрытием кода",
        )

        if success:
            print("\n📊 Отчет о покрытии создан в htmlcov/index.html")

    print(f"\n{'=' * 60}")
    if success:
        print("✅ Все тесты завершены успешно!")
        print("🎉 Задача 4 (Тестирование) выполнена!")
    else:
        print("❌ Некоторые тесты завершились с ошибками")
        sys.exit(1)
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
