import asyncio

import click
from rich.console import Console

from neosintez_api.config import NeosintezConfig
from neosintez_api.core.client import NeosintezClient


@click.group(name="class")
def class_():
    """
    Работа с классами Неосинтеза (информация, атрибуты)
    """
    pass


@class_.command()
@click.argument("class_id")
def info(class_id):
    """
    Получить информацию о классе по его идентификатору.
    """
    console = Console()
    console.print(f"[bold cyan]Информация о классе:[/] {class_id}")
    console.print("[yellow]Демо-режим. Реализация будет позже.")


@class_.command()
@click.argument("class_id")
def attributes(class_id):
    """
    Получить атрибуты класса по его идентификатору.
    """
    console = Console()
    console.print(f"[bold cyan]Атрибуты класса:[/] {class_id}")
    console.print("[yellow]Демо-режим. Реализация будет позже.")
    # TODO: Реализовать получение атрибутов класса


@class_.command("get")
@click.argument("class_id")
def get_class(class_id):
    """Получить информацию о классе по ID."""
    console = Console()
    settings = NeosintezConfig()

    async def _get():
        try:
            async with NeosintezClient(settings) as client:
                # Для работы с классами используется `client.classes`
                class_info = await client.classes.get_by_id(class_id)
                console.print(class_info)
        except Exception as e:
            console.print(f"[bold red]Ошибка:[/] {e}")

    asyncio.run(_get())
