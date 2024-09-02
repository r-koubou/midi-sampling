from typing import List, Dict, Tuple
import os
import json
from logging import getLogger
from jsonschema import validate as json_validate
from referencing import Registry

logger = getLogger(__name__)

class JsonSchemaInfo:
    def __init__(self, schema_uri: str, schema_file_path: str):
        """
        Initialize the JsonSchemaInfo with a schema URI and a schema file path.

        Parameters
        ----------
        schema_uri: str
            The URI of the schema. This value is used in the "$ref" field of the schema.
        schema_file_path: str
            The file path of the schema.
        """
        self.schema_uri = schema_uri
        self.schema_file_path = schema_file_path
        with open(schema_file_path, "r", encoding="utf-8") as f:
            self.schema = json.load(f)

class JsonValidator:
    def __init__(self, main_schema: JsonSchemaInfo, sub_schema_info_list: List[JsonSchemaInfo] = []):
        """
        Initialize the JsonValidator with a list of schema info.

        Parameters
        ----------
        sub_schema_info_list: List[JsonSchemaInfo]
            A list of JsonSchemaInfo.
        Examples
        --------

        ```python
        validator = JsonValidator(
            sub_schema_info_list = [
                JsonSchemaInfo("schema/person", "schema/person.json"),
                JsonSchemaInfo("schema/organization", "schema/organization.json")
            ]
        )

        json_body = {
            "name": "Taro Yamaada",
            "age": 30,
            "organization": {
                "name": "Acme Corporation"
            }
        }
        validator.validate(json_body)
        ```

        ## JSON schema examples: person.json
        ```json
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": {
                "name": {
                    "type": "string"
                },
                "age": {
                    "type": "integer"
                },
                "organization": {
                    "$ref": "schema/organization"
                }
            }
        }
        ```

        ## JSON schema examples: organization.json
        ```json
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": {
                "name": {
                    "type": "string"
                }
            }
        }
        ```
        """
        self.main_schema = main_schema
        self.sub_schema_info_list = sub_schema_info_list
        self.registry = Registry().with_resource(main_schema.schema_uri, main_schema.schema)

        for x in self.sub_schema_info_list:
            self.registry = self.registry.with_resource(x.schema_uri, x.schema)

        print(self.registry.items())

        for uri, _ in self.registry.items():
            print(f"  - {uri}")

    def validate(self, json_body: dict) -> bool:
        json_validate(
            instance=json_body,
            schema=self.main_schema.schema,
            registry=self.registry
        )


if __name__ == "__main__":
    import sys
    THIS_DIR = os.path.dirname(os.path.abspath(__file__))

    try:
        main_schema = JsonSchemaInfo(
            schema_uri="main",
            schema_file_path=os.path.join(THIS_DIR, "..", "appconfig", "midi-config.schema.json")
        )

        with open(sys.argv[1], "r", encoding="utf-8") as f:
            json_body = json.load(f)

        validator = JsonValidator(main_schema)
        validator.validate(json_body)
        print("OK")
    except Exception as e:
        print(e)
