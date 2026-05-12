import asyncio
import logging
import os
import io
import traceback
import requests
import json
from typing import Optional
from pydantic import Field, BaseModel, ConfigDict, ValidationError, field_validator

from neosintez_api.config import NeosintezConfig
from neosintez_api.core.client import NeosintezClient
from neosintez_api.models import NeosintezBaseModel
from neosintez_api.services.object_service import ObjectService
from neosintez_api.services.class_service import ClassService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("appius_sync.log", encoding="utf-8"), logging.StreamHandler()]
)
logger = logging.getLogger("appius_sync")

# --- Модели данных Неосинтез ---

class AppiusFolder(NeosintezBaseModel):
    class Neosintez:
        class_name = "Папка"
    
    name: str = Field(..., description="Наименование папки", alias="Наименование")


class AppiusElementPIRSMR(NeosintezBaseModel):
    class Neosintez:
        class_name = "Элемент справочника"
        
    name: str = Field(..., alias="Наименование")
    organization: Optional[str] = Field(default=None, alias="Организация")
    field_text: Optional[str] = Field(default=None, alias="Месторождение (текст)")
    direction: Optional[str] = Field(default=None, alias="Направление деятельности")
    object_types: Optional[str] = Field(default=None, alias="Виды объектов")
    object_groups: Optional[str] = Field(default=None, alias="Группы объектов")
    guid_appius: Optional[str] = Field(default=None, alias="1С:Appius")
    code_1c: Optional[str] = Field(default=None, alias="Код 1С")


class AppiusElementPE(NeosintezBaseModel):
    class Neosintez:
        class_name = "Элемент справочника"
        
    name: str = Field(..., alias="Наименование")
    organization: Optional[str] = Field(default=None, alias="Организация")
    field_text: Optional[str] = Field(default=None, alias="Месторождение_")
    direction: Optional[str] = Field(default=None, alias="Направление деятельности")
    object_types: Optional[str] = Field(default=None, alias="Виды объектов")
    object_groups: Optional[str] = Field(default=None, alias="Группы объектов")
    guid_appius: Optional[str] = Field(default=None, alias="1С:Appius")
    code_nsi: Optional[str] = Field(default=None, alias="Код НСИ")


