"""
Скрипт актуализации (upsert) справочника из Excel, используя DynamicModelFactory.

Логика по строкам Excel:
- Ищем объект по (Класс, Имя объекта)
- Если найден — читаем модель и обновляем значения атрибутов/имени
- Если не найден — создаем объект под указанным родителем

Колонки по умолчанию:
- Класс: "Класс"
- Имя: "Имя объекта"

Прочие колонки считаются атрибутами соответствующего класса.

Если в файле нет колонки класса, можно передать общий класс аргументом default_class_name.
"""

import asyncio
import logging
from typing import Any, Dict

import pandas as pd

from neosintez_api.core.client import NeosintezClient
from neosintez_api.services import (
	ClassService,
	DynamicModelFactory,
	ObjectSearchService,
	ObjectService,
)


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("scripts.update_dictionary_from_excel")

async def upsert_from_excel(
	file_path: str,
	parent_id: str,
	sheet_name: str | None,
	class_col: str | None,
	default_class_name: str | None,
	name_col: str,
	*,
	dry_run: bool = False,
	attribute_renames: Dict[str, str | list[str]] | None = None,
	name_to_attribute: str | None = "Наименование",
	actuality_attribute_name: str | None = "Актуальность",
	actual_value: str = "Да",
	not_actual_value: str = "Нет",
	guid_attribute_name: str = "GUID",
):
	# Читаем Excel
	logger.info("Чтение Excel файла: %s", file_path)
	df = pd.read_excel(file_path, sheet_name=sheet_name)

	# Если не задано имя класса аргументом и нет колонки — это ошибка
	if (not default_class_name) and (class_col is None or class_col not in df.columns):
		raise ValueError(
			"В Excel отсутствует колонка класса и не передано default_class_name."
		)
	if name_col not in df.columns:
		raise ValueError(f"В Excel не найдена колонка имени: '{name_col}'")

	total_rows = len(df)
	logger.info("Всего строк для обработки: %s", total_rows)

	# Инициализация сервисов
	client = NeosintezClient()
	object_service = ObjectService(client)
	class_service = ClassService(client)
	search_service = ObjectSearchService(client)

	# Определяем алиас для имени класса: если колонки нет, используем служебный
	effective_class_col = class_col if (class_col and class_col in df.columns) else "__class__"
	factory = DynamicModelFactory(
		client=client,
		class_service=class_service,
		name_aliases=[name_col],
		class_name_aliases=[effective_class_col],
	)

	# ================== Предзагрузка существующих объектов под родителем ==================
	# 1) Собираем список классов из файла
	classes_in_file: set[str] = set()
	for _, row in df.iterrows():
		row_class = (default_class_name or str(row.get(class_col, "")).strip())
		if row_class:
			classes_in_file.add(row_class)

	# 2) Для каждого класса загружаем все объекты под parent_id и строим карту GUID->Id
	existing_by_guid_by_class: dict[str, dict[str, str]] = {}
	all_under_parent_by_class: dict[str, list] = {}
	guid_attr_id_by_class: dict[str, str] = {}

	for cls_name in classes_in_file:
		try:
			# Находим класс и его атрибуты
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
			guid_attr_id_str = str(guid_attr.Id)
			guid_attr_id_by_class[cls_name] = guid_attr_id_str

			# Загружаем все объекты этого класса под родителем
			objs = await (
				search_service
					.query()
					.with_class_name(cls_name)
					.with_parent_id(parent_id)
					.find_all()
			)
			all_under_parent_by_class[cls_name] = objs

			# Пытаемся извлечь GUID из результата поиска (если API вернул атрибуты)
			by_guid: dict[str, str] = {}
			needs_detail: list[str] = []
			for o in objs:
				guid_val = None
				if getattr(o, "Attributes", None) and guid_attr_id_str in o.Attributes:
					attr_data = o.Attributes[guid_attr_id_str]
					guid_val = (attr_data.get("Value") if isinstance(attr_data, dict) else attr_data)
				if guid_val:
					by_guid[str(guid_val).strip()] = str(o.Id)
				else:
					needs_detail.append(str(o.Id))

			# Дочитываем детали только для тех, где GUID не удалось извлечь
			if needs_detail:
				sem = asyncio.Semaphore(8)
				async def fetch_guid(obj_id: str):
					async with sem:
						data = await client.objects.get_by_id(obj_id)
						attrs = data.get("Attributes") or {}
						attr_data = attrs.get(guid_attr_id_str)
						val = (attr_data.get("Value") if isinstance(attr_data, dict) else attr_data) if attr_data else None
						if val:
							by_guid[str(val).strip()] = obj_id
				await asyncio.gather(*[fetch_guid(oid) for oid in needs_detail])

			existing_by_guid_by_class[cls_name] = by_guid
		except Exception as e:
			logger.warning("Не удалось предзагрузить объекты для класса '%s': %s", cls_name, e)

	created_count = 0
	updated_count = 0
	skipped_count = 0
	errors: list[str] = []

	# Для финальной актуализации по GUID: какие GUID присутствуют в файле по каждому классу
	present_guids_by_class: dict[str, set[str]] = {}
	model_class_cache: dict[str, type] = {}

	def get_field_name_for_alias(model_cls, alias_name: str) -> str | None:
		for fn, f in model_cls.model_fields.items():
			if (f.alias or fn) == alias_name:
				return fn
		return None

	try:
		# Идем по строкам
		for idx, row in df.iterrows():
			try:
				row_dict: Dict[str, Any] = {}
				for col in df.columns:
					value = row[col]
					# Пропускаем NaN/None
					if pd.isna(value):
						continue
					row_dict[str(col)] = value

				# Строим словарь для фабрики с учетом переименований атрибутов
				row_for_factory: Dict[str, Any] = {}
				for col_name, value in row_dict.items():
					# Не трогаем колонку имени и (если есть) колонку класса,
					# чтобы не ломать name_aliases/class_name_aliases
					if col_name == name_col or (class_col and col_name == class_col):
						target_cols = [col_name]
					else:
						renamed = attribute_renames.get(col_name, col_name) if attribute_renames else col_name
						target_cols = renamed if isinstance(renamed, list) else [renamed]
					
					for target_col in target_cols:
						# Исправление некорректных ссылок на ТОиР (убираем лишний "/" после toir_30/)
						val_to_use = value
						if target_col == "Ссылка на ТОиР" and isinstance(val_to_use, str):
							val_to_use = val_to_use.replace("toir_30/#", "toir_30#")
						
						row_for_factory[target_col] = val_to_use

				# Валидация обязательных полей
				# Определяем класс: приоритет у параметра default_class_name
				class_name = (default_class_name or str(row_dict.get(class_col, "")).strip())
				object_name = str(row_dict.get(name_col, "")).strip()
				if not class_name or not object_name:
					skipped_count += 1
					logger.warning("Строка %s пропущена: пустой класс или '%s'", idx + 2, name_col)
					continue

				# Если нужно, копируем имя объекта в атрибут (например, "Наименование")
				if name_to_attribute:
					row_for_factory[name_to_attribute] = object_name

				# Если класс задан аргументом, подставим его в данные для фабрики
				if default_class_name:
					row_for_factory[effective_class_col] = default_class_name
     
				# Устанавливаем актуальность = Да для присутствующих в выгрузке
				if actuality_attribute_name:
					row_for_factory[actuality_attribute_name] = actual_value

				# Строим динамическую модель из строки
				blueprint = await factory.create(row_for_factory)
				dynamic_model_cls = blueprint.model_class
				source_instance = blueprint.model_instance
				model_class_cache.setdefault(class_name, dynamic_model_cls)

				# Считываем GUID из строки (после переименований), если есть
				guid_value = row_for_factory.get(guid_attribute_name)
				guid_value_str = str(guid_value).strip() if guid_value is not None else ""
				if guid_value_str:
					present_guids_by_class.setdefault(class_name, set()).add(guid_value_str)


				# Поиск существующего объекта по предварительно загруженной карте (GUID)
				existing_id = None
				by_guid_map = existing_by_guid_by_class.get(class_name)
				if by_guid_map and guid_value_str:
					existing_id = by_guid_map.get(guid_value_str)

				if dry_run:
					action = "UPDATE" if existing_id else "CREATE"
					logger.info("[%s] %s -> класс '%s'", action, object_name, class_name)
					continue

				if existing_id:
					# Читаем текущую модель объекта
					current_model = await object_service.read(str(existing_id), dynamic_model_cls)

					# Переносим значения из excel-модели
					# Обновляем имя и все атрибуты, которые присутствуют в строке
					if hasattr(current_model, "name") and hasattr(source_instance, "name"):
						current_model.name = source_instance.name

					for field_name, field in dynamic_model_cls.model_fields.items():
						if field_name.startswith("_"):
							continue
						# Алиас соответствует имени атрибута в Неосинтез
						alias = field.alias or field_name
						if alias in row_for_factory and field_name in current_model.__class__.model_fields:
							try:
								setattr(current_model, field_name, source_instance.__getattribute__(field_name))
							except Exception:
								# Не валим весь цикл из-за некорректного значения
								logger.debug(
									"Не удалось установить поле '%s' на строке %s", field_name, idx + 2
								)

					# Выполняем интеллектуальное обновление
					await object_service.update(current_model)
					updated_count += 1
				else:
					# Создание нового объекта
					await object_service.create(source_instance, parent_id=parent_id)
					created_count += 1

			except Exception as e:  # noqa: BLE001
				msg = f"Ошибка на строке {idx + 2}: {e}"
				logger.error(msg, exc_info=True)
				errors.append(msg)

		# === Финальная актуализация: ставим 'Нет' объектам, отсутствующим в выгрузке (по GUID) ===
		if not dry_run and actuality_attribute_name and guid_attribute_name:
			for class_name, present_guids in present_guids_by_class.items():
				try:
					# Берем предзагруженный список объектов
					objs = all_under_parent_by_class.get(class_name, [])

					# Подготовим модель и имя поля GUID
					dynamic_model_cls = model_class_cache.get(class_name)
					if not dynamic_model_cls:
						# Создадим через фабрику по минимальным данным
						blueprint = await factory.create({effective_class_col: class_name, name_col: (next(iter(present_guids)) if present_guids else "tmp")})
						dynamic_model_cls = blueprint.model_class
						model_class_cache[class_name] = dynamic_model_cls

					guid_field_name = get_field_name_for_alias(dynamic_model_cls, guid_attribute_name)
					actuality_field_name = get_field_name_for_alias(dynamic_model_cls, actuality_attribute_name)
					if not guid_field_name or not actuality_field_name:
						logger.warning("GUID ('%s') или атрибут актуальности ('%s') не найдены в классе '%s'", guid_attribute_name, actuality_attribute_name, class_name)
						continue

					# Обновляем объекты, GUID которых нет в выгрузке
					for obj in objs:
						try:
							model = await object_service.read(str(obj.Id), dynamic_model_cls)
							obj_guid = getattr(model, guid_field_name, None)
							obj_guid_str = str(obj_guid).strip() if obj_guid is not None else ""
							if not obj_guid_str or obj_guid_str not in present_guids:
								setattr(model, actuality_field_name, not_actual_value)
								await object_service.update(model)
						except Exception as e:
							errors.append(f"Не удалось установить актуальность 'Нет' для ID '{obj.Id}': {e}")
				except Exception as e:
					errors.append(f"Ошибка при финальной актуализации по классу '{class_name}': {e}")

	finally:
		await client.close()

	logger.info(
		"Готово. Создано: %s, Обновлено: %s, Пропущено: %s, Ошибок: %s",
		created_count,
		updated_count,
		skipped_count,
		len(errors),
	)

	if errors:
		logger.warning("Список ошибок (%s):", len(errors))
		for err in errors:
			logger.warning(" - %s", err)

async def main():
	await upsert_from_excel(
		file_path="//irkoil/dfs/WorkDATA/1C_OBMEN/Неосинтез/ТОиР/unused_repair_objects.xlsx",
		parent_id="6305e9ba-0492-f011-91f2-005056b6948b",
		sheet_name="TDSheet",
		class_col=None,
		default_class_name="Объект невостребованной инфраструктуры",
		name_col="Наименование ОР",
		dry_run=False,
		attribute_renames={
			"УИД": "GUID",
			"Номер тех.позиции по проекту": "Номер по технологической схеме",
			"Подразделение": ["Подразделение владелец", "Подразделение владелец (ссылка)"],
			"Рег.номер ОПО": "Регистрационный номер ОПО",
			"Ответственный за тех.позицию": "Ответственный за техническую позицию",
		},
		name_to_attribute="Наименование",
		actuality_attribute_name="Актуальность",
		actual_value="Да",
		not_actual_value="Нет",
		guid_attribute_name="GUID",
	)

if __name__ == "__main__":
	asyncio.run(main())