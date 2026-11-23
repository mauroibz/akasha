"""Your media (Sprint 143, DEC-193): the person's own order, and what each medium is to them.

An ordered list of `{item_type, presence}` per person. `front` media feed the front of
the Library (what is under way, what happened lately, what is next, the greeting);
`kept` media are in the library, its choosers and the bar, and stay out of the front;
`off` media are shown nowhere, and nothing of them is deleted or hidden from a direct
link, an export or an import.

Which media exist is the registry's to say. A stored list is read leniently: a medium
no longer registered is dropped, and one the list does not name is appended, `kept`
when the person holds an entry of it and `off` when not. Until a person chooses, the
media they hold are in front and the rest are off, so an empty medium they never used
is not shown; someone who holds nothing yet sees every medium, because nothing can be
ruled out for them. A write is strict: an unregistered medium, or one named twice, is
refused. No rule here names a medium (technical spec 6.6).
"""

import json
from datetime import UTC, datetime
from typing import Any, Literal, TypedDict

from sqlalchemy import text
from sqlalchemy.engine import Engine

from book_tracker.application.library import LibraryError
from book_tracker.domain.registry import DOMAINS

Presence = Literal["front", "kept", "off"]
PRESENCES: tuple[Presence, ...] = ("front", "kept", "off")
#: What an import left unsorted is not yet held (technical spec 6.6).
UNSORTED = "unsorted"


class Medium(TypedDict):
    item_type: str
    #: The domain's plural label, for the control that lists them.
    label: str
    presence: Presence
    #: Whether the person holds an entry of it, the Inbox aside.
    held: bool


class MediaError(LibraryError):
    """A refused list, in the shared error envelope."""


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def arrange(stored: object, held: set[str]) -> list[Medium]:
    """Every registered medium once: the stored ones in their order, then the rest."""
    rows: list[Medium] = []
    seen: set[str] = set()

    def add(item_type: str, presence: Presence) -> None:
        seen.add(item_type)
        rows.append(
            Medium(
                item_type=item_type,
                label=DOMAINS[item_type].plural_label,
                presence=presence,
                held=item_type in held,
            )
        )

    chosen = isinstance(stored, list)
    for row in stored if isinstance(stored, list) else []:
        if not isinstance(row, dict):
            continue
        item_type, presence = row.get("item_type"), row.get("presence")
        if item_type in DOMAINS and item_type not in seen and presence in PRESENCES:
            add(item_type, presence)
    for item_type in DOMAINS:
        if item_type in seen:
            continue
        if chosen:
            add(item_type, "kept" if item_type in held else "off")
        else:
            # No choice yet: what is held is in front; with nothing held, everything.
            add(item_type, "front" if item_type in held or not held else "off")
    return rows


class MediaService:
    def __init__(self, engine: Engine, user_id: int) -> None:
        self.engine = engine
        self.user_id = user_id

    def held(self) -> set[str]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                text(
                    "SELECT DISTINCT i.type FROM entries e JOIN items i ON i.id = e.item_id"
                    " WHERE e.user_id = :user AND e.status != :unsorted"
                ),
                {"user": self.user_id, "unsorted": UNSORTED},
            ).all()
        return {item_type for (item_type,) in rows}

    def _stored(self) -> object:
        with self.engine.connect() as connection:
            stored = connection.execute(
                text("SELECT media_json FROM media_preferences WHERE user_id = :user"),
                {"user": self.user_id},
            ).scalar()
        if stored is None:
            return None
        try:
            parsed = json.loads(stored)
        except ValueError:
            return None
        return parsed if isinstance(parsed, list) else None

    def read(self) -> dict[str, Any]:
        stored = self._stored()
        return {"media": arrange(stored, self.held()), "chosen": stored is not None}

    def front(self) -> set[str]:
        """The media that feed the front of the Library."""
        return {row["item_type"] for row in self.read()["media"] if row["presence"] == "front"}

    def write(self, media: list[dict[str, Any]]) -> dict[str, Any]:
        seen: set[str] = set()
        for row in media:
            item_type = row.get("item_type")
            if item_type not in DOMAINS:
                raise MediaError(
                    "unknown_medium",
                    "Akasha has no medium by that name",
                    status_code=422,
                    details={"item_type": item_type},
                )
            if item_type in seen:
                raise MediaError(
                    "duplicate_medium",
                    "Name each medium once",
                    status_code=422,
                    details={"item_type": item_type},
                )
            seen.add(item_type)
        # Stored whole, so what was appended keeps the place the person saw it in.
        whole = [
            {"item_type": row["item_type"], "presence": row["presence"]}
            for row in arrange(media, self.held())
        ]
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO media_preferences (user_id, media_json, updated_at)"
                    " VALUES (:user, :media, :now)"
                    " ON CONFLICT (user_id) DO UPDATE SET media_json = excluded.media_json,"
                    " updated_at = excluded.updated_at"
                ),
                {"user": self.user_id, "media": json.dumps(whole), "now": _now()},
            )
        return self.read()
