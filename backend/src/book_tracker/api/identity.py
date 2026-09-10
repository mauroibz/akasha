"""The one boundary that decides who a request belongs to."""

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request

from book_tracker.application.library import LibraryError
from book_tracker.application.sessions import SESSION_COOKIE_NAME, SessionStore

__all__ = ["Principal", "current_user", "CurrentUser", "AdminUser"]


@dataclass(frozen=True, slots=True)
class Principal:
    """The owner of a request, as a value that travels rather than a lookup.

    The signed-in identity stays in `user_id`; `acting_as` names whose rows an
    admin deliberately opened. Callers use `effective_user_id`, so none needs
    an impersonation branch of its own.
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

    Auth-off preserves the seeded implicit user. Auth-on reads only the opaque
    cookie and the server-side session it names; every downstream caller keeps
    receiving the same value type Sprint 076 introduced.
    """
    auth = getattr(request.app.state, "auth", "off")
    if auth == "off":
        return Principal(user_id=1, username="admin", is_admin=True, acting_as=None)
    principal = getattr(request.state, "principal", None)
    if isinstance(principal, Principal):
        return principal
    token = request.cookies.get(SESSION_COOKIE_NAME)
    identity = SessionStore(request.app.state.engine).lookup(token) if token else None
    if identity is None:
        raise AuthenticationRequired
    return Principal(
        user_id=identity.user_id,
        username=identity.username,
        is_admin=identity.is_admin,
        acting_as=identity.acting_as_user_id,
    )


class AuthenticationRequired(Exception):
    """Raised only if a protected dependency is reached without middleware state."""


CurrentUser = Annotated[Principal, Depends(current_user)]
"""The dependency form for route handlers: `user: CurrentUser`."""


async def require_admin(user: CurrentUser) -> Principal:
    """Refuse account administration without revealing anything about a target."""
    if not user.is_admin:
        raise LibraryError("forbidden", "Administrator access is required", status_code=403)
    return user


AdminUser = Annotated[Principal, Depends(require_admin)]
"""The dependency used only by user-management routes."""
