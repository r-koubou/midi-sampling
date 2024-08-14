import os
import sys
import json

import jsonschema2md
import pyperclip

def json_schema_to_markdown(schema_file_path: str) -> str:
    parser = jsonschema2md.Parser(
        examples_as_yaml=False,
        show_examples="all"
    )

    with open(schema_file_path, "r") as f:
        markdown_lines = parser.parse_schema(json.load(f))

    return ''.join(markdown_lines)

if __name__ == "__main__":

    if len(sys.argv) < 2:
        print("Copy a converted markdown to clipboard.")
        print(f"Usage: python {os.path.basename(__file__)} <schema_file_path>")
        sys.exit(1)

    schema_file_path = sys.argv[1]
    md_txt = json_schema_to_markdown(schema_file_path)
    pyperclip.copy(md_txt)
    print("Copied to clipboard.")
