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

Two files were **re-recorded** on 2026-08-15 for Sprint 026: the two
`musicbrainz_release_kind_of_blue*` rows. This is the deliberate re-record the rule
above describes — the adapter's request itself changed, since a tracklist is one extra
`inc=…+recordings` parameter, so the old captures pinned a request the code no longer
makes. Verified before replacing them: apart from the new `media[].tracks` array and
the `track-offset` key that arrives with it, **every field is byte-identical to the
2026-08-14 capture**, so no regression test silently started asserting new data.
MusicBrainz answered one **`503`** during the run again, and the retry after five
seconds succeeded.

Thirteen files were **added** on 2026-08-14 for Sprint 025 (the `musicbrainz_*`,
`coverartarchive_*` and `archive_org_*` rows below), captured with
`User-Agent: Akasha/1.1 (+https://github.com/mauroibz/akasha)` and paced at ~1.2 s
between requests. MusicBrainz answered one **`503`** during the run, which is how it
signals throttling — it does not use `429`. Nothing else was re-recorded.

Two files were **added** on 2026-08-20 for Sprint 030 (the `*_20260820` rows below),
captured with `User-Agent: Akasha/1.2 (+<contact address>)`. They are the sprint's
**control measurement**: MusicBrainz was already measured in Sprint 026, so the
question here is whether the finding still holds against the live API today. It does —
the two 2026-08-15 captures were re-requested verbatim and the tracklist the
`recordings` parameter returns is identical, row for row, in `(number, title, length,
recording.id)`. MusicBrainz answered one **`503`** during this run too; the retry
after five seconds succeeded, which is three-for-three on that throttling shape.

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

