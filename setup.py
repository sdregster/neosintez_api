from setuptools import setup, find_packages

setup(
    name="neosintez_api",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "aiohttp",  # Предполагаемая зависимость для HTTP-клиента
        "python-dotenv",  # Для работы с .env файлами
    ],
    description="API клиент для Neosintez",
    author="Your Name",
)
