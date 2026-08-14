import re
import unicodedata
from html import unescape
from html.parser import HTMLParser


def normalize_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    unaccented = "".join(c for c in decomposed if not unicodedata.combining(c))
    words = re.sub(r"[^\w]+", " ", unaccented.casefold(), flags=re.UNICODE)
    return " ".join(words.split())


# A single word character followed by a period: "K.", "J.", the pieces of "J. R. R.".
_INITIAL = re.compile(r"^\w\.$", re.UNICODE)


def creator_sort_name(name: str) -> str:
    """Guess the form a creator's name sorts under: `García Márquez, Gabriel`.

    Deliberately biased towards the Spanish double surname, because that is the
    library this serves. Everything after the first token is the surname, so
    "Gabriel García Márquez" and "Adolfo Bioy Casares" both come out right where a
    last-space split would file them under Márquez and Casares. The cost is
    "John Ronald Reuel Tolkien", which comes out as "Ronald Reuel Tolkien, John".

    That is why this is a *seed*. The value it produces is stored, not recomputed
    on read, and the owner can overwrite any of it; a Calibre import supplies a
    curated sort name instead and never consults this function. Tuning the
    heuristic further is not the answer to a wrong name — correcting the row is.

    An initial stays with the given name ("Ursula K. Le Guin" -> "Le Guin, Ursula
    K."), and a name that already carries a comma is left alone: Calibre and
    Goodreads both emit the inverted form, and inverting it again would produce
    "Gabriel, García Márquez".
    """
    if "," in name:
        return " ".join(name.split())
    tokens = name.split()
    if len(tokens) < 2:
        return " ".join(tokens)
    given, rest = [tokens[0]], tokens[1:]
    while rest and _INITIAL.match(rest[0]):
        given.append(rest.pop(0))
    if not rest:
        # Nothing but a first name and initials; there is no surname to move.
        return " ".join(given)
    return f"{' '.join(rest)}, {' '.join(given)}"


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
