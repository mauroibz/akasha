"""Reading a source's fingerprint from its first bytes (Sprint 095, proposal §5.2).

Shared helpers for `SniffingImporter.sniff`: every one of them works on a truncated
head (64 KiB) and never raises, because a file that cannot be read is simply not this
connector's. A zip's central directory sits at its end, but every member is preceded
by a local header carrying its name, so the names of a small export's members are all
in its first bytes.
"""

from __future__ import annotations

import csv
import io
import re
import zlib

SNIFF_BYTES = 64 * 1024

_LOCAL_HEADER = b"PK\x03\x04"


def zip_member_names(head: bytes) -> list[str]:
    """The member names whose local headers fall inside `head`."""
    names: list[str] = []
    offset = head.find(_LOCAL_HEADER)
    while offset >= 0 and offset + 30 <= len(head):
        name_length = int.from_bytes(head[offset + 26 : offset + 28], "little")
        start = offset + 30
        raw = head[start : start + name_length]
        if len(raw) == name_length:
            names.append(raw.decode("utf-8", "replace"))
        offset = head.find(_LOCAL_HEADER, start + name_length)
    return names


def is_zip(head: bytes) -> bool:
    return head.startswith(_LOCAL_HEADER)


def is_epub(head: bytes) -> bool:
    """An EPUB's first member is an uncompressed `mimetype` saying so (OCF 3.0 §4.3)."""
    return is_zip(head) and head[30:38] == b"mimetype" and b"application/epub+zip" in head[:128]


def text_of(head: bytes) -> str:
    """The head as text: gunzipped when it is gzip, decoded leniently either way."""
    if head[:2] == b"\x1f\x8b":
        # Never more than the sniff window out: 64 KiB of gzip can inflate to tens of
        # megabytes, and only the head is ever looked at (F14).
        try:
            head = zlib.decompressobj(16 + zlib.MAX_WBITS).decompress(head, SNIFF_BYTES)
        except zlib.error:
            return ""
    if b"\x00" in head[:1024]:
        return ""
    return head.decode("utf-8-sig", "replace")


def csv_header(head: bytes) -> list[str] | None:
    """The first row of a delimited text file, or `None` when it is not one."""
    text = text_of(head)
    first = text.split("\n", 1)[0].strip("\r")
    if not first:
        return None
    try:
        row = next(csv.reader(io.StringIO(first), delimiter=_header_delimiter(first)), None)
    except csv.Error:
        return None
    return [cell.strip() for cell in row] if row else None


def _header_delimiter(line: str) -> str:
    """Comma, semicolon or tab — whichever the header holds most of outside quotes.

    One linear pass. `csv.Sniffer` did the same job with regexes that are quadratic
    on a crafted 64 KiB line, about 40 s of CPU holding the GIL (F14).
    """
    counts = {",": 0, ";": 0, "\t": 0}
    quoted = False
    for character in line:
        if character == '"':
            quoted = not quoted
        elif not quoted and character in counts:
            counts[character] += 1
    best = max(counts, key=lambda key: counts[key])
    return best if counts[best] > 0 else ","


_ELEMENT_NAME = re.compile(r"[A-Za-z_][\w.-]*")


def xml_root(head: bytes) -> str | None:
    """The first element's name, skipping the declaration, comments and doctype.

    A forward scan that never revisits a byte: the regex substitution it replaces was
    quadratic on a run of unclosed `<!` (F14). An unclosed prolog construct means the
    head holds no element yet, so it answers `None`.
    """
    text = text_of(head)
    position = text.find("<")
    while position >= 0:
        following = text[position + 1 : position + 2]
        if following in ("?", "!"):
            closer = "-->" if text.startswith("<!--", position) else ">"
            end = text.find(closer, position + 2)
            if end < 0:
                return None
            position = text.find("<", end + len(closer))
            continue
        match = _ELEMENT_NAME.match(text, position + 1)
        if match:
            return match.group(0)
        position = text.find("<", position + 1)
    return None
