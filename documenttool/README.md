docmenttool
===========

This directory contains Python scripts to assist with documentation.

## Python Runtime Environment

Since pipenv is being used, activate the virtual environment with the following command:

```bash
pipenv shell
```

## jsonschema_to_md.py

`jsonschema_to_md.py` is a script that converts a JSON Schema into Markdown format and copies it to the clipboard. By pasting it into the `/README.md` description, the contents of the JSON Schema can be easily reflected and viewed in the documentation.

### Known Schema files

- `appconfig/*.schema.json`

### Usage

```bash
python jsonschema_to_md.py <JSON Schema file1> [<JSON Schema file2> ...]
```
