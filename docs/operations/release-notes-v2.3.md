# Akasha v2.3.0 — release notes

**Drop ebook files on Add.** Open Akasha, click **Add**, and drag EPUB files onto the new
*Ebook files* box. Each one becomes a book:

- **Read from the file itself.** Title, authors, ISBN, publisher, language, year, description,
  subjects and series come from the EPUB's own metadata, and its cover becomes the book's cover.
  Nothing is typed and no provider search is needed.
- **The file is attached.** The EPUB is stored on the book, downloadable from its page, exactly
  as if you had attached it by hand.
- **Straight to Triage.** The drop opens the import preview already filled in; one click commits,
  and the books wait in Triage for you to sort. A book you already have (same ISBN) is matched
  rather than duplicated, and dropping the same files again replays the earlier import.
- **One bad file costs one row.** A file that isn't a readable EPUB shows as an error on its own
  row; the rest still import.
- **Enrichment fills the gaps.** A book whose EPUB carries an ISBN is enriched from Open Library
  in the background, filling empty fields only — what the file said is kept.

Also fixed: import previews from Goodreads, Calibre and the new connector no longer tell every
row "No results. Fix the text and search again" — that message belongs to the custom list's
search, and now only appears there.

**Tagged `v2.3.0`.** Minor release: no breaking change, no migration, no owner action.

## Upgrade

```bash
docker compose pull && docker compose up -d
```

If you pin in `.env`, move the pin to `AKASHA_VERSION=2.3.0` (or track the `2.3` line).