class AppiusViewRow(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    
    guid_appius: str = Field(min_length=1, alias="GUID")
    name: str = Field(min_length=1, alias="ПолноеНаименование")
    is_deleted: Optional[str] = Field("False", alias="ПометкаУдаления")
    org: str = Field(alias="Организация")
    field_text: str = Field(default="", alias="МесторождениеНаименование")
    direction: str = Field(default="", alias="НаправлениеДеятельности")
    obj_type: str = Field(default="", alias="ВидОбъекта")
    obj_group: str = Field(default="", alias="ГруппаОбъекта")
    code: str = Field(alias="Код")

    @field_validator("org", mode="before")
    @classmethod
    def org_required_non_empty(cls, v):
        if v is None:
            raise ValueError("Организация обязательна")
        s = str(v).strip()
        if not s or s.lower() in ("nan", "none", "null"):
            raise ValueError("Организация обязательна")
        return s

    @field_validator("code", mode="before")
    @classmethod
    def code_required_non_empty(cls, v):
        if v is None:
            raise ValueError("Код обязателен")
        s = str(v).strip()
        if not s or s.lower() in ("nan", "none", "null"):
            raise ValueError("Код обязателен")
        return s

    @field_validator(
        "field_text",
        "direction",
        "obj_type",
        "obj_group",
        mode="before",
    )
    @classmethod
    def _empty_str_if_none(cls, v):
        return "" if v is None else v

    @property
    def display_name(self) -> str:
        return str(self.name) if self.name else str(self.name or "")


def validate_data(raw_data: list[dict]) -> list[AppiusViewRow]:
    result = []
    for item in raw_data:
        try:
            entity = AppiusViewRow.model_validate(item)
            result.append(entity)
        except ValidationError as ex:
            error_details = ex.errors()
            for error in error_details:
                locations = ", ".join([str(loc) for loc in error["loc"]])
                msg = error["msg"]
                logger.error(f'[Валидация] "{locations}" "{msg}"')
    return result


def get_src_data() -> list[AppiusViewRow]:
    logger.info("Получение данных из микросервиса...")
    response = requests.get("http://neosintez-ir:6003/api/v1/views/bi_production_nonproduction_objects", timeout=60)
    response.raise_for_status()
    src_data = json.loads(response.text)
    validated_entities = validate_data(src_data)
    return validated_entities



class SyncManager:
    def __init__(self, client: NeosintezClient, portal_name: str, root_folder_id: str, is_pe: bool = False):
        self.client = client
        self.object_service = ObjectService(client)
        self.portal_name = portal_name
        self.root_folder_id = root_folder_id
        self.is_pe = is_pe
        
        # Кэш для папок: path_tuple -> folder_id
        self.folder_cache = {}
        self.folders_to_check = set()
        # Статистика
        self.stats = {"created": 0, "updated": 0, "deleted": 0, "errors": 0, "moved": 0}
        
        # Кэш для быстрого поиска объектов по GUID
        self.guid_cache = {}
        self.cache_populated = False
        # ID класса «Папка» (лениво, для поиска только среди прямых детей)
        self._folder_class_id: Optional[str] = None

    @staticmethod
    def _normalize_for_compare(value):
        # Для строк считаем None и "" эквивалентными, чтобы не делать лишних update.
        if value is None:
            return ""
        return value

    async def _folder_class_entity_id(self) -> str:
        if self._folder_class_id is not None:
            return self._folder_class_id
        class_service = ClassService(self.client)
        found = await class_service.find_by_names(["Папка"])
        if not found:
            raise ValueError("Класс «Папка» не найден в метаданных портала")
        if len(found) > 1:
            logger.warning(
                f"[{self.portal_name}] Несколько классов с именем «Папка», используется Id={found[0].Id}"
            )
        self._folder_class_id = str(found[0].Id)
        return self._folder_class_id

    async def populate_guid_cache(self, model_cls):
        """Выкачивает и кэширует GUID-ы всех элементов справочника один раз для молниеносного точного поиска."""
        if self.cache_populated:
            return
            
        logger.info(f"[{self.portal_name}] Кэширование всех элементов справочника для быстрого поиска...")
        search_service = self.client.search
        all_objects = await search_service.query() \
            .with_class_name("Элемент справочника") \
            .with_parent_id(self.root_folder_id) \
            .find_all()
            
        logger.info(f"[{self.portal_name}] Найдено {len(all_objects)} справочных объектов. Скачиваем атрибуты...")
        
        batch_size = 20
        for i in range(0, len(all_objects), batch_size):
            batch = all_objects[i:i+batch_size]
            tasks = [self.object_service.read(str(obj.Id), model_cls) for obj in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for j, res in enumerate(results):
                if not isinstance(res, Exception):
                    guid_val = getattr(res, 'guid_appius', None)
                    if guid_val:
                        self.guid_cache[str(guid_val)] = (all_objects[i+j], res)
                    
        self.cache_populated = True
        logger.info(f"[{self.portal_name}] Кэширование завершено. Разрешено {len(self.guid_cache)} уникальных GUID.")

    async def get_or_create_folder(self, parent_id: str, folder_name: str, path_key: tuple) -> str:
        if path_key in self.folder_cache:
            return self.folder_cache[path_key]
        
        # Только прямые дочерние объекты: фильтр BY_PARENT в поиске API даёт поддерево,
        # из‑за чего с одинаковым именем находятся папки глубже по ветке.
        try:
            folder_class_id = await self._folder_class_entity_id()
            children = await self.client.objects.get_children(parent_id)
            name_lower = folder_name.strip().lower()
            matches = [
                c
                for c in children
                if str(c.EntityId) == folder_class_id
                and (c.Name or "").strip().lower() == name_lower
            ]
            if len(matches) > 1:
                logger.warning(
                    f"[{self.portal_name}] У родителя {parent_id} несколько папок «{folder_name}», "
                    f"используется первая (Id={matches[0].Id})"
                )
            if matches:
                folder_id = str(matches[0].Id)
                self.folder_cache[path_key] = folder_id
                return folder_id
            
            # Если не найдено - создаем
            folder_model = AppiusFolder(name=folder_name)
            created = await self.object_service.create(folder_model, parent_id=parent_id)
            folder_id = str(created._id)
            self.folder_cache[path_key] = folder_id
            logger.info(f"[{self.portal_name}] Создана папка '{folder_name}' (ID: {folder_id})")
            return folder_id
            
        except Exception as e:
            logger.error(f"[{self.portal_name}] Ошибка получения/создания папки '{folder_name}': {e}")
            raise

    async def ensure_folder_structure(self, org, field, direction, obj_type, obj_group) -> str:
        """
        Создаёт/находит цепочку папок: организация всегда первая; далее только непустые
        уровни — Месторождение → Направление → Виды объектов → Группы объектов.
        Родитель элемента — папка последнего непустого уровня (организация минимум).
        """
        levels = [
            (org,                 "Организация"),
            (field,               "Месторождение"),
            (direction,           "Направление деятельности"),
            (obj_type,            "Виды объектов"),
            (obj_group,           "Группы объектов")
        ]
        
        current_parent_id = self.root_folder_id
        current_path = []
        
        for name, _level_desc in levels:
            name_str = str(name).strip()
            if not name_str or name_str.lower() in ("nan", "none", "null"):
                continue
                
            current_path.append(name_str)
            path_key = tuple(current_path)
            
            current_parent_id = await self.get_or_create_folder(current_parent_id, name_str, path_key)
            
        return current_parent_id

    async def sync_element(self, row: AppiusViewRow):
        guid = str(row.guid_appius)
        name = row.display_name
        is_deleted = str(row.is_deleted).lower() in ("true", "1", "yes")
        
        org = str(row.org or "")
        field = str(row.field_text or "")
        direction = str(row.direction or "")
        obj_type = str(row.obj_type or "")
        obj_group = str(row.obj_group or "")
        code = str(row.code or "")

        if not guid:
            logger.warning(f"[{self.portal_name}] Пропуск строки без 1С:Appius (GUID). Строка: {row}")
            self.stats["errors"] += 1
            return

        try:
            # СНАЧАЛА валидация (если выбросится ValidationError, обработка прервется ДО создания папок)
            if self.is_pe:
                model_instance = AppiusElementPE(
                    name=name, organization=org, field_text=field, 
                    direction=direction, object_types=obj_type, 
                    object_groups=obj_group, guid_appius=guid, code_nsi=code
                )
                model_cls = AppiusElementPE
            else:
                model_instance = AppiusElementPIRSMR(
                    name=name, organization=org, field_text=field, 
                    direction=direction, object_types=obj_type, 
                    object_groups=obj_group, guid_appius=guid, code_1c=code
                )
                model_cls = AppiusElementPIRSMR

            # 1. Поиск сущности по GUID
            # Так как API Неосинтеза игнорирует атрибут (не индексирован), мы используем 100% надежный локальный кэш
            if not self.cache_populated:
                await self.populate_guid_cache(model_cls)
                
            cached_data = self.guid_cache.get(guid)
            if cached_data:
                existing, read_obj = cached_data
            else:
                existing, read_obj = None, None
            
            if is_deleted:
                if existing:
                    # Пометка удаления = True, удаляем
                    old_parent_id = str(existing.ParentId) if getattr(existing, "ParentId", None) else None
                    await self.object_service.delete(str(existing.Id))
                    logger.info(f"[{self.portal_name}] Элемент '{name}' удален (ПометкаУдаления=True)")
                    self.stats["deleted"] += 1
                    if old_parent_id:
                        self.folders_to_check.add(old_parent_id)
                return
            
            # Гарантируем структуру папок (выполнится ТОЛЬКО если все проверки выше прошли успешно)
            target_folder_id = await self.ensure_folder_structure(org, field, direction, obj_type, obj_group)
            
            if existing and read_obj:
                needs_update = False
                moved = False
                
                # Сверяем папку
                if read_obj._parent_id != target_folder_id:
                    old_parent_id = read_obj._parent_id
                    read_obj._parent_id = target_folder_id
                    needs_update = True
                    moved = True
                    if old_parent_id:
                        self.folders_to_check.add(old_parent_id)
                
                # Сверяем атрибуты
                for field_name in model_instance.model_fields.keys():
                    current_val = getattr(read_obj, field_name)
                    new_val = getattr(model_instance, field_name)
                    if self._normalize_for_compare(current_val) != self._normalize_for_compare(new_val):
                        setattr(read_obj, field_name, new_val)
                        needs_update = True
                        
                if needs_update:
                    await self.object_service.update(read_obj)
                    if moved:
                        self.stats["moved"] += 1
                        logger.info(f"[{self.portal_name}] Элемент '{name}' перемещен и обновлен.")
                    else:
                        self.stats["updated"] += 1
                        logger.info(f"[{self.portal_name}] Элемент '{name}' обновлен.")
            else:
                # Создаем новый
                await self.object_service.create(model_instance, parent_id=target_folder_id)
                self.stats["created"] += 1
                logger.info(f"[{self.portal_name}] Элемент '{name}' создан.")
                
        except ValidationError as e:
            logger.error(f"[{self.portal_name}] Ошибка валидации '{name}' (GUID: {guid}): структура не создана. Ошибка: {e}")
            self.stats["errors"] += 1
        except Exception as e:
            logger.error(f"[{self.portal_name}] Ошибка обработки '{name}' (GUID: {guid}): {e}")
            logger.error(traceback.format_exc())
            self.stats["errors"] += 1

    async def cleanup_empty_folders(self):
        to_check = list(self.folders_to_check)
        self.folders_to_check.clear()
        
        while to_check:
            folder_id = to_check.pop()
            if not folder_id or folder_id == self.root_folder_id:
                continue
                
            try:
                # Используем сырой запрос к API, чтобы избежать ошибок маппинга в get_children, 
                # которые могли отфильтровать валидные объекты (например, элементы справочника) 
                # и ошибочно определить папку как пустую.
                raw_children = await self.client._request("GET", f"api/objects/{folder_id}/children")
                
                if isinstance(raw_children, list) and len(raw_children) == 0:
                    # Папка действительно пуста - удаляем и проверяем родителя
                    folder_obj = await self.object_service.read(folder_id, AppiusFolder)
                    parent_id = folder_obj._parent_id
                    
                    await self.object_service.delete(folder_id)
                    logger.info(f"[{self.portal_name}] Пустая папка (ID: {folder_id}) автоматически перемещена в корзину.")
                    
                    if parent_id and parent_id != self.root_folder_id:
                        to_check.append(parent_id)
            except Exception as e:
                logger.error(f"[{self.portal_name}] Ошибка при проверке/удалении папки {folder_id}: {e}")

async def main():
    logger.info("Запуск интеграции справочника Аппиус -> Неосинтез")
    
    # 1. Читаем данные из микросервиса
    try:
        records = get_src_data()
        logger.info(f"Получено и провалидировано {len(records)} записей из микросервиса.")
    except Exception as e:
        logger.error(f"Ошибка получения данных из микросервиса: {e}")
        return

    # 2. Настройки порталов Неосинтез
    base_settings = NeosintezConfig()
    
    # ПИР+СМР (основной портал)
    pirsmr_root_id = "0217dcde-f348-f111-9215-005056b6948b"
    
    # ПЭ
    pe_base_url = os.getenv("NEOSINTEZ_PE_URL")
    pe_root_id = "19437743-5f23-f111-920e-005056b6948b"

    summary_messages = []

    # --- Синхронизация ПИР+СМР ---
    if pirsmr_root_id:
        logger.info(f"Подключение к ПИР+СМР по адресу {base_settings.base_url}...")
        pirsmr_config = base_settings
        try:
            async with NeosintezClient(pirsmr_config) as pirsmr_client:
                manager = SyncManager(pirsmr_client, "ПИР+СМР", pirsmr_root_id, is_pe=False)
                for i, row in enumerate(records):
                    if i % 50 == 0:
                        logger.info(f"[ПИР+СМР] Обработано {i}/{len(records)}")
                    await manager.sync_element(row)
                
                await manager.cleanup_empty_folders()
                
                stats = manager.stats
                msg = f"ПИР+СМР успешно обновлен. Создано: {stats['created']}, Обновлено: {stats['updated']}, Перемещено: {stats['moved']}, Удалено: {stats['deleted']}, Ошибок: {stats['errors']}"
                logger.info(msg)
                summary_messages.append(msg)
        except Exception as e:
            logger.error(f"Ошибка при работе с ПИР+СМР: {e}")
            summary_messages.append(f"Ошибка при работе с ПИР+СМР: {e}")
    else:
        logger.warning("Неполные настройки для ПИР+СМР, пропускаем портал.")

    # --- Синхронизация ПЭ ---
    if pe_base_url and pe_root_id:
        logger.info("Подключение к ПЭ...")
        pe_config = base_settings.model_copy(update={"base_url": pe_base_url})
        try:
            async with NeosintezClient(pe_config) as pe_client:
                manager = SyncManager(pe_client, "ПЭ", pe_root_id, is_pe=True)
                for i, row in enumerate(records):
                    if i % 50 == 0:
                        logger.info(f"[ПЭ] Обработано {i}/{len(records)}")
                    await manager.sync_element(row)
                
                await manager.cleanup_empty_folders()
                
                stats = manager.stats
                msg = f"ПЭ успешно обновлен. Создано: {stats['created']}, Обновлено: {stats['updated']}, Перемещено: {stats['moved']}, Удалено: {stats['deleted']}, Ошибок: {stats['errors']}"
                logger.info(msg)
                summary_messages.append(msg)
        except Exception as e:
            logger.error(f"Ошибка при работе с ПЭ: {e}")
            summary_messages.append(f"Ошибка при работе с ПЭ: {e}")
    else:
        logger.warning("Неполные настройки для ПЭ, пропускаем портал.")

    # 3. Логирование итогов
    final_msg = "Интеграция Аппиус -> Неосинтез завершена.\n" + "\n".join(summary_messages)
    logger.info(final_msg)


if __name__ == "__main__":
    if os.name == "nt":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
