"""Home's layout, stored per person (Sprint 131, DEC-183).

An ordered list of `{module, size, hidden}`. The module keys are Home's own, not a
domain's, so naming them here is not a branch on the item type. A stored layout is
read leniently: an unknown key or a malformed row is dropped, an unknown size falls
back to the module's default, and every module the layout does not name is appended
with its default. A write is strict: an unknown key, an unknown size or a module named
twice is refused.

Since Sprint 138 (DEC-192) two module families sit beside the fixed modules: a year
per library, `year:<item type>`, for every registered domain whose entries carry a
finished date, and a shelf, `shelf:<shelf id>`, for each of this person's shelves. The
registry and the shelves table say which members exist; a row naming one that no
longer does (a deleted shelf) is dropped like any unknown key. A library's year is
shown by default, after *Up next*; a shelf is hidden until it is turned on.

Since Sprint 141 (DEC-193) the Library is the home and these are its showcases. What
its bands and tabs say is no longer a module (`now`, `lately`, `libraries`, `shelves`,
`tidy`, `lent` and the all-media `year`): a layout stored before then still names
them, and the lenient read drops them like any unknown key. Only *Up next* and the
libraries' years are shown until the person places more, so the grid stays near.

Sprint 142 adds a third family, a number from the Journal: `insight:<item type>:<section>`,
where a section is `scores`, `decade`, or a key the domain declares groupable. It is
offered for each medium the person holds an entry of, hidden until placed. The registry
says which keys exist, so nothing here names a medium.

Sprint 150 (DEC-195) makes `now` and `lately` layout items again: the owner wanted to
move *Lately* and turn it off. They are first and shown by default.
"""

import json
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, Literal, TypedDict

from sqlalchemy import text
from sqlalchemy.engine import Engine

from book_tracker.application.library import LibraryError
from book_tracker.domain.registry import DOMAINS

Size = Literal["S", "M", "L"]
SIZES: tuple[Size, ...] = ("S", "M", "L")


class ModuleLayout(TypedDict):
    module: str
    size: Size
    hidden: bool


class LabelledLayout(ModuleLayout):
    #: What *Edit home* calls a family member ("Books this year", "Shelf: Favorites");
    #: `None` for a fixed module, which the client names itself.
    label: str | None


#: The families' prefixes.
YEAR = "year:"
SHELF = "shelf:"
INSIGHT = "insight:"
#: The sections every medium has without declaring anything: how it is scored, and the
#: built-in ranking by decade.
INSIGHT_SCORES = "scores"
INSIGHT_DECADE = "decade"


#: Every module, in its default order, with its default size. Sizes are column
#: spans on a wide screen (S 3, M 5, L 7 of 12); on a phone every module is full
#: width and its size only changes how much it shows.
DEFAULT_LAYOUT: tuple[ModuleLayout, ...] = (
    # The two bands (Sprint 150, DEC-195): layout items like any other, so they can be
    # moved and removed; the screen always draws them the full width.
    {"module": "now", "size": "L", "hidden": False},
    {"module": "lately", "size": "L", "hidden": False},
    {"module": "next", "size": "L", "hidden": False},
    {"module": "question", "size": "S", "hidden": True},
    {"module": "suggested", "size": "M", "hidden": True},
)
MODULES: tuple[str, ...] = tuple(row["module"] for row in DEFAULT_LAYOUT)


class LayoutError(LibraryError):
    """A refused layout, in the shared error envelope."""


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def year_members() -> list[tuple[str, str]]:
    """`(key, label)` for each library whose entries can carry a finished date."""
    return [
        (f"{YEAR}{domain.item_type}", f"{domain.plural_label} this year")
        for domain in DOMAINS.values()
        if "date_finished" in domain.entry_fields
    ]


def insight_members(held: Sequence[str]) -> list[tuple[str, str]]:
    """`(key, label)` for each number a medium the person holds can show, in registry order."""
    members: list[tuple[str, str]] = []
    for domain in DOMAINS.values():
        if domain.item_type not in held:
            continue
        prefix = f"{INSIGHT}{domain.item_type}:"
        plural = domain.plural_label
        members.append((f"{prefix}{INSIGHT_SCORES}", f"How you rate {plural.lower()}"))
        members.append((f"{prefix}{INSIGHT_DECADE}", f"{plural} by decade"))
        members.extend(
            (f"{prefix}{field.name}", f"{plural} by {field.label.lower()}")
            for field in domain.fields
            if field.groupable
        )
    return members


