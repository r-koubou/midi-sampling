from typing import List, Dict, Tuple
import os
import json
from logging import getLogger
from jsonschema import validate as json_validate
from referencing import Registry, Resource

logger = getLogger(__name__)

class JsonSchemaInfo:

    @classmethod
    def from_content(cls, schema_uri: str, schema_content: any):
        return cls(schema_uri, schema_content)

    @classmethod
    def from_file(cls, schema_uri: str, schema_file_path: str):
        with open(schema_file_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
        return cls(schema_uri, schema)

    def __init__(self, schema_uri: str, schema: any):
        self.schema_uri: str = schema_uri
        self.schema: any = schema

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
        self.registry = Registry().with_resources([
            (main_schema.schema_uri, Resource.from_contents(main_schema.schema))
        ])

        for x in self.sub_schema_info_list:
            self.registry = self.registry.with_resources([
                (x.schema_uri, Resource.from_contents(x.schema))
            ])

    def validate(self, json_body) -> bool:
        json_validate(
            instance=json_body,
            schema=self.main_schema.schema,
            registry=self.registry
        )
