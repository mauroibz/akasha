"""Per-provider daily request budgets.

The persistent sibling of `RateLimiter` in `jobs.py`: that one spaces requests out
within a session, this one bounds how many are spent in a day and survives a restart,
because a counter that resets when the container restarts protects nothing.

Deliberately provider-agnostic (DEC-045). No provider is named here or in the schema —
limits arrive as configuration, so adding a metered provider later is a config entry
rather than a change to this file. A provider with no configured limit is never blocked
but is still counted, so a limit can later be set against observed history rather than
a guess.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

from sqlalchemy import Engine, text


def _day(now: datetime) -> str:
    """The UTC date a request counts against.

    Providers reset on their own timezones — Google Books on Pacific time — so this
    boundary is approximate by design and the limits configured against it are set
    conservatively rather than at the provider's exact ceiling.
    """
    return now.date().isoformat()


class ProviderQuota:
    def __init__(self, engine: Engine, *, limits: Mapping[str, int]) -> None:
        self.engine = engine
        self.limits = dict(limits)

    def used(self, provider: str, now: datetime) -> int:
        with self.engine.connect() as connection:
            return (
                connection.execute(
                    text(
                        "SELECT count FROM provider_usage WHERE provider = :provider AND day = :day"
                    ),
                    {"provider": provider, "day": _day(now)},
                ).scalar()
                or 0
            )

    def allows(self, provider: str, now: datetime) -> bool:
        limit = self.limits.get(provider)
        if limit is None:
            return True
        return self.used(provider, now) < limit

    def record(self, provider: str, now: datetime) -> None:
        """Count one request against a provider, metered or not."""
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO provider_usage (provider, day, count)"
                    " VALUES (:provider, :day, 1)"
                    " ON CONFLICT(provider, day)"
                    " DO UPDATE SET count = count + 1"
                ),
                {"provider": provider, "day": _day(now)},
            )
