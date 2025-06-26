import click
from rich.console import Console
import asyncio
from neosintez_api.services import ObjectService
from neosintez_api.core import NeosintezClient
from neosintez_api.config import NeosintezSettings
from neosintez_api.models import EquipmentModel
from neosintez_api.exceptions import ApiError

@click.group()
def object():
    """
    Работа с объектами Неосинтеза (get, create, update, delete)
    """
    pass

@object.command()
@click.argument('object_id')
def get(object_id):
    """
    Получить объект по его идентификатору.
    """
    console = Console()
    async def _get():
        try:
            settings = NeosintezSettings()
            async with NeosintezClient(settings) as client:
                service = ObjectService(client)
                model = await service.read(object_id, EquipmentModel)
                console.print("[bold green]Объект получен:[/]")
                console.print(model)
        except ApiError as e:
            console.print(f"[bold red]Ошибка API:[/] {e}")
        except Exception as e:
            console.print(f"[bold red]Неизвестная ошибка:[/] {e}")
    asyncio.run(_get())

@object.command()
@click.option('--class', 'class_name', required=True, help='Класс объекта')
@click.option('--name', required=True, help='Имя объекта')
@click.option('--parent', 'parent_id', required=False, help='ID родителя')
@click.option('--dry-run', is_flag=True, help='Показать данные, не создавать объект')
def create(class_name, name, parent_id, dry_run):
    """
    Создать новый объект.
    """
    console = Console()
    async def _create():
        try:
            # Пример: EquipmentModel, в реальности — динамически по class_name
            model = EquipmentModel(name=name, model="Модель", serial_number="123", installation_date="2024-01-01", is_active=True)
            if dry_run:
                console.print("[yellow]Режим dry-run. Объект не будет создан.[/]")
                console.print(model)
                return
            settings = NeosintezSettings()
            async with NeosintezClient(settings) as client:
                service = ObjectService(client)
                object_id = await service.create(model, parent_id)
                console.print(f"[bold green]Объект создан. ID:[/] {object_id}")
        except ApiError as e:
            console.print(f"[bold red]Ошибка API:[/] {e}")
        except Exception as e:
            console.print(f"[bold red]Неизвестная ошибка:[/] {e}")
    asyncio.run(_create())

@object.command()
@click.argument('object_id')
@click.option('--attr', multiple=True, help='Атрибуты для обновления (ключ=значение)')
@click.option('--dry-run', is_flag=True, help='Показать изменения, не обновлять')
def update(object_id, attr, dry_run):
    """
    Обновить атрибуты объекта.
    """
    console = Console()
    async def _update():
        try:
            # Пример: обновление только поля model
            attrs = dict(a.split('=', 1) for a in attr)
            settings = NeosintezSettings()
            async with NeosintezClient(settings) as client:
                service = ObjectService(client)
                # Получаем текущий объект
                current = await service.read(object_id, EquipmentModel)
                # Обновляем поля
                for k, v in attrs.items():
                    if hasattr(current, k):
                        setattr(current, k, v)
                if dry_run:
                    console.print("[yellow]Режим dry-run. Изменения не будут применены.[/]")
                    console.print(current)
                    return
                result = await service.update_attrs(object_id, current)
                if result:
                    console.print(f"[bold green]Объект обновлён:[/] {object_id}")
                else:
                    console.print(f"[bold red]Ошибка при обновлении объекта:[/] {object_id}")
        except ApiError as e:
            console.print(f"[bold red]Ошибка API:[/] {e}")
        except Exception as e:
            console.print(f"[bold red]Неизвестная ошибка:[/] {e}")
    asyncio.run(_update())

@object.command()
@click.argument('object_id')
@click.option('--dry-run', is_flag=True, help='Показать предупреждение, не удалять')
def delete(object_id, dry_run):
    """
    Удалить объект по его идентификатору.
    """
    console = Console()
    async def _delete():
        try:
            if dry_run:
                console.print(f"[yellow]Режим dry-run. Объект не будет удалён:[/] {object_id}")
                return
            settings = NeosintezSettings()
            async with NeosintezClient(settings) as client:
                # В ObjectService нет delete, используем client напрямую
                await client.delete(f"objects/{object_id}")
                console.print(f"[bold red]Объект удалён:[/] {object_id}")
        except ApiError as e:
            console.print(f"[bold red]Ошибка API:[/] {e}")
        except Exception as e:
            console.print(f"[bold red]Неизвестная ошибка:[/] {e}")
    asyncio.run(_delete()) 