"""One log line per refusal at the boundary (Sprint 129).

Guessing, lockouts, setup-code attempts and cross-site requests each leave a
JSON line with `category: "security"`, the event name, the client address the
limiter used and, where there is one, the username tried. Never a password,
a setup code or a token: the callers pass only the fields below. An operator
filters on the category to alert, or to feed fail2ban.
"""

from __future__ import annotations

import logging

_LOGGER = logging.getLogger("book_tracker.security")


def security_event(
    event: str, *, client: str, level: int = logging.WARNING, **fields: object
) -> None:
    _LOGGER.log(level, event, extra={"category": "security", "client": client, **fields})
