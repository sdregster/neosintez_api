import asyncio
import logging
from typing import Any, Dict, List
import requests
import json
from datetime import datetime
import pandas as pd  # Для чтения Excel

from neosintez_api.core.client import NeosintezClient
from neosintez_api.services import (
    ClassService,
    DynamicModelFactory,
    ObjectSearchService,
    ObjectService,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("scripts.update_dictionary_from_json")


def validate_date(value: Any) -> datetime | None:
    """Валидация даты и преобразование в datetime"""
    if value is None:
        return None
    
    if isinstance(value, datetime):
        return value
        
    val_str = str(value).strip()
    if not val_str or val_str in ["-", "null", "None", "nan", "NaT"]:
        return None
        
    # Удаляем время если оно есть (для парсинга строки)
    if " " in val_str:
        val_str = val_str.split(" ")[0]
    if "T" in val_str:
        val_str = val_str.split("T")[0]
        
    # Если это просто год (4 цифры)
    if val_str.isdigit() and len(val_str) == 4:
        return datetime(int(val_str), 1, 1)
        
    formats = [
        "%d.%m.%Y", 
        "%Y-%m-%d", 
        "%d-%m-%Y",
        "%Y.%m.%d",
        "%d/%m/%Y",
        "%Y/%m/%d"
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(val_str, fmt)
        except ValueError:
            continue
            
    return None



def clean_value(value: Any, is_numeric: bool = False) -> Any:
    """Очистка значения с учетом типа поля."""
    if value is None or value == "-" or value == "null" or value == "":
        return None
    
    if isinstance(value, (int, float)):
        return value
    
    if not isinstance(value, str):
        value = str(value)
    
    value = value.replace('\n', '').replace('\r', '')
    value = ' '.join(value.split()).strip()
    
    # ГЛОБАЛЬНО заменяем запятые на точки для всех значений
    value = value.replace(',', '.')
    
    if is_numeric and value:
        try:
            if '.' in value or 'e' in value.lower():
                return float(value)
            return int(value)
        except ValueError:
            return None
    
    return value



def transform_row_data_to_dict(row_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Преобразует новый формат row_data в плоский словарь."""
    result = {}
    for item in row_data:
        attr_name = item.get("attribute_name", "")
        attr_value = item.get("attribute_value")
        result[attr_name] = attr_value
    return result


async def upsert_from_json(
    json_data: List[Dict[str, Any]],
    parent_id: str,
    class_col: str | None,
    default_class_name: str | None,
    name_col: str,
    folder_class_name: str = "Папка",
    *,
    dry_run: bool = False,
    attribute_renames: Dict[str, str] | None = None,
    name_to_attribute: str | None = "Наименование",
    actuality_attribute_name: str | None = "Актуальность",
    actual_value: str = "Да",
    not_actual_value: str = "Нет",
    guid_attribute_name: str = "GUID",
    equipment_type_mapping: Dict[str, str] = None,
    update_date_attribute_name: str = "Дата обновления из Серафимы",
):
    # Преобразуем новый формат данных в старый плоский формат
    transformed_data = []
    for row in json_data:
        if row.get("relevance") != "Да":
            continue
        flat_row = transform_row_data_to_dict(row.get("row_data", []))
        if flat_row.get("Вид оборудования") is None:
            flat_row["Вид оборудования"] = row.get("equipment_type")
        flat_row["row_id"] = row.get("row_id")  # GUID из row_id
        flat_row["Тип файла"] = row.get("file_type")
        transformed_data.append(flat_row)
        
    if not transformed_data:
        raise ValueError("Нет данных с relevance='Да' для обработки")
    
    if not default_class_name and (class_col is None or not any(class_col in item for item in transformed_data)):
        raise ValueError("В JSON отсутствует ключ класса и не передано default_class_name.")
    
    # Проверка наличия ключа имени или его альтернативы
    has_valid_name = False
    for item in transformed_data:
        if name_col in item:
            has_valid_name = True
            break
        if item.get("Тип файла") == "reg" and "Наименование трубопровода (объекта)" in item:
            has_valid_name = True
            break
            
    if not has_valid_name:
        available_keys = set().union(*(set(item.keys()) for item in transformed_data[:5]))
        logger.warning(
            "Ключ '%s' (или альтернатива для reg) не найден ни в одной записи. Доступные ключи: %s",
            name_col, available_keys
        )
        raise ValueError(f"В преобразованных данных не найден ключ имени: '{name_col}' или 'Наименование трубопровода (объекта)'")

    
    total_rows = len(transformed_data)
    logger.info("Всего элементов для обработки: %s", total_rows)

    client = NeosintezClient()
    object_service = ObjectService(client)
    class_service = ClassService(client)
    search_service = ObjectSearchService(client)

    effective_class_col = class_col if class_col else "__class__"
    factory = DynamicModelFactory(
        client=client,
        class_service=class_service,
        name_aliases=[name_col],
        class_name_aliases=[effective_class_col],
    )

    # Функция для проверки валидности элемента (те же проверки, что и в основном цикле)
    def is_valid_item(item: Dict[str, Any]) -> bool:
        """Проверяет, будет ли элемент обработан (не пропущен)."""
        # Проверка на "Ссылка на карточку в 1С:ТОИР 3"
        if item.get("Ссылка на карточку в 1С:ТОИР 3") and item.get("Ссылка на карточку в 1С:ТОИР 3") != "Объект ремонта в ТОиР не вносился":
            return False
        
        # Проверка на пустой класс или имя
        row_class = default_class_name or str(item.get(class_col, "")).strip() if class_col else default_class_name
        # Custom logic for name extraction
        if item.get("Тип файла") == "reg":
            object_name = str(item.get("Наименование трубопровода (объекта)", "")).strip()
        else:
            object_name = str(item.get(name_col, "")).strip()
        if not row_class or not object_name:
            return False
        
        
        
        return True

    # Извлекаем уникальные equipment_type только из валидных элементов
    unique_equipment_types = set()
    for item in transformed_data:
        # Проверяем валидность перед добавлением типа оборудования
        if not is_valid_item(item):
            continue
            
        if "Вид оборудования" in item:
            cleaned_value = clean_value(str(item["Вид оборудования"]))
            if equipment_type_mapping:
                if cleaned_value == str(None) or cleaned_value == "":
                    mapped_value = "Прочее"
                    item["Вид оборудования"] = mapped_value
                else:
                    mapped_value = equipment_type_mapping.get(cleaned_value, cleaned_value)
                    item["Вид оборудования"] = mapped_value
                unique_equipment_types.add(mapped_value)
            else:
                unique_equipment_types.add(cleaned_value)
        else:
            item["Вид оборудования"] = "Прочее"
            unique_equipment_types.add("Прочее")
        
    # Создаём папки только для типов оборудования, у которых есть валидные данные
    equipment_type_to_folder_id: Dict[str, str] = {}
    for eq_type in unique_equipment_types:
        folder_name = f"{eq_type}"
        existing_folders = await search_service.query().with_class_name(folder_class_name).with_parent_id(parent_id).with_name(folder_name).find_all()
        if existing_folders:
            folder_id = str(existing_folders[0].Id)
            logger.info(f"Папка для '{eq_type}' уже существует: ID {folder_id}")
        else:
            folder_blueprint = await factory.create({
                effective_class_col: folder_class_name,
                name_col: folder_name,
            })
            folder_instance = folder_blueprint.model_instance
            created_folder = await object_service.create(folder_instance, parent_id=parent_id)
            folder_id = str(created_folder._id)
            logger.info(f"Создана папка для '{eq_type}': ID {folder_id}")
        equipment_type_to_folder_id[eq_type] = folder_id

    # Предзагрузка существующих объектов
    classes_in_file: set[str] = set()
    for item in transformed_data:
        row_class = default_class_name or str(item.get(class_col, "")).strip()
        if row_class:
            classes_in_file.add(row_class)

    existing_by_guid_by_class: dict[str, dict[str, str]] = {}
    all_under_parent_by_class: dict[str, list] = {}
    guid_attr_id_by_class: dict[str, str] = {}

    for cls_name in classes_in_file:
        try:
            classes_found = await class_service.find_by_name(cls_name)
            cls_exact = next((c for c in classes_found if c.Name.lower() == cls_name.lower()), None)
            if not cls_exact:
                logger.warning("Класс '%s' не найден для предзагрузки", cls_name)
                continue
            cls_id = str(cls_exact.Id)
            attrs_meta = await class_service.get_attributes(cls_id)
            guid_attr = next((a for a in attrs_meta if a.Name == guid_attribute_name), None)
            if not guid_attr:
                logger.warning("Атрибут GUID '%s' не найден в классе '%s'", guid_attribute_name, cls_name)
                continue
            guid_attr_id_by_class[cls_name] = str(guid_attr.Id)

            objs = await search_service.query().with_class_name(cls_name).with_parent_id(parent_id).find_all()
            all_under_parent_by_class[cls_name] = objs

            by_guid: dict[str, str] = {}
            needs_detail: list[str] = []
            for o in objs:
                guid_val = o.Attributes.get(guid_attr_id_by_class[cls_name], {}).get("Value") if o.Attributes else None
                if guid_val:
                    by_guid[str(guid_val).strip()] = str(o.Id)
                else:
                    needs_detail.append(str(o.Id))

            if needs_detail:
                sem = asyncio.Semaphore(8)
                async def fetch_guid(obj_id: str):
                    async with sem:
                        data = await client.objects.get_by_id(obj_id)
                        attr_data = data.get("Attributes", {}).get(guid_attr_id_by_class[cls_name])
                        val = attr_data.get("Value") if attr_data else None
                        if val:
                            by_guid[str(val).strip()] = obj_id
                await asyncio.gather(*[fetch_guid(oid) for oid in needs_detail])

            existing_by_guid_by_class[cls_name] = by_guid
        except Exception as e:
            logger.warning("Не удалось предзагрузить объекты для класса '%s': %s", cls_name, e)
    a = []

    created_count = 0
    updated_count = 0
    skipped_count = 0
    toir_lin_not_null_count = 0
    errors: list[str] = []
    present_guids_by_class: dict[str, set[str]] = {}
    model_class_cache: dict[str, type] = {}
    for idx, row_dict in enumerate(transformed_data, start=1):
        # try:
            if row_dict.get("Ссылка на карточку в 1С:ТОИР 3") and row_dict.get("Ссылка на карточку в 1С:ТОИР 3") != "Объект ремонта в ТОиР не вносился":
                toir_lin_not_null_count += 1
                continue
            row_for_factory: Dict[str, Any] = row_dict.copy()

            if class_col and class_col in row_for_factory:
                class_name = str(row_for_factory[class_col]).strip()
            else:
                class_name = default_class_name
                row_for_factory[effective_class_col] = class_name

            if row_dict.get("Тип файла") == "reg":
                object_name = str(row_dict.get("Наименование трубопровода (объекта)", "")).strip()
            else:
                object_name = str(row_dict.get(name_col, "")).strip()
            equipment_type_value = row_dict.get("Вид оборудования", None)
            if equipment_type_value:
                cleaned_eq_type = clean_value(str(equipment_type_value))
                mapped_eq_type = equipment_type_mapping.get(cleaned_eq_type, cleaned_eq_type) if equipment_type_mapping else cleaned_eq_type
                target_folder_id = equipment_type_to_folder_id.get(mapped_eq_type, parent_id)
            else:
                target_folder_id = parent_id

            if not class_name or not object_name:
                skipped_count += 1
                logger.warning("Элемент %s пропущен: пустой класс или '%s'", idx, name_col)
                continue

            for col_name, value in list(row_for_factory.items()):
                target_col = attribute_renames.get(col_name, col_name) if attribute_renames else col_name

                # Валидация дат
                if target_col in ["Дата изготовления", "Дата вывода из эксплуатации", "Дата высвобождения", "Дата запуска в работу"]:
                    value = validate_date(value)

                if col_name == name_col or (class_col and col_name == class_col):
                    continue
                if col_name == "Вид оборудования" and equipment_type_mapping:
                    cleaned_value = clean_value(str(value))
                    value = equipment_type_mapping.get(cleaned_value, cleaned_value)
                
                row_for_factory[target_col] = clean_value(value)
                if col_name != target_col:
                    del row_for_factory[col_name]

            if name_to_attribute:
                row_for_factory[name_to_attribute] = object_name

            if actuality_attribute_name:
                row_for_factory[actuality_attribute_name] = actual_value

            if update_date_attribute_name:
                row_for_factory[update_date_attribute_name] = datetime.now()
                
            if row_for_factory["Вид невостребованного оборудования"] == "Скважина":
                continue

            row_for_factory["GUID"] = str(row_for_factory["GUID"])
            row_for_factory[guid_attribute_name] = str(row_for_factory["№ пп"])
            blueprint = await factory.create(row_for_factory)
            dynamic_model_cls = blueprint.model_class
            source_instance = blueprint.model_instance
            source_instance.naimenovanie = source_instance.name
            model_class_cache.setdefault(class_name, dynamic_model_cls)

            guid_value = row_for_factory.get(guid_attribute_name)
            guid_value_str = str(guid_value).strip() if guid_value else ""
            if guid_value_str:
                present_guids_by_class.setdefault(class_name, set()).add(guid_value_str)

            existing_id = existing_by_guid_by_class.get(class_name, {}).get(guid_value_str)

            if dry_run:
                action = "UPDATE" if existing_id else "CREATE"
                logger.info("[%s] %s -> класс '%s', папка: %s", action, object_name, class_name, target_folder_id)
                continue

            if existing_id:
                current_model = await object_service.read(str(existing_id), dynamic_model_cls)
                if hasattr(current_model, "name"):
                    current_model.name = source_instance.name
                for field_name in dynamic_model_cls.model_fields:
                    if field_name.startswith("_"):
                        continue
                    alias = dynamic_model_cls.model_fields[field_name].alias or field_name
                    if alias in row_for_factory:
                        try:
                            setattr(current_model, field_name, getattr(source_instance, field_name))
                        except Exception:
                            logger.debug("Не удалось установить поле '%s' на элементе %s", field_name, idx)
                await object_service.update(current_model)
                updated_count += 1
            else:
                await object_service.create(source_instance, parent_id=target_folder_id)
                created_count += 1

        # except Exception as e:
        #     msg = f"Ошибка на элементе {idx}: {e}"
        #     logger.error(msg, exc_info=True)
        #     errors.append(msg)

    # Финальная актуализация
    if not dry_run and actuality_attribute_name and guid_attribute_name:
        for class_name, present_guids in present_guids_by_class.items():
            try:
                objs = all_under_parent_by_class.get(class_name, [])
                dynamic_model_cls = model_class_cache.get(class_name)
                if dynamic_model_cls:
                    guid_field_name = next((fn for fn, f in dynamic_model_cls.model_fields.items() if (f.alias or fn) == guid_attribute_name), None)
                    actuality_field_name = next((fn for fn, f in dynamic_model_cls.model_fields.items() if (f.alias or fn) == actuality_attribute_name), None)
                    if guid_field_name and actuality_field_name:
                        for obj in objs:
                            model = await object_service.read(str(obj.Id), dynamic_model_cls)
                            obj_guid = getattr(model, guid_field_name, None)
                            if str(obj_guid).strip() not in present_guids:
                                setattr(model, actuality_field_name, not_actual_value)
                                await object_service.update(model)
            except Exception as e:
                errors.append(f"Ошибка при финальной актуализации по классу '{class_name}': {e}")

    await client.close()
    logger.info("Готово. Создано: %s, Обновлено: %s, Пропущено: %s, Ошибок: %s", created_count, updated_count, skipped_count, len(errors))
    if errors:
        for err in errors:
            logger.warning(" - %s", err)


async def main():
    excel_file = r"C:\python\excel\Справочник видов.xlsx"
    try:
        df = pd.read_excel(excel_file)
        equipment_type_mapping = dict(zip(df.iloc[:, 0], df.iloc[:, 1]))
        logger.info("Загружено %s записей для маппинга Вид оборудования.", len(equipment_type_mapping))
    except Exception as e:
        logger.error("Ошибка при чтении Excel файла: %s", e)
        return

    api_url = "https://dl-data.dl.irkutskoil.ru/data/serafima/equipment"
    date_param = "2026-02"
    # try:
    payload = {"date": date_param}
    headers = {"content-type": "application/json"}
    logger.info("Отправка запроса к API: %s", api_url)
    response = requests.post(api_url, data=json.dumps(payload), headers=headers)
    if response.status_code == 200:
        response_data = response.json()
        if "data" in response_data and response_data.get("status") != "Ошибка ...":
            json_data = response_data["data"]
            logger.info("Получено %s строк данных из API.", len(json_data))
            a =[]
            for i in json_data:
                if i["file_type"] not in a:
                    a.append({i["file_type"]:i})
            await upsert_from_json(
                json_data=json_data,
                parent_id="6fd6d497-ee0a-f111-920a-005056b6948b",
                class_col=None,
                default_class_name="Объект невостребованной инфраструктуры",
                name_col="Наименование",
                folder_class_name="Папка",
                dry_run=False,
                attribute_renames={
                    "row_id": "GUID",
                    "Наименование": "Наименование",
                    "Габаритные размеры": "Габаритные размеры",
                    "Месторождение": "Месторождение (текст)",
                    "Наименование производственного объекта": "Наименование объекта",
                    "Цех": "Цех",
                    "Вид оборудования": "Вид невостребованного оборудования",
                    "Обвязка аппарата (к какому аппарату относится)": "Обвязка аппарата",
                    "Номер позиции": "Номер позиции",
                    "Рабочая среда": "Рабочая среда",
                    "Расчетное давление, МПа": "Расчетное давление",
                    "Расчетная температура, оС": "Температура расчетная",
                    "Объем аппарата, м3": "Объем",
                    "Материальное исполнение": "Материальное исполнение",
                    "Давление на входе, МПа": "Давление на входе",
                    "Давление на выходе, МПа": "Давление на выходе, МПа",
                    "Температура входа, оС": "Температура на входе",
                    "Температура выхода, оС": "Температура на выходе",
                    "Адсорбент": "Адсорбент",
                    "Дата изготовления": "Дата изготовления",
                    "Срок службы": "Срок службы",
                    "№ п/п": "№ пп",
                    "№ П/П": "№ пп",
                    "Оборудование КИП": "Оборудование КИП",
                    "Трубопровод. Толщина стенки, мм": "Толщина стенки трубопровода",
                    "Трубопровод. Длина, м": "Длина трубопровода",
                    "Фасонная деталь. Вид": "Вид фасонной детали",
                    "Фасонная деталь. Размерность": "Размерность фасонной детали",
                    "ЗРА. Вид": "Вид ЗРА",
                    "ЗРА. Dy": "ЗРА. Dy",
                    "ЗРА. Py": "ЗРА. Py",
                    "ЗРА. Привод": "Привод ЗРА",
                    "Насос. Э/дв. Мощность": "Мощность электродвигателя насоса",
                    "Насос. Э/дв. Частота вращения": "Частота вращения электродвигателя насоса",
                    "Насос. Марка": "Марка насоса",
                    "Насос. Напор, м": "Напор насоса, м",
                    "Насос. Тип насоса": "Тип насоса",
                    "Ссылка на карточку в 1С:ТОИР 3": "Ссылка на ТОиР",
                    "Примечание": "Примечание",
                    "Насос. Э/дв. Марка": "Марка электродвигателя насоса",
                    "Трубопровод. Dy, мм": "Трубопровод. Dy",
                    "Производительность по продукту, м3/сут": "Производительность по продукту, м3/сут",
                    "КП/Установка": "КП/Установка",
                    "Диспетчерское наименование ЭУ (ТП/РП/ПР/ПС и др.)": "Диспетчерское наименование",
                    "Зав.№": "Заводской номер",
                    "Мощность тр-ра (тр-ров), кВА (при наличии)": "Мощность трансформаторов",
                    "Количество трансформаторов, шт.(при наличии)": "Количество трансформаторов",
                    "Дата вывода из эксплуатации": "Дата вывода из эксплуатации",
                    "Прибор учета": "Прибор учета",
                    "D, мм": "Диаметр",
                    "Нст, мм": "Высота",
                    "Юридическое лицо": "Юридическое лицо",
                    "Подразделение УЭТ": "Подразделение владелец",
                    "Лицензионный участок": "Лицензионный участок",
                    "Принадлежность к объекту (ДНС, УКПГ, КНС, ЦППН)": "Принадлежность к объекту",
                    "Назначение трубопровода": "Назначение",
                    "Наименование трубопровода (объекта)": "Наименование",
                    "Дата высвобождения": "Дата высвобождения",
                    "Планы по вовлечению": "Планы по вовлечению",
                    'Месторождение(всплывающий список с листа "Справочник")': "Месторождение (текст)",
                    "Дата запуска в работу (ДД.ММ.ГГГГ)ФАКТ": "Дата запуска в работу",
                    "Возраст, лет (формула)": "Срок службы"
                    },
                name_to_attribute="Наименование",
                actuality_attribute_name="Актуальность",
                actual_value="Да",
                not_actual_value="Нет",
                guid_attribute_name="№ пп",
                equipment_type_mapping=equipment_type_mapping,
            )
        else:
            logger.error("API вернул ошибку: %s", response_data.get("status", "Неизвестная ошибка"))
    else:
        logger.error("Ошибка API: Статус код %s, Текст: %s", response.status_code, response.text)
    # except Exception as e:
        # logger.error("Ошибка при запросе к API: %s", e)


if __name__ == "__main__":
    asyncio.run(main())