def defaults(
    shelves: Sequence[tuple[int, str]] = (), held: Sequence[str] = ()
) -> list[LabelledLayout]:
    """The default: the fixed modules, each library's year after *Up next*, the shelves,
    then the numbers of each medium held."""
    rows: list[LabelledLayout] = []
    for row in DEFAULT_LAYOUT:
        rows.append(LabelledLayout(**row, label=None))
        if row["module"] == "next":
            rows.extend(
                LabelledLayout(module=key, size="M", hidden=False, label=label)
                for key, label in year_members()
            )
    rows.extend(
        LabelledLayout(module=f"{SHELF}{shelf_id}", size="M", hidden=True, label=f"Shelf: {name}")
        for shelf_id, name in shelves
    )
    rows.extend(
        LabelledLayout(module=key, size="S", hidden=True, label=label)
        for key, label in insight_members(held)
    )
    return rows


def normalize(
    stored: object, shelves: Sequence[tuple[int, str]] = (), held: Sequence[str] = ()
) -> list[LabelledLayout]:
    """A stored layout made whole: known modules in their order, then the rest."""
    known = {row["module"]: row for row in defaults(shelves, held)}
    rows: list[LabelledLayout] = []
    seen: set[str] = set()
    for row in stored if isinstance(stored, list) else []:
        if not isinstance(row, dict):
            continue
        module = row.get("module")
        if not isinstance(module, str) or module not in known or module in seen:
            continue
        seen.add(module)
        default = known[module]
        size = row.get("size")
        hidden = row.get("hidden")
        rows.append(
            {
                "module": module,
                "size": size if size in SIZES else default["size"],
                "hidden": hidden if isinstance(hidden, bool) else default["hidden"],
                "label": default["label"],
            }
        )
    rows.extend(row for module, row in known.items() if module not in seen)
    return rows


class HomeLayoutService:
    def __init__(self, engine: Engine, user_id: int) -> None:
        self.engine = engine
        self.user_id = user_id

    def shelves(self) -> list[tuple[int, str]]:
        """This person's shelves, `(id, name)`, in the order the shelves page lists them."""
        with self.engine.connect() as connection:
            rows = connection.execute(
                text("SELECT id, name FROM shelves WHERE user_id = :user ORDER BY name, id"),
                {"user": self.user_id},
            ).all()
        return [(shelf_id, name) for shelf_id, name in rows]

    def held(self) -> list[str]:
        """The media this person holds an entry of, the Inbox aside."""
        with self.engine.connect() as connection:
            rows = connection.execute(
                text(
                    "SELECT DISTINCT i.type FROM entries e JOIN items i ON i.id = e.item_id"
                    " WHERE e.user_id = :user AND e.status != 'unsorted'"
                ),
                {"user": self.user_id},
            ).all()
        return [item_type for (item_type,) in rows]

    def defaults(self) -> list[LabelledLayout]:
        return defaults(self.shelves(), self.held())

    def read(self) -> list[LabelledLayout]:
        with self.engine.connect() as connection:
            stored = connection.execute(
                text("SELECT layout_json FROM home_layouts WHERE user_id = :user"),
                {"user": self.user_id},
            ).scalar()
        shelves = self.shelves()
        held = self.held()
        if stored is None:
            return defaults(shelves, held)
        try:
            return normalize(json.loads(stored), shelves, held)
        except ValueError:
            return defaults(shelves, held)

    def hidden(self) -> set[str]:
        return {row["module"] for row in self.read() if row["hidden"]}

    def knows(self, module: str) -> bool:
        """Whether `module` is something this person can place."""
        return any(row["module"] == module for row in self.defaults())

    def all(self) -> set[str]:
        return {row["module"] for row in self.defaults()}

    def write(self, modules: list[dict[str, Any]]) -> list[LabelledLayout]:
        shelves = self.shelves()
        held = self.held()
        known = {row["module"] for row in defaults(shelves, held)}
        seen: set[str] = set()
        for row in modules:
            module = row.get("module")
            if module not in known:
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
        layout = normalize(modules, shelves, held)
        stored = [
            {"module": row["module"], "size": row["size"], "hidden": row["hidden"]}
            for row in layout
        ]
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO home_layouts (user_id, layout_json, updated_at)"
                    " VALUES (:user, :layout, :now)"
                    " ON CONFLICT (user_id) DO UPDATE SET layout_json = excluded.layout_json,"
                    " updated_at = excluded.updated_at"
                ),
                {"user": self.user_id, "layout": json.dumps(stored), "now": _now()},
            )
        return layout
