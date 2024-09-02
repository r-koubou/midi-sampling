from typing import List, Dict, Tuple
import os
import json
from logging import getLogger
from jsonschema import validate as json_validate
from referencing import Registry, Resource

logger = getLogger(__name__)

class JsonSchemaInfo:

    @classmethod
    def from_content(cls, schema_uri: str, schema_content: any) -> "JsonSchemaInfo":
        return cls(schema_uri, schema_content)

    @classmethod
    def from_file(cls, schema_uri: str, schema_file_path: str) -> "JsonSchemaInfo":
        with open(schema_file_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
        return cls(schema_uri, schema)

    @classmethod
    def from_files(cls, schema_info_list: List[Tuple[str, str]]) -> List["JsonSchemaInfo"]:
        """
        Create a list of JsonSchemaInfo from a list of schema file paths.

        Parameters
        ----------
        schema_info_list: List[Tuple[str, str]]
            A list of pairs of schema URI and schema file path.
            e.g.
            ```python
            [
                ("schema/person", "schema/person.json"),
                ("schema/organization", "schema/organization.json")
            ]
            ```

        Returns
        -------
        List[JsonSchemaInfo]
            A list of JsonSchemaInfo.
        """
        result: List[JsonSchemaInfo] = []
        for schema_uri, schema_file_path in schema_info_list:
            result.append(cls.from_file(schema_uri, schema_file_path))

        return result

    def __init__(self, schema_uri: str, schema: any):
        self.schema_uri: str = schema_uri
        self.schema: any = schema

class JsonValidator:
    def __init__(self, main_schema_info: JsonSchemaInfo, sub_schema_info_list: List[JsonSchemaInfo] = []):
        """
        Initialize the JsonValidator with a list of schema info.

        Parameters
        ----------
        sub_schema_info_list: List[JsonSchemaInfo]
            A list of JsonSchemaInfo.
        Examples
        --------

        ```python
        >>> validator = JsonValidator(
        ...     main_schema_info = JsonSchemaInfo("schema/main", "schema/main.json"),
        ...     sub_schema_info_list = JsonSchemaInfo.from_files([
        ...         ("schema/person", "schema/person.json"),
        ...         ("schema/organization", "schema/organization.json")
        ...     ])
        ... )
        ```
        """

        self.main_schema = main_schema_info
        self.sub_schema_info_list = sub_schema_info_list
        self.registry = Registry().with_resources([
            (main_schema_info.schema_uri, Resource.from_contents(main_schema_info.schema))
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
