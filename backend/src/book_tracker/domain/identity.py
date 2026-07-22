from dataclasses import dataclass


class InvalidIdentifier(ValueError):
    """Raised when an authoritative identifier is malformed."""


@dataclass(frozen=True)
class Identifier:
    kind: str
    normalized_value: str
    value: str


def _isbn10_valid(value: str) -> bool:
    return (
        len(value) == 10
        and all(c.isdigit() for c in value[:9])
        and (value[9].isdigit() or value[9] == "X")
        and sum((10 - index) * (10 if c == "X" else int(c)) for index, c in enumerate(value)) % 11
        == 0
    )


def _isbn13_valid(value: str) -> bool:
    return (
        len(value) == 13
        and value.isdigit()
        and sum(int(c) * (1 if index % 2 == 0 else 3) for index, c in enumerate(value)) % 10 == 0
    )


def _isbn10_to_13(value: str) -> str:
    prefix = f"978{value[:9]}"
    check = (10 - sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(prefix)) % 10) % 10
    return f"{prefix}{check}"


def normalize_identifier(kind: str, value: str) -> Identifier:
    original = value
    normalized_kind = kind.strip().casefold()
    if normalized_kind in {"isbn", "isbn10", "isbn13"}:
        armored = "".join(c for c in value.upper() if c.isdigit() or c == "X")
        if _isbn10_valid(armored):
            armored = _isbn10_to_13(armored)
        elif not _isbn13_valid(armored):
            raise InvalidIdentifier("invalid ISBN checksum")
        return Identifier("isbn", armored, original)
    cleaned = value.strip()
    if not normalized_kind or not cleaned:
        raise InvalidIdentifier("identifier kind and value are required")
    return Identifier(normalized_kind, cleaned, original)
