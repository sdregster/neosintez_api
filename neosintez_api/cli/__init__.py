import click
from rich.console import Console

from .commands.class_ import class_
from .commands.import_excel import import_ as import_excel
from .commands.object import object


@click.group()
def cli():
    """
    Неосинтез CLI — удобная командная строка для работы с API Неосинтеза.
    """
    pass


cli.add_command(object)
cli.add_command(class_)
cli.add_command(import_excel)

# Импортируем команды (будут добавлены позже)
# from .commands import object, class_, import_excel
