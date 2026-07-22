from enum import StrEnum


class EntryStatus(StrEnum):
    UNSORTED = "unsorted"
    READ = "read"
    READING = "reading"
    TO_READ = "to_read"
    WISHLIST = "wishlist"
    DROPPED = "dropped"


class SourceName(StrEnum):
    OPEN_LIBRARY = "openlibrary"
    GOOGLE_BOOKS = "googlebooks"
    MANUAL = "manual"