| `musicbrainz_search_kind_of_blue.json` | `GET https://musicbrainz.org/ws/2/release-group?query=Kind of Blue AND artist:Miles Davis&fmt=json&limit=10` — captured **2026-08-14**. The album search path. The intended release group scores 100 and the next two are compilations that contain it, which is what album search noise really looks like. |
| `musicbrainz_release_group_kind_of_blue.json` | `GET https://musicbrainz.org/ws/2/release-group/8e8a594f-2175-38c7-a871-abb68ec363e7?inc=releases+artist-credits&fmt=json` — captured **2026-08-14**. **25 releases in one group**, which is the release-group ≈ work, release ≈ edition observation DEC-052 rests on. |
| `musicbrainz_release_kind_of_blue.json` | `GET https://musicbrainz.org/ws/2/release/bee5e0cd-1767-4a8e-9578-6455e87ba60b?inc=artist-credits+labels+media+release-groups+recordings&fmt=json` — re-recorded **2026-08-15** with `recordings` added. One full release: `label-info` is `("CS 8163", "Columbia")` — the publisher analogue — `media` is `12" Vinyl` with 5 tracks, `text-representation` carries the language, and **`barcode` is empty**, which is why a 1959 release cannot be keyed on one. The tracklist costs **6.5 KB and no extra request**, and each track carries **both** a sequential `position` and a printed `number` — `A1`, `A2` on a record — which are different strings and the second is the one on the sleeve. |
| `musicbrainz_release_kind_of_blue_mono.json` | `GET https://musicbrainz.org/ws/2/release/79ed3ff2-1b33-3245-8755-947554bc8b3d?inc=artist-credits+labels+media+release-groups+recordings&fmt=json` — re-recorded **2026-08-15** with `recordings` added. The mono pressing of the same day, catalogue number `CL 1355` against the stereo's `CS 8163`. Two official releases share the group's `first-release-date`, which is why the adapter needs a stable tiebreak; this is the one it settles on, and `barcode` is `null` here rather than empty. |
| `musicbrainz_artist_person_miles_davis.json` | `GET https://musicbrainz.org/ws/2/artist/561d854a-6a28-4aa7-8c99-323e6ce46c2a?fmt=json` — captured **2026-08-14**. Type `Person`, `sort-name` `Davis, Miles`: the source inverts a person's name. |
| `musicbrainz_artist_group_daft_punk.json` | `GET https://musicbrainz.org/ws/2/artist/056e4f3e-d505-4dad-8ec1-d04f521cbb56?fmt=json` — captured **2026-08-14**. Type `Group`, `sort-name` `Daft Punk`: **not** inverted. This is the fixture the whole seam-1 rule turns on; the DEC-051 heuristic would produce `Punk, Daft`. |
| `musicbrainz_artist_other_various_artists.json` | `GET https://musicbrainz.org/ws/2/artist/89ad4ac3-39f7-470e-963a-56509c546377?fmt=json` — captured **2026-08-14**. Type `Other`, `sort-name` `Various Artists`, also not inverted. |
| `musicbrainz_search_dean_blunt.json` | `GET https://musicbrainz.org/ws/2/release-group?query=arid:e8bd5b47-e8b4-4671-a9f6-590a92e88898&fmt=json&limit=25` — captured **2026-08-14**. Two of these credit more than one artist, with `joinphrase` `" & "`: a credit is a **rendered string**, not the `", "` join of a list. |
| `musicbrainz_search_discovery.json` | `GET https://musicbrainz.org/ws/2/release-group?query=Discovery AND artist:Daft Punk&fmt=json&limit=10` — captured **2026-08-14**. The `Group` case reaching the adapter through the search path it really uses: `artist-credit[0].artist.sort-name` is `Daft Punk`, uninverted, in the search response itself. No artist lookup is needed to get it. |
| `musicbrainz_search_now_thats_what_i_call_music.json` | `GET https://musicbrainz.org/ws/2/release-group?query=artist:"Various Artists" AND release:"Now That's What I Call Music!"&fmt=json&limit=10` — captured **2026-08-14**. The `Other` case: `Various Artists`, also uninverted. |
| `coverartarchive_release_group_kind_of_blue.json` | `GET https://coverartarchive.org/release-group/8e8a594f-2175-38c7-a871-abb68ec363e7` — captured **2026-08-14**. The `image` URL is **`http://`**, and each image carries `1200`/`500`/`250` thumbnails. `MAX_COVER_EDGE` is 600, so the 1200 is the one to fetch: the full image is downscaled to 600 anyway and the 500 would upscale. |
| `coverartarchive_thumbnail_1200.headers` | `GET http://coverartarchive.org/release/e7ba3cb7-a074-45ee-870f-3baeb6d3e8bf/12708426541-1200.jpg` — response headers only, captured **2026-08-14**. Status **307**, `Location:` an `http://archive.org/download/...` URL. |
| `archive_org_download_redirect.headers` | `GET http://archive.org/download/mbid-e7ba3cb7-…-12708426541_thumb1200.jpg` — response headers only, captured **2026-08-14**. Status **302** to `http://dn710907.ca.archive.org/…`, a host matched by neither `archive.org` exactly nor the `.us.archive.org` suffix rule. Note that **both** hops answer `http://`, so an https upgrade applied only to the first URL does not survive the chain. |
| `musicbrainz_release_kind_of_blue_recordings_only_20260820.json` | `GET https://musicbrainz.org/ws/2/release/bee5e0cd-1767-4a8e-9578-6455e87ba60b?inc=artist-credits+labels+media+release-groups+recordings&fmt=json` — captured **2026-08-20** for Sprint 030's control. The same request as the 2026-08-15 row above, re-run live: the `media[].tracks` list is identical to that capture in `(number, title, length, recording.id)`, so "a tracklist is one parameter and no extra request" still holds. 6.5 KB. |
| `musicbrainz_release_group_kind_of_blue_releases_20260820.json` | `GET https://musicbrainz.org/ws/2/release-group/8e8a594f-2175-38c7-a871-abb68ec363e7?inc=releases+artist-credits&fmt=json` — captured **2026-08-20** for the same control. Still **25 releases in one group**; the release-group ≈ work, release ≈ edition observation is unchanged. |

The `fields` parameter used for both search recordings is the one
`OpenLibraryProvider.search` sends; it is reproduced in the test that replays them.
