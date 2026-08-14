import re
import unicodedata
from html import unescape
from html.parser import HTMLParser


def normalize_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    unaccented = "".join(c for c in decomposed if not unicodedata.combining(c))
    words = re.sub(r"[^\w]+", " ", unaccented.casefold(), flags=re.UNICODE)
    return " ".join(words.split())


def shelf_slug(value: str) -> str:
    slug = normalize_text(value).replace("_", " ").replace(" ", "-")
    if not slug:
        raise ValueError("shelf name must contain letters or numbers")
    return slug


class _TextExtractor(HTMLParser):
    """Collect visible text, turning block-level tags into paragraph breaks."""

    # Tags whose boundaries are a break in the prose rather than a word boundary.
    _BREAKS = {"p", "br", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"}
    # Tags whose *content* is not prose at all and must not survive as text.
    _SILENT = {"script", "style"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._muted = 0

    def handle_starttag(self, tag: str, attrs: object) -> None:
        if tag in self._SILENT:
            self._muted += 1
        elif tag in self._BREAKS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SILENT:
            self._muted = max(0, self._muted - 1)
        elif tag in self._BREAKS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._muted:
            self.parts.append(data)


def strip_html(value: str) -> str:
    """Reduce a provider description to plain text.

    Google Books and Open Library both return descriptions containing markup —
    `<p>To stay competitive...`, `<p> <b>` — and the detail page escapes what it
    renders, so the tags showed up as literal text. Stripping at the provider
    boundary keeps the stored value the plain prose the UI has always assumed.

    Not a sanitiser and not a security control: nothing downstream renders this as
    HTML. It is a display fix, so it errs towards keeping the text.
    """
    if not value or "<" not in value:
        # `unescape` still matters: a description can carry `&amp;` with no tags.
        return unescape(value).strip()
    parser = _TextExtractor()
    try:
        parser.feed(value)
        parser.close()
    except Exception:
        # Malformed markup should degrade to the original text, never lose it.
        return unescape(value).strip()
    text = "".join(parser.parts)
    # Collapse runs of whitespace inside a line, then runs of blank lines, so the
    # result reads as paragraphs rather than as one wall or a column of gaps.
    lines = [re.sub(r"[^\S\n]+", " ", line).strip() for line in text.split("\n")]
    return "\n\n".join(line for line in lines if line).strip()
