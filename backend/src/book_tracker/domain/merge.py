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


def prefer_fuller(
    chosen: Mapping[str, Any], offered: Mapping[str, Any], fields: tuple[str, ...]
) -> dict[str, Any]:
    """The fields among `fields` where `offered` holds a longer string than
    `chosen`, and nothing else (DEC-115).

    This is the one declared place where a later provider's answer beats an
    earlier one: a long-text field where "one line" and "three paragraphs" are
    both complete answers of different value. A shorter or equally long answer
    changes nothing, a non-string on either side changes nothing, and every
    field outside `fields` is untouched — the rule is
    fuller-*than-what-would-otherwise-be-stored*, never "the last provider
    wins". Both the background enrichment handler and the add path apply it, so
    an item meets the same rule however it arrived.
    """
    fuller: dict[str, Any] = {}
    for field_name in fields:
        current = chosen.get(field_name)
        candidate = offered.get(field_name)
        if not isinstance(current, str) or not isinstance(candidate, str):
            continue
        if len(candidate) > len(current):
            fuller[field_name] = candidate
    return fuller
