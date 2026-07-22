import re
import unicodedata


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
