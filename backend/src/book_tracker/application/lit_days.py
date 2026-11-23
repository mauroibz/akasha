"""Lit days (Sprint 147, DEC-193): the Journal's *Every day* widget.

A day is lit when something was read, watched or finished on it. Three things light
one: logging progress on an entry, finishing an entry, and a tap by hand, which may
say what the day was for by naming entries, or name none. Nothing here counts a
streak or says a day was missed; an unlit day is only unlit (DEC-169, DEC-171).

A reading is at most `MAX_SPAN` days, a month and the weeks around it: the widget
shows a week or a month, never a year (the owner, 2026-11-23).
"""

import json
from datetime import UTC, date, datetime
from typing import Any, Literal

from sqlalchemy import text
from sqlalchemy.engine import Engine

from book_tracker.application.library import LibraryError, LibraryService

Source = Literal["progress", "finish", "tap"]
SOURCES: tuple[Source, ...] = ("progress", "finish", "tap")
#: The longest reading: a month drawn with the weeks it starts and ends in.
MAX_SPAN = 62


class LitDayError(LibraryError):
    """A refused day, in the shared error envelope."""


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def parse_day(value: str) -> date:
    try:
        day = date.fromisoformat(value)
    except ValueError as error:
        raise LitDayError(
            "invalid_day", "A day is written YYYY-MM-DD", status_code=422, details={"day": value}
        ) from error
    if day.isoformat() != value:
        raise LitDayError(
            "invalid_day", "A day is written YYYY-MM-DD", status_code=422, details={"day": value}
        )
    return day


class LitDayService:
    def __init__(self, engine: Engine, user_id: int, library: LibraryService) -> None:
        self.engine = engine
        self.user_id = user_id
        self.library = library

    def days(self, start: date, end: date) -> list[dict[str, Any]]:
        """Each lit day from `start` to `end`, oldest first, with what it was for."""
        if end < start:
            raise LitDayError("invalid_range", "The range ends before it starts", status_code=422)
        if (end - start).days >= MAX_SPAN:
            raise LitDayError(
                "range_too_long",
                f"At most {MAX_SPAN} days at a time",
                status_code=422,
                details={"max_days": MAX_SPAN},
            )
        with self.engine.connect() as connection:
            rows = connection.execute(
                text(
                    "SELECT day, entry_id FROM lit_days WHERE user_id = :user"
                    " AND day BETWEEN :start AND :end ORDER BY day, id"
                ),
                {"user": self.user_id, "start": start.isoformat(), "end": end.isoformat()},
            ).all()
        ids = list(dict.fromkeys(entry_id for _day, entry_id in rows if entry_id is not None))
        entries = {entry["id"]: entry for entry in self.library.get_entries(ids)}
        days: dict[str, list[dict[str, Any]]] = {}
        for day, entry_id in rows:
            named = days.setdefault(day, [])
            if entry_id is not None and entry_id in entries:
                named.append(entries[entry_id])
        return [{"day": day, "entries": named} for day, named in days.items()]

    def record(self, entry_id: int, day: date, source: Source) -> None:
        """Light `day` for an entry; a day it already lights is left as it was."""
        if source not in SOURCES:
            raise ValueError(f"not a way a day is lit: {source!r}")
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT OR IGNORE INTO lit_days (user_id, day, entry_id, source, created_at)"
                    " VALUES (:user, :day, :entry, :source, :now)"
                ),
                {
                    "user": self.user_id,
                    "day": day.isoformat(),
                    "entry": entry_id,
                    "source": source,
                    "now": _now(),
                },
            )

    def light(self, day: date, entry_ids: list[int], today: date) -> dict[str, Any]:
        """Light a day by hand, for these entries or for nothing in particular.

        Saying it again replaces what the hand said before; what progress and finishes
        lit stays. It changes no entry: this is only the day.
        """
        if day > today:
            raise LitDayError(
                "future_day",
                "A day that has not come cannot be lit",
                status_code=422,
                details={"day": day.isoformat()},
            )
        wanted = list(dict.fromkeys(entry_ids))
        with self.engine.begin() as connection:
            if wanted:
                # Own entries only; another person's is as unknown as one that is not there.
                rows = connection.execute(
                    text(
                        "SELECT id FROM entries WHERE user_id = :user"
                        " AND id IN (SELECT value FROM json_each(:ids))"
                    ),
                    {"user": self.user_id, "ids": _json(wanted)},
                ).all()
                missing = sorted(set(wanted) - {entry_id for (entry_id,) in rows})
                if missing:
                    raise LitDayError(
                        "unknown_entry",
                        "That is not in your library",
                        status_code=422,
                        details={"entry_ids": missing},
                    )
            connection.execute(
                text(
                    "DELETE FROM lit_days WHERE user_id = :user AND day = :day AND source = 'tap'"
                ),
                {"user": self.user_id, "day": day.isoformat()},
            )
            params = {"user": self.user_id, "day": day.isoformat(), "now": _now()}
            if not wanted:
                connection.execute(
                    text(
                        "INSERT OR IGNORE INTO lit_days (user_id, day, entry_id, source,"
                        " created_at) VALUES (:user, :day, NULL, 'tap', :now)"
                    ),
                    params,
                )
            for entry_id in wanted:
                connection.execute(
                    text(
                        "INSERT OR IGNORE INTO lit_days (user_id, day, entry_id, source,"
                        " created_at) VALUES (:user, :day, :entry, 'tap', :now)"
                    ),
                    {**params, "entry": entry_id},
                )
        lit = self.days(day, day)
        return lit[0] if lit else {"day": day.isoformat(), "entries": []}

    def unlight(self, day: date) -> None:
        """Take everything off a day, however it came to be lit."""
        with self.engine.begin() as connection:
            connection.execute(
                text("DELETE FROM lit_days WHERE user_id = :user AND day = :day"),
                {"user": self.user_id, "day": day.isoformat()},
            )


def _json(values: list[int]) -> str:
    return json.dumps(values)
