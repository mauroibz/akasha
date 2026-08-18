import base64
import json
from dataclasses import asdict, dataclass
from typing import Any, Literal


class CursorError(ValueError):
    pass


@dataclass(frozen=True)
class CursorState:
    sort: str
    order: Literal["asc", "desc"]
    filter_key: str
    value: Any
    entry_id: int
    null_bucket: int
    # Bumped to 2 in Sprint 023. The creator sort stopped ordering by the first name
    # verbatim and started ordering by the stored creator sort name, so a cursor
    # issued before that migration compares "gabriel" against "garcia marquez
    # gabriel" and silently skips or repeats a page. Rejecting it is the point.
    v: int = 2


def encode_cursor(state: CursorState) -> str:
    raw = json.dumps(asdict(state), separators=(",", ":"), sort_keys=True).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(
    value: str, *, sort: str, order: Literal["asc", "desc"], filter_key: str
) -> CursorState:
    try:
        raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        payload = json.loads(raw)
        state = CursorState(**payload)
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as error:
        raise CursorError("cursor is malformed") from error
    if state.v != 2 or state.sort != sort or state.order != order or state.filter_key != filter_key:
        raise CursorError("cursor does not match this query")
    if state.null_bucket not in (0, 1) or state.entry_id < 1:
        raise CursorError("cursor values are invalid")
    return state
