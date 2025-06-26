import asyncio

from pydantic import BaseModel, Field

from neosintez_api.client import NeosintezClient
from neosintez_api.config import NeosintezSettings


# class TestModel(BaseModel):
#     __class_name__ = "Стройка"

#     name: str = Field(alias="Name")
#     mvz: str = Field(alias="МВЗ")
#     adept_id: int = Field(alias="ID стройки Адепт")


# test_model = TestModel(name="Тестовая стройка", mvz="12345", adept_id=544)


async def main():
    settings = NeosintezSettings()
    client = NeosintezClient(settings)

    # test_object_payload_for_creation = {
    #     "Id": "00000000-0000-0000-0002-000000000000",
    #     "Name": "Тестовая стройка",
    #     "Entity": {
    #         "Id": "3aa54908-2283-ec11-911c-005056b6948b",
    #         "Name": "forvalidation",
    #     },
    # }

    # Так создаётся объект без атрибутов
    # response = await client._request(
    #     "POST", "api/objects", data=test_object_payload_for_creation
    # )
    # """
    # response = 
    # {'EffectivePermissions': 8191, 'Entity': {'Id': '3aa54908-2283-ec11-911c-005056b6948b', 'Name': 'Стройка'}, 'Version': 1, 'VersionTimestamp': '2025-06-26T20:02:22.9687987', 'IsActualVersion': True, 'Id': '3398846a-8552-f011-91e5-005056b6948b', 'Name': 'Тестовая стройка'}
    # """

    # # А так мы сетим атрибуты после создания объекта
    # attributes_payload_for_creation = [
    #     {
    #         "Id": "626370d8-ad8f-ec11-911d-005056b6948b",
    #         "Name": "forvalidation",
    #         "Type": 2,
    #         "Value": "12345",
    #         "Constraints": [],
    #     },
    #     {
    #         "Id": "f980619f-b547-ee11-917e-005056b6948b",
    #         "Name": "forvalidation",
    #         "Type": 1,
    #         "Value": 544,
    #         "Constraints": [],
    #     },
    # ]

    # await client._request(
    #     "PUT",
    #     "api/objects/3aa54908-2283-ec11-911c-005056b6948b/attributes",
    #     data=attributes_payload_for_creation,
    # )

    # так мы можем запросить объект с атрибутами
    response = await client._request(
        "GET",
        "api/objects/3aa54908-2283-ec11-911c-005056b6948b",
    )
    
    """
    {
  "Entity": {
    "Id": "3aa54908-2283-ec11-911c-005056b6948b",
    "Name": "Стройка"
  },
  "Attributes": {
    "626370d8-ad8f-ec11-911d-005056b6948b": {
      "Value": "12345",
      "Type": 2,
      "Id": "626370d8-ad8f-ec11-911d-005056b6948b"
    },
    "f980619f-b547-ee11-917e-005056b6948b": {
      "Value": 544,
      "Type": 1,
      "Id": "f980619f-b547-ee11-917e-005056b6948b"
    }
  },
  "CreationDate": "2025-06-26T20:00:10.8371376",
  "ModificationDate": "2025-06-26T20:04:07.6198844",
  "Owner": {
    "Id": 6835,
    "Name": "Zhukov_SA"
  },
  "EffectivePermissions": 8191,
  "Icon": null,
  "Version": 1,
  "VersionTimestamp": "2025-06-26T20:00:10.8371376",
  "IsActualVersion": true,
  "Id": "30e7c21b-8552-f011-91e5-005056b6948b",
  "Name": "Тестовая стройка"
}
    """


if __name__ == "__main__":
    asyncio.run(main())
