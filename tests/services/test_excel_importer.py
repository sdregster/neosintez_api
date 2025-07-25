"""
Интеграционные тесты для `ExcelImporter`.

Проверяют полный цикл иерархического импорта из Excel-файла:
- Анализ структуры файла.
- Предварительный просмотр.
- Валидация данных.
- Поуровневое создание объектов.
- Проверка созданной иерархии.
- Очистка созданных данных.
"""

from pathlib import Path

import pandas as pd
import pytest
import pytest_asyncio

from neosintez_api.config import settings
from neosintez_api.core.client import NeosintezClient
from neosintez_api.services import ObjectService
from neosintez_api.services.excel_importer import ExcelImporter, ImportResult
from neosintez_api.services.factories import DynamicModelFactory


pytestmark = pytest.mark.asyncio


HIERARCHY_DATA = [
    # Уровень 1
    {
        "Уровень": 1,
        "Класс": "Объект капитальных вложений",
        "Имя объекта": "Тестовый проект-стройка",
        "ID стройки Адепт": 999,
        "МВЗ": "ABC-1",
    },
    # Уровень 2. Используем тот же класс "Объект капитальных вложений" для проверки иерархии
    {
        "Уровень": 2,
        "Класс": "Объект капитальных вложений",
        "Имя объекта": "Дочерний элемент-стройка",
        "ID стройки Адепт": 1000,
        "МВЗ": "ABC-2",
    },
    # Уровень 3.
    {
        "Уровень": 3,
        "Класс": "Объект капитальных вложений",
        "Имя объекта": "Внучатый элемент-стройка",
        "ID стройки Адепт": 1001,
        "МВЗ": "ABC-3",
    },
]

INVALID_CLASS_DATA = [
    {"Уровень": 1, "Класс": "НесуществующийКласс", "Имя объекта": "Объект с ошибкой класса"},
]

INVALID_ATTRIBUTE_DATA = [
    {
        "Уровень": 1,
        "Класс": "Объект капитальных вложений",
        "Имя объекта": "Объект с ошибкой атрибута",
        "НесуществующийАтрибут": "значение",
    },
]

REPEATED_INVALID_ATTRIBUTE_DATA = [
    {"Уровень": 1, "Класс": "Объект капитальных вложений", "Имя объекта": "Объект 1", "Атрибут1": "значение1"},
    {
        "Уровень": 1,
        "Класс": "Объект капитальных вложений",
        "Имя объекта": "Объект 2",
        "Атрибут1": "значение2",
        "Атрибут2": "val",
    },
    {"Уровень": 1, "Класс": "Объект капитальных вложений", "Имя объекта": "Объект 3", "Атрибут1": "значение3"},
]

BROKEN_HIERARCHY_DATA = [
    # Уровень 1
    {
        "Уровень": 1,
        "Класс": "Объект капитальных вложений",
        "Имя объекта": "Родитель 1-го уровня",
    },
    # Прыжок на уровень 3
    {
        "Уровень": 3,
        "Класс": "Объект капитальных вложений",
        "Имя объекта": "Потомок 3-го уровня (осиротевший)",
    },
]

MISSING_KEY_DATA = [
    # Строка с корректными данными
    {"Уровень": 1, "Класс": "Объект капитальных вложений", "Имя объекта": "Корректный объект"},
    # Строка с пропущенным классом
    {"Уровень": 2, "Класс": None, "Имя объекта": "Объект без класса"},
    # Строка, которая не должна быть обработана
    {"Уровень": 2, "Класс": "Объект капитальных вложений", "Имя объекта": "Этот объект не должен быть создан"},
]

RUNTIME_FAILURE_HIERARCHY_DATA = [
    # Уровень 1, этот объект вызовет ошибку при установке атрибутов
    {
        "Уровень": 1,
        "Класс": "Объект капитальных вложений",
        "Имя объекта": "Родитель с ошибкой во время выполнения",
        "ID стройки Адепт": "ЭТО-НЕ-ЧИСЛО",  # Атрибут ожидает число, вызовет ошибку 400
        "МВЗ": "ABC-FAIL-1",
    },
    # Уровень 2, дочерний элемент, который не должен быть создан
    {
        "Уровень": 2,
        "Класс": "Объект капитальных вложений",
        "Имя объекта": "Пропущенный дочерний элемент",
        "ID стройки Адепт": 2000,
        "МВЗ": "ABC-FAIL-2",
    },
]

