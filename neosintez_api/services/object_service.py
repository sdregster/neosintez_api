"""
Сервисный слой для работы с объектами через Pydantic-модели.
Обеспечивает создание, чтение и обновление объектов через типизированные модели данных.
"""

import asyncio
import logging
from typing import TYPE_CHECKING, Any, Dict, Generic, List, Optional, Type, Union
from uuid import UUID

from neosintez_api.config import settings
from neosintez_api.core.exceptions import NeosintezAPIError

from .class_service import ClassService
from .mappers.object_mapper import ObjectMapper
from .models import BulkCreateResult, CreateRequest, T
from .resolvers import AttributeResolver


# Настройка логгера
logger = logging.getLogger("neosintez_api.services.object_service")

if TYPE_CHECKING:
    from neosintez_api.models import NeosintezBaseModel

    from ..core.client import NeosintezClient


class ObjectService(Generic[T]):
    """
    Сервис для работы с объектами через Pydantic-модели.
    Обеспечивает создание, чтение и обновление объектов.
    """

    def __init__(self, client: "NeosintezClient"):
        """
        Инициализирует сервис с клиентом API.

        Args:
            client: Экземпляр клиента для взаимодействия с API
        """
        self.client = client
        self.mapper = ObjectMapper()
        self.class_service = ClassService(client)
        self.resolver = AttributeResolver(client)

    async def create(
        self,
        model: Union["NeosintezBaseModel", T],
        class_id: Optional[str] = None,
        class_name: Optional[str] = None,
        attributes_meta: Optional[Dict[str, Any]] = None,
        parent_id: Union[str, UUID, None] = None,
    ) -> T:
        """
        Создает объект из Pydantic-модели.

        Может работать в двух режимах:
        1. Декларативный: Принимает наследника NeosintezBaseModel.
           Сервис сам определяет класс и разрешает атрибуты.
        2. Явный: Принимает обычную модель и метаданные (class_id и т.д.).
           Используется для работы с динамически созданными моделями.

        Args:
            model: Экземпляр Pydantic-модели с данными.
            class_id: ID класса (для явного режима).
            class_name: Имя класса (для явного режима).
            attributes_meta: Метаданные атрибутов (для явного режима).
            parent_id: Идентификатор родительского объекта.

        Returns:
            T: Экземпляр модели, дополненный ID созданного объекта.

        Raises:
            ApiError: Если произошла ошибка при создании объекта.
            ValueError: Если переданы некорректные аргументы.
        """
        from neosintez_api.models import NeosintezBaseModel

        object_name: str

        # --- Диспетчеризация ---
        if isinstance(model, NeosintezBaseModel):
            # Декларативный режим
            if not hasattr(model, "Neosintez") or not hasattr(model.Neosintez, "class_name"):
                raise ValueError("Декларативная модель должна иметь внутренний класс Neosintez с атрибутом class_name")

            object_name = model.name
            class_name = model.Neosintez.class_name
            logger.info(f"Запуск создания в декларативном режиме для объекта '{object_name}' класса '{class_name}'")

            # Получаем метаданные класса
            found_classes = await self.class_service.find_by_name(class_name)
            if not found_classes:
                raise ValueError(f"Класс с именем '{class_name}' не найден.")
            if len(found_classes) > 1:
                # Попытка найти точное совпадение
                exact_matches = [c for c in found_classes if c.Name.lower() == class_name.lower()]
                if len(exact_matches) == 1:
                    class_info = exact_matches[0]
                else:
                    raise ValueError(f"Найдено несколько классов с именем, похожим на '{class_name}'. Уточните имя.")
            else:
                class_info = found_classes[0]

            class_id = str(class_info.Id)

            # Получаем атрибуты и создаем словарь для маппинга
            class_attributes = await self.class_service.get_attributes(class_id)
            attributes_meta = {attr.Name: attr for attr in class_attributes}

            # Создаем копию модели для подготовки к отправке в API.
            # Мы не хотим менять исходный экземпляр пользователя.
            model_for_api = model.model_copy(deep=True)

            # Разрешаем ссылочные атрибуты
            for field_name, field_info in model.__class__.model_fields.items():
                if field_info.alias and field_info.alias in attributes_meta:
                    attr_meta = attributes_meta[field_info.alias]
                    attr_value = getattr(model_for_api, field_name)

                    # Если это ссылочный атрибут и значение - строка, разрешаем его
                    if attr_meta.Type == 8 and isinstance(attr_value, str):
                        logger.debug(f"Разрешение ссылочного атрибута '{attr_meta.Name}' со значением '{attr_value}'")
                        try:
                            resolved_obj = await self.resolver.resolve_link_attribute_as_object(
                                attr_meta=attr_meta, attr_value=attr_value
                            )
                            # Обновляем значение в копии модели
                            setattr(model_for_api, field_name, resolved_obj)
                            logger.debug(f"Атрибут '{attr_meta.Name}' разрешен в объект: {resolved_obj}")
                        except ValueError as e:
                            logger.warning(
                                f"Не удалось разрешить значение '{attr_value}' для ссылочного "
                                f"атрибута '{attr_meta.Name}'. Атрибут будет пропущен. Ошибка: {e}"
                            )
                            # Пропускаем атрибут, не устанавливая его
                            setattr(model_for_api, field_name, None)

            # В дальнейшем для создания будет использоваться model_for_api
            # Здесь мы временно передаем исходную модель, чтобы не ломать маппер
            # TODO: Адаптировать маппер для работы с уже разрешенными данными

        elif all([class_id, class_name, attributes_meta]):
            # Явный режим
            object_name = model.name
            logger.info(f"Запуск создания в явном режиме для объекта '{object_name}' класса '{class_name}'")

        else:
            raise ValueError(
                "Для создания объекта необходимо передать либо наследника NeosintezBaseModel, либо полную мета-информацию (class_id, class_name, attributes_meta)."
            )

        try:
            # 1. Получаем имя из модели (уже сделано выше)
            logger.info(f"Создание объекта '{object_name}' класса '{class_name}' (ID: {class_id})")

            # 2. Создаем объект в API без атрибутов
            object_data = {
                "Name": object_name,
                "Entity": {"Id": class_id, "Name": class_name},
            }
            response = await self.client.objects.create(object_data, parent_id=parent_id)
            object_id = response.get("Id")
            if not object_id:
                raise NeosintezAPIError("Не удалось получить ID созданного объекта после создания")
            logger.debug(f"Объект '{object_name}' создан с ID: {object_id}")

            # 3. Преобразуем модель в атрибуты с помощью маппера
            attr_meta_by_name = {
                (a["Name"] if isinstance(a, dict) else a.Name): (a if isinstance(a, dict) else a.model_dump())
                for a in attributes_meta.values()
            }

            # Используем model_for_api если она была создана, иначе исходную модель
            source_model_for_mapper = locals().get("model_for_api", model)
            attributes_list = await self.mapper.model_to_attributes(source_model_for_mapper, attr_meta_by_name)

            # 4. Устанавливаем атрибуты
            if attributes_list:
                await self.client.objects.set_attributes(object_id, attributes_list)
                logger.info(f"Для объекта {object_id} установлено {len(attributes_list)} атрибутов.")

            # 5. Возвращаем обновленную модель с ID
            if isinstance(model, NeosintezBaseModel):
                model._id = object_id
                model._class_id = class_id
                model._parent_id = str(parent_id) if parent_id else None
            else:
                # Для обратной совместимости со старыми моделями
                model.id = object_id
                model.class_id = class_id
                model.parent_id = str(parent_id) if parent_id else None
            return model

        except Exception as e:
            logger.error(f"Ошибка API при создании объекта '{object_name}': {e}")
            raise

    async def create_many(
        self,
        requests: List[CreateRequest[T]],
    ) -> BulkCreateResult[T]:
        """
        Массовое создание объектов из списка запросов.

        Args:
            requests: Список запросов на создание, каждый из которых
                      содержит модель и метаданные.

        Returns:
            BulkCreateResult: Результат с созданными моделями и ошибками.
        """
        logger.info(f"Начало массового создания {len(requests)} объектов.")
        result = BulkCreateResult[T]()

        for request in requests:
            try:
                created_model = await self.create(
                    model=request.model,
                    class_id=request.class_id,
                    class_name=request.class_name,
                    attributes_meta=request.attributes_meta,
                    parent_id=request.parent_id,
                )
                result.created_models.append(created_model)
            except Exception as e:
                error_msg = f"Ошибка при создании объекта '{request.model.name}': {e}"
                logger.error(error_msg, exc_info=True)
                result.errors.append(error_msg)

        logger.info(f"Массовое создание завершено. Успешно: {len(result.created_models)}, Ошибок: {len(result.errors)}")
        return result

    async def read(self, object_id: Union[str, UUID], model_class: Type[T]) -> T:
        """
        Читает объект и преобразует его в плоскую модель Pydantic.

        Args:
            object_id: Идентификатор объекта.
            model_class: Класс Pydantic-модели, в который нужно преобразовать данные.
                         Если это наследник NeosintezBaseModel, системные поля
                         (_id, _class_id, _parent_id) будут заполнены автоматически.

        Returns:
            Экземпляр model_class с данными объекта.
        """
        try:
            # 1. Параллельно получаем данные объекта и его путь
            object_data, path_data = await asyncio.gather(
                self.client.objects.get_by_id(object_id),
                self.client.objects.get_path(object_id),
            )
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"Получен объект {object_id} и его путь.")

            class_id = object_data["EntityId"]

            # 2. Получаем метаданные атрибутов класса
            class_attributes = await self.class_service.get_attributes(str(class_id))
            attr_id_to_name = {str(attr.Id): attr.Name for attr in class_attributes}

            # Строим карту для сопоставления имени атрибута API с именем поля модели
            alias_to_field_map = {(f.alias or n): n for n, f in model_class.model_fields.items()}

            # 3. Определяем родителя
            parent_id = None
            if path_data and path_data.AncestorsOrSelf and len(path_data.AncestorsOrSelf) > 1:
                # Родитель - это предпоследний элемент в пути
                parent_id = str(path_data.AncestorsOrSelf[-2].Id)

            # 4. Собираем данные для создания модели
            flat_data = {}
            if "name" in model_class.model_fields:
                flat_data["name"] = object_data["Name"]

            # 5. Извлекаем и преобразуем атрибуты
            if "Attributes" in object_data and object_data["Attributes"]:
                for attr_id_str, attr_value_data in object_data["Attributes"].items():
                    api_attr_name = attr_id_to_name.get(attr_id_str)
                    if not api_attr_name:
                        logger.warning(f"Атрибут с ID {attr_id_str} не найден в метаданных класса.")
                        continue

                    field_name = alias_to_field_map.get(api_attr_name)
                    if not field_name:
                        logger.warning(
                            f"Для атрибута '{api_attr_name}' не найдено соответствующее поле в модели {model_class.__name__}."
                        )
                        continue

                    attr_value = attr_value_data.get("Value")

                    # Если значение - словарь (ссылочный атрибут), а поле модели ждет строку, берем Name
                    if isinstance(attr_value, dict) and "Name" in attr_value:
                        target_field = model_class.model_fields.get(field_name)
                        if target_field and target_field.annotation == str:
                            attr_value = attr_value.get("Name")

                    flat_data[field_name] = attr_value

            # "Выпрямляем" ссылочные атрибуты: из {Id:.., Name: ..} делаем просто Name
            for key, value in flat_data.items():
                if isinstance(value, dict) and "Name" in value:
                    flat_data[key] = value["Name"]

            # 6. Создаем экземпляр модели
            try:
                instance = model_class(**flat_data)
            except Exception as e:
                logger.error(f"Ошибка при чтении объекта {object_id}: {e}")
                raise

            # 7. Если это наша базовая модель, заполняем системные поля
            from neosintez_api.models import NeosintezBaseModel

            if isinstance(instance, NeosintezBaseModel):
                instance._id = str(object_id)
                instance._class_id = class_id
                instance._parent_id = str(parent_id) if parent_id else None

            return instance

        except Exception as e:
            logger.error(f"Ошибка при чтении объекта {object_id}: {e}")
            raise

    async def update(
        self,
        model: Union["NeosintezBaseModel", T],
    ) -> T:
        """
        Интеллектуально обновляет объект на основе Pydantic-модели.

        Автоматически определяет, какие поля были изменены (имя, родитель, атрибуты),
        и выполняет необходимые запросы к API параллельно.
        Работает только с декларативными моделями (наследниками NeosintezBaseModel).

        Args:
            model: Экземпляр модели с обновленными данными.
                   Должен содержать `_id` и `_class_id`.

        Returns:
            T: Обновленный экземпляр модели.

        Raises:
            ValueError: Если модель не содержит необходимых данных.
            NeosintezAPIError: Если произошла ошибка API.
        """
        from neosintez_api.models import NeosintezBaseModel

        if not isinstance(model, NeosintezBaseModel) or not model._id or not model._class_id:
            raise ValueError(
                "Для 'умного' обновления модель должна быть наследником NeosintezBaseModel "
                "и содержать `_id` и `_class_id`."
            )

        object_id = model._id
        logger.info(f"Запуск интеллектуального обновления для объекта ID: {object_id}")

        # 1. Параллельно получаем текущее состояние объекта и его метаданные
        try:
            current_data, path_data, class_attributes = await asyncio.gather(
                self.client.objects.get_by_id(object_id),
                self.client.objects.get_path(object_id),
                self.client.classes.get_attributes(model._class_id),
            )
            attributes_meta = {attr.Name: attr for attr in class_attributes}
        except Exception as e:
            logger.error(f"Не удалось получить текущее состояние объекта {object_id}: {e}")
            raise

        # 2. Собираем задачи для параллельного выполнения
        update_tasks = []

        # --- Сравнение и добавление задачи на переименование ---
        if model.name != current_data["Name"]:
            logger.info(f"Обнаружено изменение имени: '{current_data['Name']}' -> '{model.name}'")
            update_tasks.append(self.client.objects.rename(object_id, model.name))

        # --- Сравнение и добавление задачи на перемещение ---
        current_parent_id = None
        if path_data and path_data.AncestorsOrSelf and len(path_data.AncestorsOrSelf) > 1:
            current_parent_id = str(path_data.AncestorsOrSelf[-2].Id)

        if model._parent_id and model._parent_id != current_parent_id:
            logger.debug(f"Обнаружено изменение родителя: '{current_parent_id}' -> '{model._parent_id}'.")
            update_tasks.append(self.client.objects.move(object_id, model._parent_id))

        # --- Сравнение и обновление атрибутов ---
        # Получаем текущие значения атрибутов из `current_data`
        current_attributes = {}
        if "Attributes" in current_data and current_data["Attributes"]:
            for attr_id_str, attr_data in current_data["Attributes"].items():
                attr_meta = next((attr for attr in class_attributes if str(attr.Id) == attr_id_str), None)
                if attr_meta:
                    current_attributes[attr_meta.Name] = attr_data.get("Value")

        # Готовим модель для отправки в API: разрешаем ссылочные атрибуты
        model_for_api = await self._prepare_model_for_api(model, attributes_meta)

        # Получаем желаемые значения атрибутов из Pydantic модели
        new_attributes = await self._get_changed_attributes(
            model=model_for_api,
            attributes_meta=attributes_meta,
            current_attributes=current_attributes,
        )
        if new_attributes:
            logger.debug(f"Обнаружено {len(new_attributes)} измененных атрибутов.")
            update_tasks.append(self.client.objects.set_attributes(object_id, new_attributes))

        # 3. Выполняем все запланированные задачи
        if update_tasks:
            logger.info(f"Выполнение {len(update_tasks)} задач на обновление...")
            await asyncio.gather(*update_tasks)
            logger.info(f"Все операции для объекта {object_id} успешно выполнены.")
        else:
            logger.info(f"Для объекта {object_id} не обнаружено изменений.")

        # После всех операций заново читаем объект, чтобы вернуть модель
        # с гарантированно актуальным состоянием.
        logger.info(f"Повторное чтение объекта {object_id} для возврата актуальной модели.")
        return await self.read(object_id, model.__class__)

    async def _prepare_model_for_api(
        self, model: "NeosintezBaseModel", attributes_meta: Dict[str, Any]
    ) -> "NeosintezBaseModel":
        """
        Подготавливает модель к отправке в API, разрешая строковые значения
        ссылочных атрибутов в объекты-словари.
        """
        model_copy = model.model_copy(deep=True)
        model_fields = model_copy.__class__.model_fields

        for field_name, field_info in model_fields.items():
            alias = field_info.alias
            if not alias or alias not in attributes_meta:
                continue

            attr_meta = attributes_meta[alias]
            if attr_meta.Type != 8:  # 8 - тип "Ссылка на объект"
                continue

            value = getattr(model_copy, field_name)
            # Если значение - строка, его нужно разрешить в объект
            if isinstance(value, str):
                try:
                    resolved_obj = await self.resolver.resolve_link_attribute_as_object(
                        attr_meta=attr_meta, attr_value=value
                    )
                    if resolved_obj:
                        setattr(model_copy, field_name, resolved_obj)
                    else:
                        logger.warning(
                            f"Не удалось разрешить значение '{value}' для ссылочного атрибута '{alias}'. "
                            f"Атрибут будет пропущен при обновлении."
                        )
                        setattr(model_copy, field_name, None)
                except Exception:
                    logger.exception(f"Ошибка при разрешении значения '{value}' для атрибута '{alias}'")
                    setattr(model_copy, field_name, None)

        return model_copy

    async def _get_changed_attributes(
        self,
        model: T,
        attributes_meta: Dict[str, Any],
        current_attributes: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Возвращает список только тех атрибутов, значения которых изменились.
        """
        if current_attributes is None:
            current_attributes = {}

        # Преобразуем модель в "идеальный" список атрибутов
        attr_meta_by_name = {
            (a.Name if hasattr(a, "Name") else a["Name"]): (a.model_dump() if hasattr(a, "model_dump") else a)
            for a in attributes_meta.values()
        }
        new_attributes_list = await self.mapper.model_to_attributes(model, attr_meta_by_name)

        # Сравниваем новые атрибуты с текущими
        attributes_to_update = []
        for new_attr in new_attributes_list:
            attr_id = new_attr.get("Id")
            if not attr_id:
                continue

            current_attr_data = current_attributes.get(str(attr_id))
            current_value = current_attr_data.get("Value") if current_attr_data else None
            new_value = new_attr.get("Value")

            # Простое сравнение по строковому представлению.
            # TODO: Реализовать более строгое сравнение с учетом типов.
            if str(current_value) != str(new_value):
                attributes_to_update.append(new_attr)
        return attributes_to_update

    async def delete(self, object_id: Union[str, UUID]) -> bool:
        """
        Перемещает объект в папку "Корзина", если она задана в настройках.
        Если trash_folder_id не задан, выбрасывает ValueError.

        Args:
            object_id: Идентификатор объекта для "удаления".

        Returns:
            bool: True, если перемещение успешно.

        Raises:
            ValueError: Если `settings.trash_folder_id` не сконфигурирован.
        """
        if not settings.trash_folder_id:
            raise ValueError("Мягкое удаление невозможно: 'trash_folder_id' не задан в конфигурации.")

        logger.info(f"Перемещение объекта {object_id} в корзину (ID: {settings.trash_folder_id})")
        await self.client.objects.move(object_id=str(object_id), parent_id=settings.trash_folder_id)
        return True
