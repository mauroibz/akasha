"""Versioned standard-library password hashing (DEC-146, Sprint 077)."""

from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ScryptParameters:
    """The cost stored with each digest so defaults can rise independently."""

    n: int = 2**14
    r: int = 8
    p: int = 1
    dklen: int = 32


@dataclass(frozen=True, slots=True)
class PasswordHash:
    digest: str
    salt: str


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def hash_password(
    password: str, *, parameters: ScryptParameters = ScryptParameters()
) -> PasswordHash:
    """Hash one password with a fresh salt and a self-describing digest."""
    salt = secrets.token_bytes(16)
    derived = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=parameters.n,
        r=parameters.r,
        p=parameters.p,
        dklen=parameters.dklen,
    )
    encoded = (
        "scrypt$"
        f"n={parameters.n}$r={parameters.r}$p={parameters.p}$dklen={parameters.dklen}$"
        f"{_encode(derived)}"
    )
    return PasswordHash(digest=encoded, salt=_encode(salt))


def verify_password(password: str, encoded_digest: str, encoded_salt: str) -> bool:
    """Verify using the cost in the stored digest and constant-time comparison."""
    try:
        algorithm, n, r, p, dklen, expected = encoded_digest.split("$")
        if algorithm != "scrypt":
            return False
        parameters = ScryptParameters(
            n=int(n.removeprefix("n=")),
            r=int(r.removeprefix("r=")),
            p=int(p.removeprefix("p=")),
            dklen=int(dklen.removeprefix("dklen=")),
        )
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=_decode(encoded_salt),
            n=parameters.n,
            r=parameters.r,
            p=parameters.p,
            dklen=parameters.dklen,
        )
        return secrets.compare_digest(actual, _decode(expected))
    except (ValueError, TypeError):
        return False