FILE_ATTRIBUTE_DATA = [
    {
        "Уровень": 1,
        "Класс": "Акт КС-2",
        "Имя объекта": "Тестовый акт с файлом",
        "Файл": "some_file.xlsx",
        "Номер сметы": "СМ-01",
    }
]


@pytest.fixture(scope="module")
def test_excel_file_path(tmp_path_factory) -> Path:
    """Создает тестовый Excel-файл и возвращает путь к нему."""
    path = tmp_path_factory.mktemp("data") / "test_import.xlsx"
    df = pd.DataFrame(HIERARCHY_DATA)
    df.to_excel(path, index=False)
    return path


@pytest.fixture(scope="module")
def invalid_class_excel_file_path(tmp_path_factory) -> Path:
    """Создает тестовый Excel-файл с ошибкой в имени класса."""
    path = tmp_path_factory.mktemp("data") / "invalid_class.xlsx"
    df = pd.DataFrame(INVALID_CLASS_DATA)
    df.to_excel(path, index=False)
    return path


@pytest.fixture(scope="module")
def invalid_attribute_excel_file_path(tmp_path_factory) -> Path:
    """Создает тестовый Excel-файл с ошибкой в имени атрибута."""
    path = tmp_path_factory.mktemp("data") / "invalid_attribute.xlsx"
    df = pd.DataFrame(INVALID_ATTRIBUTE_DATA)
    df.to_excel(path, index=False)
    return path


@pytest.fixture(scope="module")
def repeated_invalid_attribute_excel_file_path(tmp_path_factory) -> Path:
    """Создает тестовый Excel-файл с повторяющимися ошибками в атрибутах."""
    path = tmp_path_factory.mktemp("data") / "repeated_invalid_attribute.xlsx"
    df = pd.DataFrame(REPEATED_INVALID_ATTRIBUTE_DATA)
    df.to_excel(path, index=False)
    return path


@pytest.fixture(scope="module")
def broken_hierarchy_excel_file_path(tmp_path_factory) -> Path:
    """Создает тестовый Excel-файл с нарушенной иерархией."""
    path = tmp_path_factory.mktemp("data") / "broken_hierarchy.xlsx"
    df = pd.DataFrame(BROKEN_HIERARCHY_DATA)
    df.to_excel(path, index=False)
    return path


@pytest.fixture(scope="module")
def missing_key_data_excel_file_path(tmp_path_factory) -> Path:
    """Создает тестовый Excel-файл со строкой, где отсутствуют ключевые данные."""
    path = tmp_path_factory.mktemp("data") / "missing_key_data.xlsx"
    df = pd.DataFrame(MISSING_KEY_DATA)
    df.to_excel(path, index=False)
    return path


@pytest.fixture(scope="module")
def runtime_failure_excel_file_path(tmp_path_factory) -> Path:
    """Создает тестовый Excel-файл, который вызовет ошибку во время выполнения."""
    path = tmp_path_factory.mktemp("data") / "runtime_failure.xlsx"
    df = pd.DataFrame(RUNTIME_FAILURE_HIERARCHY_DATA)
    df.to_excel(path, index=False)
    return path


@pytest.fixture(scope="module")
def file_attribute_excel_path(tmp_path_factory) -> Path:
    """Создает тестовый Excel-файл с атрибутом типа 'Файл'."""
    path = tmp_path_factory.mktemp("data") / "file_attribute.xlsx"
    df = pd.DataFrame(FILE_ATTRIBUTE_DATA)
    df.to_excel(path, index=False)
    return path


@pytest.fixture
def excel_importer(real_client: NeosintezClient) -> ExcelImporter:
    """Фикстура для создания экземпляра ExcelImporter."""
    return ExcelImporter(real_client)


