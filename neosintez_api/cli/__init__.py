import click

from .commands.import_excel import import_ as import_excel


@click.group()
def cli():
    """
    Неосинтез CLI — удобная командная строка для работы с API Неосинтеза.
    """
    pass


cli.add_command(import_excel)
