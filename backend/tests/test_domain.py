import pytest

from book_tracker.domain.identity import InvalidIdentifier, normalize_identifier
from book_tracker.domain.matching import MatchKind, decide_match
from book_tracker.domain.merge import fill_empty
from book_tracker.domain.normalization import normalize_text


@pytest.mark.parametrize(
    ("value", "canonical"),
    [("0-306-40615-2", "9780306406157"), ("978-0-306-40615-7", "9780306406157")],
)
def test_isbn_normalizes_to_canonical_isbn13(value: str, canonical: str) -> None:
    assert normalize_identifier("isbn", value).normalized_value == canonical


def test_invalid_isbn_is_rejected() -> None:
    with pytest.raises(InvalidIdentifier):
        normalize_identifier("isbn", "9780306406158")


def test_text_normalization_is_accent_and_punctuation_insensitive() -> None:
    assert normalize_text("  Cien años—de SOLEDAD! ") == "cien anos de soledad"


def test_title_author_match_is_ambiguity_only() -> None:
    decision = decide_match(exact_item_ids=set(), title_author_item_ids={3})
    assert decision.kind is MatchKind.AMBIGUOUS
    assert decision.item_id is None
    assert decision.candidates == (3,)


def test_fill_empty_preserves_non_empty_values() -> None:
    assert fill_empty(
        {"title": "Existing", "subtitle": "", "metadata": {"authors": ["A"]}},
        {"title": "Incoming", "subtitle": "Filled", "metadata": {"authors": ["B"]}},
    ) == {"title": "Existing", "subtitle": "Filled", "metadata": {"authors": ["A"]}}
