"""Home's layout, stored per person (Sprint 131, DEC-183).

An ordered list of `{module, size, hidden}`. The module keys are Home's own, not a
domain's, so naming them here is not a branch on the item type. A stored layout is
read leniently: an unknown key or a malformed row is dropped, an unknown size falls
back to the module's default, and every module the layout does not name is appended
with its default. A write is strict: an unknown key, an unknown size or a module named
twice is refused.
"""

import json
from datetime import UTC, datetime
from typing import Any, Literal, TypedDict

from sqlalchemy import text
from sqlalchemy.engine import Engine

from book_tracker.application.library import LibraryError

Size = Literal["S", "M", "L"]
SIZES: tuple[Size, ...] = ("S", "M", "L")


class ModuleLayout(TypedDict):
    module: str
    size: Size
    hidden: bool


#: Every module, in its default order, with its default size. Sizes are column
#: spans on a wide screen (S 3, M 5, L 7 of 12); on a phone every module is full
#: width and its size only changes how much it shows.
DEFAULT_LAYOUT: tuple[ModuleLayout, ...] = (
    {"module": "now", "size": "M", "hidden": False},
    {"module": "next", "size": "L", "hidden": False},
    {"module": "year", "size": "L", "hidden": False},
    {"module": "lately", "size": "M", "hidden": False},
    {"module": "libraries", "size": "L", "hidden": False},
    {"module": "tidy", "size": "S", "hidden": False},
    {"module": "question", "size": "S", "hidden": False},
    {"module": "shelves", "size": "S", "hidden": False},
    {"module": "lent", "size": "S", "hidden": False},
)
MODULES: tuple[str, ...] = tuple(row["module"] for row in DEFAULT_LAYOUT)
_DEFAULTS = {row["module"]: row for row in DEFAULT_LAYOUT}


class LayoutError(LibraryError):
    """A refused layout, in the shared error envelope."""


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def defaults() -> list[ModuleLayout]:
    return [ModuleLayout(**row) for row in DEFAULT_LAYOUT]


def normalize(stored: object) -> list[ModuleLayout]:
    """A stored layout made whole: known modules in their order, then the rest."""
    rows: list[ModuleLayout] = []
    seen: set[str] = set()
    for row in stored if isinstance(stored, list) else []:
        if not isinstance(row, dict):
            continue
        module = row.get("module")
        if not isinstance(module, str) or module not in _DEFAULTS or module in seen:
            continue
        seen.add(module)
        default = _DEFAULTS[module]
        size = row.get("size")
        hidden = row.get("hidden")
        rows.append(
            {
                "module": module,
                "size": size if size in SIZES else default["size"],
                "hidden": hidden if isinstance(hidden, bool) else default["hidden"],
            }
        )
    rows.extend(ModuleLayout(**row) for row in DEFAULT_LAYOUT if row["module"] not in seen)
    return rows


class HomeLayoutService:
    def __init__(self, engine: Engine, user_id: int) -> None:
        self.engine = engine
        self.user_id = user_id

    def read(self) -> list[ModuleLayout]:
        with self.engine.connect() as connection:
            stored = connection.execute(
                text("SELECT layout_json FROM home_layouts WHERE user_id = :user"),
                {"user": self.user_id},
            ).scalar()
        if stored is None:
            return defaults()
        try:
            return normalize(json.loads(stored))
        except ValueError:
            return defaults()

    def hidden(self) -> set[str]:
        return {row["module"] for row in self.read() if row["hidden"]}

    def write(self, modules: list[dict[str, Any]]) -> list[ModuleLayout]:
        seen: set[str] = set()
        for row in modules:
            module = row.get("module")
            if module not in _DEFAULTS:
                raise LayoutError(
                    "unknown_module",
                    "Home has no module by that name",
                    status_code=422,
                    details={"module": module},
                )
            if module in seen:
                raise LayoutError(
                    "duplicate_module",
                    "Name each module once",
                    status_code=422,
                    details={"module": module},
                )
            if row.get("size") not in SIZES:
                raise LayoutError(
                    "invalid_size", "A size is S, M or L", status_code=422, details=row
                )
            seen.add(module)
        layout = normalize(modules)
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO home_layouts (user_id, layout_json, updated_at)"
                    " VALUES (:user, :layout, :now)"
                    " ON CONFLICT (user_id) DO UPDATE SET layout_json = excluded.layout_json,"
                    " updated_at = excluded.updated_at"
                ),
                {"user": self.user_id, "layout": json.dumps(layout), "now": _now()},
            )
        return layout