@pytest_asyncio.fixture
async def managed_import(
    excel_importer: ExcelImporter,
    object_service: ObjectService,
    test_excel_file_path: Path,
) -> ImportResult:
    """
    Выполняет импорт и гарантирует удаление созданных объектов после теста.
    """
    created_ids = []

    result = await excel_importer.import_from_excel(
        excel_path=str(test_excel_file_path),
        parent_id=settings.test_folder_id,
    )
    assert not result.errors, f"Во время импорта возникли ошибки: {result.errors}"
    assert result.total_created == len(HIERARCHY_DATA), "Не все объекты были созданы"

    for obj in result.created_objects:
        created_ids.append(obj["id"])

    yield result

    # --- Очистка ---
    if not created_ids:
        return

    print(f"Очистка тестовых данных: удаление {len(created_ids)} объектов...")
    try:
        # TODO: Заменить на delete_many, когда он будет реализован
        for obj_id in created_ids:
            await object_service.delete(obj_id)
        print("Очистка успешно завершена.")
    except Exception as e:
        pytest.fail(f"Не удалось удалить тестовые объекты: {e}")


class TestExcelImporter:
    """Тестирование иерархического импорта из Excel."""

    async def test_analyze_structure(
        self,
        excel_importer: ExcelImporter,
        test_excel_file_path: Path,
    ):
        """Тестирует корректность анализа структуры Excel файла."""
        structure = await excel_importer.analyze_structure(str(test_excel_file_path))

        assert structure.level_column == 0
        assert structure.class_column == 1
        assert structure.name_column == 2
        assert structure.total_rows == len(HIERARCHY_DATA)
        assert structure.max_level == 3
        assert set(structure.classes_found) == {"Объект капитальных вложений"}
        # Проверяем, что все остальные колонки попали в атрибуты
        expected_attrs = {"ID стройки Адепт", "МВЗ"}
        assert set(structure.attribute_columns.values()) == expected_attrs

    async def test_preview_with_invalid_class(
        self,
        excel_importer: ExcelImporter,
        invalid_class_excel_file_path: Path,
    ):
        """
        Проверяет, что preview_import корректно находит ошибку несуществующего класса.
        """
        preview = await excel_importer.preview_import(
            excel_path=str(invalid_class_excel_file_path),
            parent_id=settings.test_folder_id,
        )

        assert len(preview.validation_errors) == 1
        assert "Класс 'НесуществующийКласс' не найден" in preview.validation_errors[0]

    async def test_preview_with_invalid_attribute_is_a_warning(
        self,
        excel_importer: ExcelImporter,
        invalid_attribute_excel_file_path: Path,
    ):
        """
        Проверяет, что preview_import корректно находит ошибку несуществующего
        атрибута и классифицирует ее как предупреждение.
        """
        preview = await excel_importer.preview_import(
            excel_path=str(invalid_attribute_excel_file_path),
            parent_id=settings.test_folder_id,
        )

        assert len(preview.validation_warnings) == 1
        assert (
            "Атрибут 'НесуществующийАтрибут' не найден в классе 'Объект капитальных вложений'"
            in preview.validation_warnings[0]
        )
        assert not preview.validation_errors

    async def test_import_with_invalid_class(
        self,
        excel_importer: ExcelImporter,
        invalid_class_excel_file_path: Path,
    ):
        """
        Проверяет, что импорт прерывается, если найден несуществующий класс.
        """
        result = await excel_importer.import_from_excel(
            excel_path=str(invalid_class_excel_file_path),
            parent_id=settings.test_folder_id,
        )

        assert result.total_created == 0
        assert len(result.errors) == 1
        assert "Класс 'НесуществующийКласс' не найден" in result.errors[0]

    async def test_import_succeeds_with_invalid_attribute_warning(
        self,
        excel_importer: ExcelImporter,
        invalid_attribute_excel_file_path: Path,
        object_service: ObjectService,
    ):
        """
        Проверяет, что импорт продолжается, если найден несуществующий атрибут,
        и в результат записывается предупреждение.
        """
        result = await excel_importer.import_from_excel(
            excel_path=str(invalid_attribute_excel_file_path),
            parent_id=settings.test_folder_id,
        )

        created_ids = [obj["id"] for obj in result.created_objects]
        try:
            assert result.total_created == 1
            assert not result.errors
            assert len(result.warnings) == 1
            assert (
                "Атрибут 'НесуществующийАтрибут' не найден в классе 'Объект капитальных вложений'" in result.warnings[0]
            )
        finally:
            if created_ids:
                for obj_id in created_ids:
                    await object_service.delete(obj_id)

    async def test_import_and_attributes_verification(
        self,
        managed_import: ImportResult,
        dynamic_model_factory: DynamicModelFactory,
        object_service: ObjectService,
    ):
        """
        Тестирует импорт и проверяет корректность установки атрибутов.
        """
        result = managed_import
        assert result.total_created == len(HIERARCHY_DATA)

        # Создадим словарь "имя объекта -> id" для удобства
        id_map = {obj["name"]: obj["id"] for obj in result.created_objects}

        # --- Проверка объекта "Объект капитальных вложений" ---
        stroyka_data = HIERARCHY_DATA[0]
        stroyka_id = id_map[stroyka_data["Имя объекта"]]
        StroykaModel = (
            await dynamic_model_factory.create({"Класс": "Объект капитальных вложений", "Имя объекта": "fake"})
        ).model_class
        stroyka_obj = await object_service.read(stroyka_id, StroykaModel)

        assert stroyka_obj.name == stroyka_data["Имя объекта"]
        assert stroyka_obj.id_stroyki_adept == stroyka_data["ID стройки Адепт"]
        assert stroyka_obj.mvz == stroyka_data["МВЗ"]

        # --- Проверка дочернего объекта ---
        child_data = HIERARCHY_DATA[1]
        child_id = id_map[child_data["Имя объекта"]]
        child_obj = await object_service.read(child_id, StroykaModel)  # Используем ту же модель

        assert child_obj.name == child_data["Имя объекта"]
        assert child_obj.id_stroyki_adept == child_data["ID стройки Адепт"]
        assert child_obj.mvz == child_data["МВЗ"]

    async def test_full_import_and_hierarchy(
        self,
        managed_import: ImportResult,
        object_service: ObjectService,
        real_client: NeosintezClient,
        dynamic_model_factory: DynamicModelFactory,
    ):
        """
        Тестирует полный цикл импорта и проверяет правильность выстроенной иерархии.
        """
        result = managed_import

        # 1. Проверяем результат импорта
        assert result.total_created == len(HIERARCHY_DATA)
        assert result.created_by_level == {1: 1, 2: 1, 3: 1}
        assert not result.errors

        # 2. Проверяем иерархию в Неосинтезе
        id_map = {obj["name"]: obj["id"] for obj in result.created_objects}

        # Проверяем родителей каждого объекта
        project_id = id_map["Тестовый проект-стройка"]
        child_id = id_map["Дочерний элемент-стройка"]
        grandchild_id = id_map["Внучатый элемент-стройка"]

        # Используем object_service.read, чтобы получить модели с заполненными _parent_id
        StroykaModel = (
            await dynamic_model_factory.create({"Класс": "Объект капитальных вложений", "Имя объекта": "fake"})
        ).model_class

        # Объекты 1-го уровня
        project_obj = await object_service.read(project_id, StroykaModel)
        assert project_obj._parent_id == settings.test_folder_id

        # Объекты 2-го уровня
        child_obj = await object_service.read(child_id, StroykaModel)
        assert child_obj._parent_id == project_id

        # Объекты 3-го уровня
        grandchild_obj = await object_service.read(grandchild_id, StroykaModel)
        assert grandchild_obj._parent_id == child_id

    async def test_import_groups_attribute_warnings(
        self,
        excel_importer: ExcelImporter,
        object_service: ObjectService,
        repeated_invalid_attribute_excel_file_path: Path,
    ):
        """
        Проверяет, что однотипные предупреждения об атрибутах группируются.
        """
        result = await excel_importer.import_from_excel(
            excel_path=str(repeated_invalid_attribute_excel_file_path),
            parent_id=settings.test_folder_id,
        )
        created_ids = [obj["id"] for obj in result.created_objects]
        try:
            assert result.total_created == len(REPEATED_INVALID_ATTRIBUTE_DATA)
            assert not result.errors
            assert len(result.warnings) == 2  # Должно быть 2 уникальных предупреждения
            # Проверяем, что оба типа предупреждений присутствуют
            warnings_text = "".join(result.warnings)
            assert "Атрибут 'Атрибут1' не найден в классе 'Объект капитальных вложений'" in warnings_text
            assert "Атрибут 'Атрибут2' не найден в классе 'Объект капитальных вложений'" in warnings_text
        finally:
            if created_ids:
                for obj_id in created_ids:
                    await object_service.delete(obj_id)

    async def test_import_with_broken_hierarchy_is_an_error(
        self,
        excel_importer: ExcelImporter,
        broken_hierarchy_excel_file_path: Path,
    ):
        """
        Тестирует, что импорт файла с нарушенной иерархией прерывается
        и возвращает ошибку.
        """
        result = await excel_importer.import_from_excel(
            excel_path=str(broken_hierarchy_excel_file_path),
            parent_id=settings.test_folder_id,
        )

        assert result.total_created == 0
        assert len(result.errors) == 1
        assert "Нарушена иерархия" in result.errors[0]
        assert "уровня 3 не может следовать за уровнем 1" in result.errors[0]

    async def test_import_with_missing_key_data_is_an_error(
        self,
        excel_importer: ExcelImporter,
        object_service: ObjectService,
        missing_key_data_excel_file_path: Path,
    ):
        """
        Тестирует, что импорт прерывается, если в строке отсутствуют
        ключевые данные (класс или имя).
        """
        result = await excel_importer.import_from_excel(
            excel_path=str(missing_key_data_excel_file_path),
            parent_id=settings.test_folder_id,
        )

        try:
            # Объекты, созданные до ошибки, должны остаться.
            # Новая логика - ошибка прерывает ВЕСЬ импорт.
            assert result.total_created == 0
            assert len(result.errors) == 1
            assert "Отсутствуют обязательные данные" in result.errors[0]
        finally:
            # На случай, если логика отработает неверно и что-то создастся
            if result.created_objects:
                for obj in result.created_objects:
                    await object_service.delete(obj["id"])

    async def test_import_with_runtime_parent_failure_is_clean(
        self,
        excel_importer: ExcelImporter,
        runtime_failure_excel_file_path: Path,
        object_service: ObjectService,
    ):
        """
        Проверяет, что при сбое создания родительского объекта во время выполнения,
        дочерние объекты пропускаются без лишних сообщений об ошибках.
        """
        result = await excel_importer.import_from_excel(
            excel_path=str(runtime_failure_excel_file_path),
            parent_id=settings.test_folder_id,
        )
        created_ids = [obj["id"] for obj in result.created_objects]

        try:
            # 1. Ни один объект не должен быть создан, так как родитель упал.
            assert result.total_created == 0, "Объекты не должны были создаться"
            assert not created_ids, "Список созданных объектов должен быть пуст"

            # 2. Должна быть только ОДНА ошибка от API.
            # Никаких "Не удалось найти реальный ID..."
            assert len(result.errors) == 1, "Должна быть только одна ошибка"

            # 3. Проверяем содержание ошибки
            error_text = result.errors[0]
            assert "Ошибка подготовки данных" in error_text, "Должна быть ошибка подготовки данных"
            # Проверяем, что это ошибка валидации Pydantic
            assert "unable to parse string as a number" in error_text, "Должна быть ошибка парсинга числа Pydantic"
            assert "Не найден родительский объект" not in error_text

        finally:
            # На случай, если что-то все-таки создалось вопреки логике
            if created_ids:
                for obj_id in created_ids:
                    await object_service.delete(obj_id)

    async def test_import_with_file_attribute_skips_it_with_warning(
        self,
        excel_importer: ExcelImporter,
        file_attribute_excel_path: Path,
        object_service: ObjectService,
    ):
        """
        Проверяет, что при импорте атрибут типа 'Файл' пропускается,
        но для пользователя выводится предупреждение.
        """
        result = await excel_importer.import_from_excel(
            excel_path=str(file_attribute_excel_path),
            parent_id=settings.test_folder_id,
        )

        created_ids = [obj["id"] for obj in result.created_objects]
        try:
            assert result.total_created == 1, "Должен быть создан один объект"
            assert not result.errors, "Не должно быть ошибок при импорте"

            assert len(result.warnings) == 1, "Должно быть одно предупреждение о пропуске файлового атрибута"
            warning_text = result.warnings[0]
            assert "является файловым и будет пропущен" in warning_text
            assert "Атрибут 'Файл'" in warning_text

        finally:
            if created_ids:
                for obj_id in created_ids:
                    await object_service.delete(obj_id)
