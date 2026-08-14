# Recorded provider responses

These files are verbatim responses captured from the live providers. They exist because
DEC-025 forbids proving provider-boundary behaviour with a mock of the method under
test: the Open Library enrichment defect survived thirteen sprints behind an `AsyncMock`
of the exact broken method.

**Never re-record silently.** A fixture is a pinned observation of an external contract.
If a provider changes shape, re-record deliberately, in its own commit, and say so in the
sprint outcome — otherwise a regression test quietly starts asserting the new bug.

Captured 2026-08-09 with `User-Agent: Akasha/0.1 (<contact address>)`, the value
`USER_AGENT_CONTACT` supplies at runtime, except where a row states a different date.

One file was **added** on 2026-08-13 (`googlebooks_isbn_9780307474728.json`). Nothing was
re-recorded: the Sprint 020 verification work found that
`googlebooks_isbn_9788437604572.json` already demonstrated the defect it needed to prove,
and a live check that day returned the same volume.

| File | Source |
|---|---|
| `isbn_9788437604572.headers` | `GET https://openlibrary.org/isbn/9788437604572.json` — response headers only. Status **302**, `Location: https://openlibrary.org/books/OL19845805M.json`. The same ISBN against `https://openlibrary.org/books/9788437604572.json` returns **404**: that endpoint takes an OLID, and requesting it with an ISBN is the defect Sprint 014 repaired. |
| `edition_OL19845805M.json` | `GET https://openlibrary.org/books/OL19845805M.json` — the edition the redirect above resolves to (Rayuela, Cátedra, 1984). |
| `author_OL2631008A.json` | `GET https://openlibrary.org/authors/OL2631008A.json` |
| `work_OL14860424W.json` | `GET https://openlibrary.org/works/OL14860424W.json` |
| `search_rayuela.json` | `GET https://openlibrary.org/search.json?q=Rayuela+Cortázar&limit=20&fields=…` — 20 real results whose intended edition (`OL47684105M`, rank 0 from the provider) sorts late alphabetically. |
| `search_don_quijote.json` | `GET https://openlibrary.org/search.json?q=Don+Quijote+de+la+Mancha&limit=20&fields=…` — results 7 and 14 carry no edition publish date, so they exercise year resolution beyond the first row. |
| `editions_OL17741305W.json` | `GET https://openlibrary.org/works/OL17741305W/editions.json?limit=20` — empty; the work behind result 7, which genuinely has no datable edition. |
| `editions_OL34762840W.json` | `GET https://openlibrary.org/works/OL34762840W/editions.json?limit=20` — the work behind result 14. Its publish dates are `"Mar 09, 2005"`-style, which the original four-character year parser could not read. |
| `googlebooks_isbn_9788437604572.json` | `GET https://www.googleapis.com/books/v1/volumes?q=isbn:9788437604572&maxResults=1&key=…` — the Google Books fallback answer for the same book. The API key is a query parameter and appears nowhere in the response. |
| `googlebooks_isbn_9789994444441_empty.json` | The same endpoint for an ISBN Google Books does not index: `totalItems: 0`, no `items` key. |
| `editions_OL14860424W.json` | `GET https://openlibrary.org/works/OL14860424W/editions.json?limit=20` — captured **2026-08-13**, for Sprint 020 Phase B. The work behind `edition_OL19845805M.json`, so the two compose into the whole cover-candidate path: edition to work to editions. Its `size` is **129** and all 20 returned entries carry a cover, which is the measurement DEC-044 rests on. The entries are deliberately not all Spanish — Italian, French, Turkish, Persian and Finnish editions appear — because that is what a work's editions really look like. |
| `googlebooks_isbn_9780307474728.json` | `GET https://www.googleapis.com/books/v1/volumes?q=isbn:9780307474728&maxResults=1&key=…` — captured **2026-08-13**, for Sprint 020. The counterpart to the row above: this volume *does* carry the requested ISBN13 in `industryIdentifiers`, so it is the confirmed case. It exists so the edition-verification repair can be shown to still admit a verified candidate rather than merely disabling the Google Books fallback. |

The `fields` parameter used for both search recordings is the one
`OpenLibraryProvider.search` sends; it is reproduced in the test that replays them.
