"""Who a request belongs to.

Sprint 076 (DEC-146): v1 has no authentication, but every ledger row written
since Sprint 075 has an owner column that Sprint 075 filled with the seeded
user by server default. Past that sprint the code kept deciding "this row
belongs to user 1" in two dozen places the request never reached — a
single-user assumption smuggled through constructor defaults. This module is
the only one allowed to make that decision: a FastAPI dependency that names
the request's owner and carries that name as a value to every service.

`Settings.auth` accepts exactly one value in v1 (`off`; anything else is
refused at startup), so the answer is always the seeded user. Sprint 077
replaces the body with a session lookup and Sprint 080 fills `acting_as`;
neither changes the signature, and callers keep using `effective_user_id` so
they never learn the difference.
"""

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request

__all__ = ["Principal", "current_user", "CurrentUser"]


@dataclass(frozen=True, slots=True)
class Principal:
    """The owner of a request, as a value that travels rather than a lookup.

    `acting_as` is `None` everywhere in v1: impersonation is Sprint 080, and
    everything that needs "whose rows" was written to use `effective_user_id`
    from that day on, so no caller knows when the two start to differ.
    """

    user_id: int
    username: str
    is_admin: bool
    acting_as: int | None = None

    @property
    def effective_user_id(self) -> int:
        """Whose rows this request touches — the attribute callers must use."""
        return self.acting_as if self.acting_as is not None else self.user_id


async def current_user(request: Request) -> Principal:
    """The one place that decides who a request belongs to.

    `app.state.auth` mirrors `Settings.auth`, whose validator admits exactly one
    value in v1 (`off`), so this branch is a constant — the dependency exists
    so Sprint 077 can replace the constant with a session lookup in exactly one
    file instead of discovering another hardcoded user somewhere it cannot see.
    """
    auth = getattr(request.app.state, "auth", "off")
    if auth != "off":
        raise RuntimeError(
            "AKASHA_AUTH must be 'off' in this build — a different value should "
            "have been refused at startup before reaching here"
        )
    # The seeded user, written by Sprint 075's migration and renamed `admin` at
    # DEC-147's cheap path. Sprint 077 turns this line into a session lookup;
    # the dependency's return type is the part that is permanent.
    return Principal(user_id=1, username="admin", is_admin=True, acting_as=None)


CurrentUser = Annotated[Principal, Depends(current_user)]
"""The dependency form for route handlers: `user: CurrentUser`."""