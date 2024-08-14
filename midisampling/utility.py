import json

def as_json_structure(obj: object) -> None:
    return json.dumps(obj.__dict__, ensure_ascii=False, indent=2)
