import asyncio

import click
from rich.console import Console
from rich.table import Table

from neosintez_api.config import NeosintezConfig
from neosintez_api.core.client import NeosintezClient
from neosintez_api.services.excel_importer import ExcelImporter


@click.group(name="import")
def import_():
    """
    Импорт данных (Excel и др.)
    """
    pass


@import_.command("excel")
@click.option("--file", "file_path", required=True, type=click.Path(exists=True), help="Путь к Excel-файлу")
@click.option("--parent", "parent_id", required=True, help="ID родительского объекта")
@click.option("--sheet", "sheet_name", help="Имя листа Excel (по умолчанию первый лист)")
@click.option("--preview", is_flag=True, help="Только показать предварительный просмотр")
@click.option("--dry-run", is_flag=True, help="Только проверить структуру файла")
def excel(file_path, parent_id, sheet_name, preview, dry_run):
    """
    Иерархический импорт объектов из Excel-файла по уровням.
    Автоматически определяет структуру файла и создает объекты уровень за уровнем.
    """
    console = Console()

    async def run_import():
        try:
            # Инициализация клиента
            settings = NeosintezConfig()
            async with NeosintezClient(settings) as client:
                importer = ExcelImporter(client)

                # Анализ структуры файла
                console.print(f"[blue]Анализ структуры файла:[/] {file_path}")
                structure = await importer.analyze_structure(file_path, sheet_name)

                # Показываем структуру
                table = Table(title="Структура Excel файла")
                table.add_column("Параметр", style="cyan")
                table.add_column("Значение", style="green")

                table.add_row("Колонка уровня", str(structure.level_column))
                table.add_row("Колонка класса", str(structure.class_column))
                table.add_row("Колонка имени", str(structure.name_column))
                table.add_row("Колонки атрибутов", str(len(structure.attribute_columns)))
                table.add_row("Всего строк", str(structure.total_rows))
                table.add_row("Максимальный уровень", str(structure.max_level))
                table.add_row("Найденные классы", ", ".join(structure.classes_found))

                console.print(table)

                if dry_run:
                    console.print("[yellow]Режим dry-run. Анализ структуры завершен.[/]")
                    return

                # Предварительный просмотр
                console.print("[blue]Предварительный просмотр импорта...[/]")
                preview_result = await importer.preview_import(file_path, parent_id, sheet_name)

                # Показываем предварительный просмотр
                preview_table = Table(title="Предварительный просмотр импорта")
                preview_table.add_column("Уровень", style="cyan")
                preview_table.add_column("Количество объектов", style="green")
                preview_table.add_column("Примеры объектов", style="yellow")

                objects_by_level = {}
                for obj in preview_result.objects_to_create:
                    level = obj["level"]
                    if level not in objects_by_level:
                        objects_by_level[level] = []
                    objects_by_level[level].append(obj)

                for level, objects in sorted(objects_by_level.items()):
                    examples = ", ".join([obj["name"] for obj in objects[:3]])
                    if len(objects) > 3:
                        examples += f" (и еще {len(objects) - 3})"
                    preview_table.add_row(str(level), str(len(objects)), examples)

                console.print(preview_table)
                console.print(f"[green]Всего ожидается объектов: {preview_result.estimated_objects}[/]")

                # Проверяем ошибки валидации
                if preview_result.validation_errors:
                    console.print("[red]Найдены ошибки валидации:[/]")
                    for error in preview_result.validation_errors:
                        console.print(f"  [red]• {error}[/]")
                    return

                if preview:
                    console.print("[yellow]Режим preview. Импорт не выполнен.[/]")
                    return

                # Подтверждение импорта
                if not click.confirm(f"Создать {preview_result.estimated_objects} объектов?"):
                    console.print("[yellow]Импорт отменен пользователем.[/]")
                    return

                # Выполняем импорт
                console.print("[blue]Выполняем импорт...[/]")

                with console.status("[bold green]Создание объектов..."):
                    result = await importer.import_from_excel(file_path, parent_id, sheet_name)

                # Показываем результаты
                if result.total_created > 0:
                    result_table = Table(title="Результат импорта")
                    result_table.add_column("Уровень", style="cyan")
                    result_table.add_column("Создано объектов", style="green")

                    for level, count in result.created_by_level.items():
                        result_table.add_row(str(level), str(count))

                    console.print(result_table)
                    console.print(f"[green]Всего создано объектов: {result.total_created}[/]")
                    console.print(f"[blue]Время выполнения: {result.duration_seconds:.2f} секунд[/]")

                # Показываем ошибки, если есть
                if result.errors:
                    console.print("[red]Ошибки при импорте:[/]")
                    for error in result.errors:
                        console.print(f"  [red]• {error}[/]")

                if result.total_created == 0:
                    console.print("[red]Ни одного объекта не было создано.[/]")
                else:
                    console.print("[green]Импорт завершен успешно![/]")

        except Exception as e:
            console.print(f"[red]Ошибка при импорте: {e}[/]")
            import traceback

            console.print(f"[red]{traceback.format_exc()}[/]")

    # Запускаем асинхронную функцию
    asyncio.run(run_import())
