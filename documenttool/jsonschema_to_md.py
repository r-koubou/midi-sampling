import os
import sys
import json

import jsonschema2md
import pyperclip

def json_schema_to_markdown(schema_file_path: str, add_paragraph_count: int = 0) -> str:
    parser = jsonschema2md.Parser(
        examples_as_yaml=False,
        show_examples="all"
    )

    with open(schema_file_path, "r") as f:
        markdown_lines = parser.parse_schema(json.load(f))
        if add_paragraph_count > 0:
            markdown_lines = [("#" * add_paragraph_count) + line if line.startswith('#') else line for line in markdown_lines]

    return ''.join(markdown_lines)

if __name__ == "__main__":

    if len(sys.argv) < 2:
        print("Copy a converted markdown to clipboard.")
        print(f"Usage: python {os.path.basename(__file__)} <schema_file_path> [add paragraph ('#') count]")
        sys.exit(1)

    args = sys.argv[1:]

    schema_file_path = args[0]
    add_paragraph_count = int(args[1]) if len(args) > 1 else 0

    md_txt = json_schema_to_markdown(schema_file_path, add_paragraph_count)
    pyperclip.copy(md_txt)

    print("Copied to clipboard.")
