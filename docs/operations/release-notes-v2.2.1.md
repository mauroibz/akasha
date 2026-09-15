# Akasha v2.2.1 — release notes

**The list importer gets comfortable.** v2.2.1 is the owner's own validation
feedback on v2.2, shipped as four usability improvements to the custom list:

- **Type your list, or paste it.** A text editor sits beside the file input:
  drop a file and it fills the editor so you can check what you uploaded and
  fix it inline, or just type three rows and hit Preview with no file at all.
- **The creators column is optional.** A checkbox — "No creators column" —
  opts the list out of reading authors or artists, on any library: most
  searches work fine by title, and for some libraries a "creator" is hard to
  define. Unchecked, everything works exactly as before.
- **Custom list is the first importer.** A hand-written list is the source
  you always have; the platform exports follow it.
- **Every importer names its library.** A small badge on each tab —
  "Any library" for the custom list, "Book" for Goodreads and Calibre —
  rendered from each connector's own declaration.

Two defects found by the live check are fixed too: the importer strip could
scroll its first tab out of reach once the badges widened it, and visiting
the import screen no longer auto-scrolls.

**Tagged `v2.2.1`.** Patch release: no breaking change, no owner action, no
migration.

## Upgrade

```bash
docker compose pull && docker compose up -d
```

If you pin in `.env`, move the pin to `AKASHA_VERSION=2.2.1` (or track the
`2.2` line).
