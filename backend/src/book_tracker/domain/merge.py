from collections.abc import Mapping
from typing import Any


def is_empty(value: object) -> bool:
    return value is None or value == "" or value == [] or value == {}


def fill_empty(existing: Mapping[str, Any], incoming: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(existing)
    for key, value in incoming.items():
        if key not in result or is_empty(result[key]):
            result[key] = value
    return result
