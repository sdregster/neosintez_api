import click
from rich.console import Console


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
