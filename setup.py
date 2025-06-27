from setuptools import find_packages, setup


setup(
    name="neosintez_api",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "aiohttp",  # Предполагаемая зависимость для HTTP-клиента
        "python-dotenv",  # Для работы с .env файлами
        "click>=8.1.0",  # Для CLI
        "rich>=13.0.0",  # Для красивого вывода
    ],
    entry_points={
        "console_scripts": [
            "neosintez=neosintez_api.__main__:cli",
        ],
    },
    description="API клиент для Neosintez",
    author="Your Name",
)
