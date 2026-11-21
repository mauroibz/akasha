"""The one boundary that decides who a request belongs to."""

import ipaddress
from dataclasses import dataclass
from datetime import timedelta
from typing import Annotated

from fastapi import Depends, Request

from book_tracker.application.library import LibraryError
from book_tracker.application.sessions import SESSION_COOKIE_NAME, SESSION_LIFETIME, SessionStore

__all__ = [
    "Principal",
    "current_user",
    "CurrentUser",
    "AdminUser",
    "SECURE_SESSION_COOKIE_NAME",
    "client_address",
    "peer_is_trusted",
    "request_path",
    "request_uses_https",
    "session_cookie_name",
    "session_store",
    "session_token",
]

#: The cookie's name when it is `Secure` (Sprint 128, F12). The `__Host-` prefix
#: makes the browser refuse one set with a `Domain` or from plain HTTP, so a
#: sibling subdomain cannot plant a session of its own choosing.
SECURE_SESSION_COOKIE_NAME = "__Host-akasha_session"


def request_path(request: Request) -> str:
    """The path the router dispatches on.

    Never `request.url.path`: Starlette builds that URL from the `Host` header,
    so `Host: x/api/health/?` made a protected route look public (F2).
    """
    return str(request.scope.get("path", ""))


def peer_is_trusted(request: Request, configured_peers: list[str]) -> bool:
    if request.client is None:
        return False
    try:
        peer = ipaddress.ip_address(request.client.host)
    except ValueError:
        return False
    for configured in configured_peers:
        try:
            if peer in ipaddress.ip_network(configured, strict=False):
                return True
        except ValueError:
            continue
    return False


def client_address(request: Request) -> str:
    """The address a request comes from, for rate limiting.

    The configured header (`CF-Connecting-IP`) is believed only from a trusted
    peer and only when it holds an IP address; anything else falls back to the
    socket peer, so a direct caller cannot rotate a forged value for fresh
    buckets. uvicorn's `--forwarded-allow-ips` is never relied on.
    """
    peer = request.client.host if request.client is not None else "unknown"
    header = getattr(request.app.state, "client_ip_header", None)
    if not header:
        return peer
    if not peer_is_trusted(request, getattr(request.app.state, "trusted_proxy_peers", [])):
        return peer
    asserted = request.headers.get(header, "").split(",", 1)[0].strip()
    try:
        return str(ipaddress.ip_address(asserted))
    except ValueError:
        return peer


def request_uses_https(request: Request) -> bool:
    override = getattr(request.app.state, "cookie_secure", None)
    if override is not None:
        return bool(override)
    scheme = str(request.scope.get("scheme", "http"))
    forwarded = request.headers.get("x-forwarded-proto")
    if forwarded and peer_is_trusted(
        request, getattr(request.app.state, "trusted_proxy_peers", [])
    ):
        scheme = forwarded.split(",", 1)[0].strip().casefold()
    return scheme == "https"


def session_cookie_name(request: Request) -> str:
    """`__Host-akasha_session` when Secure, the old name on plain HTTP."""
    return SECURE_SESSION_COOKIE_NAME if request_uses_https(request) else SESSION_COOKIE_NAME


def session_token(request: Request) -> str | None:
    """The session token this request presents under the name it is allowed.

    On a Secure deployment only the `__Host-` cookie counts: a legacy-named one
    may have been planted with `Domain=` by a sibling subdomain. On plain HTTP
    the legacy name is the only one a browser can hold.
    """
    return request.cookies.get(session_cookie_name(request)) or None


def session_store(request: Request) -> SessionStore:
    lifetime = getattr(request.app.state, "session_lifetime", SESSION_LIFETIME)
    return SessionStore(
        request.app.state.engine,
        lifetime=lifetime if isinstance(lifetime, timedelta) else SESSION_LIFETIME,
    )


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
    token = session_token(request)
    identity = session_store(request).lookup(token) if token else None
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
