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

Ten files were **added** on 2026-08-27 for Sprint 038 (the `anilist_*` and `kitsu_*` rows
below), captured with `User-Agent: Akasha/1.2 (+https://github.com/mauroibz/akasha)` and
paced at ~1 s between requests. Nothing was re-recorded. They are the measurement DEC-088
rests on, and two of them exist to pin behaviour that a reasonable implementation would
have guessed wrong:

- **AniList requires a User-Agent.** Requested without one, Cloudflare answers
  `error code: 1010` with HTTP **403**. This is why the header is constructed in the
  adapter rather than left to the shared client.
- **AniList answers a record that does not exist with HTTP 404**, carrying a GraphQL
  `errors` array *and* `"data": {"Media": null}` — not a 200 with a null payload. Latency
  across the capture run was 0.3–1.5 s with one 40.04 s outlier on an otherwise ordinary
  request.

**Jikan (`api.jikan.moe`) has no recordings because it is not registered.** It returned
HTTP 504 (`Jikan failed to connect to MyAnimeList`) to **every** request across a
forty-minute window — 0 of 12 searches and 1 of 81 by-id lookups, where that single
success was a record requested moments earlier and served from its own cache — while
`myanimelist.net` answered the same host in 0.66 s throughout. See DEC-088.

| File | Source |
|---|---|
| `anilist_search_frieren.json` | `POST https://graphql.anilist.co` — the search query the adapter sends, with `{"query": "frieren", "perPage": 10}`. Four of the five rows carry an `idMal`; `Sousou no Frieren` is the first and the studio arrives as `MADHOUSE`, uninverted, in the search response itself, so no second lookup is needed for a sort name. |
| `anilist_search_bocchi_null_idmal.json` | The same query with `"bocchi the rock"`. **`Bocchi the Rock! Re:Re:` has `idMal: null`** — a real record with no MyAnimeList mapping, which is why `identity_key` answering `None` is a live path and not a defensive branch. |
| `anilist_media_20613_akame.json` | `Media(id: 20613)` — Akame ga Kill!. Carries `idMal: 22199`, the same series `kitsu_anime_8270_akame.json` holds, which is what makes the cross-provider merge testable. Its `description` contains `<br>` **even though the query asks for `asHtml: false`**, which is why the adapter strips markup. |
| `anilist_media_mal_44511_chainsaw.json` | `Media(idMal: 44511)` — Chainsaw Man, fetched by MyAnimeList id rather than AniList id. This is the path a pasted `myanimelist.net` link takes. |
| `anilist_media_mal_missing.json` | `Media(idMal: 99999999)` — response body for the **404** described above. |
| `kitsu_search_akame_mappings.json` | `GET https://kitsu.io/api/edge/anime?filter[text]=akame+ga+kill&page[limit]=10&include=mappings` — 19.2 KiB. The `include` is the point: every result carries its `myanimelist/anime` external id in the same request, so a Kitsu **search row** can merge with an AniList one. Without it this domain would have no cross-provider identity. |
| `kitsu_search_frieren_mappings.json` | The same request for `frieren`, 35.0 KiB. Kitsu matched `Blame! Movie` and other export titles that AniList's `SEARCH_MATCH` did not, which is part of why it is registered rather than merely available. |
| `kitsu_anime_8270_akame.json` | `GET .../anime/8270?include=animeProductions.producer,categories,mappings` — 22.7 KiB in one request. **Four producers come back and only one has `role: "studio"`**: Square Enix and TOHO animation are `producer`, Sentai Filmworks is `licensor`, White Fox is the studio. Taking the first would file the series under its manga publisher. Eight mappings arrive, so the MyAnimeList one is matched by site rather than by position. |
| `kitsu_anime_slug_akame.json` | `GET .../anime?filter[slug]=akame-ga-kill&include=...` — the same record reached the way a pasted `kitsu.io/anime/<slug>` URL reaches it. `/anime/{id}` takes a numeric id only. |
| `kitsu_anime_missing.json` | `GET .../anime/99999999?include=...` — Kitsu's **404** body, for the counterpart of the AniList case above. |

Nineteen files were **added** on 2026-08-27 for Sprint 046 (the `wikidata_*` and
`letterboxd_*` rows below), captured with
`User-Agent: Akasha/1.3 (+https://github.com/mauroibz/akasha)` and paced at ~1 s between
requests. Nothing was re-recorded. Every response is a verbatim body except
`wikidata_search_ambiguous.json`, which is **synthetic** and says so in its own row.

The common parameters, sent on every Wikidata request the adapter makes and therefore on
every capture: `format=json&formatversion=2&maxlag=5`, plus `languages=es|en` on entity
reads. Search is `action=query&list=search`; entity and label reads are
`action=wbgetentities`, distinguished only by their `props`. All of them are
`GET https://www.wikidata.org/w/api.php`, which is why the test transport keys routes by
parameters rather than by path.

Three observations are pinned by these files and are the reason the parser reads ranks,
snaktypes and precision rather than first values:

- `Q546900` lists **four** `P364` original languages — German, Latin, *preferred* Italian,
  English — in that order. First-value parsing reads Dario Argento's film as German.
- `Q151599` opens with a **deprecated** `P495` (Germany, retired in favour of the Weimar
  Republic) and a `P364` whose snaktype is `somevalue`: known to exist, unknown which.
- `P577` arrives up to **thirty** times per film at mixed precision, including
  `+1977-03-00T00:00:00Z`. Day zero is a valid month-precision Wikidata timestamp and no
  date parser will read it, so the year is taken from the text.

A fourth observation needed no fixture but is worth recording: `haswbstatement:P345=tt0000000`
returns a real film (`Q137599605`) because that entity genuinely carries the placeholder id.
Wikidata is edited by people, so the adapter re-checks the claim on the fetched entity
rather than trusting that a search hit holds the value it was found by.

| File | Source |
|---|---|
| `wikidata_search_suspiria_films.json` | `srsearch=Suspiria haswbstatement:P31=Q11424&srlimit=6` — exactly two hits, `Q546900` (1977) and `Q28123467` (2018). The same-title remake case, and the evidence that title and year are not identity even between two films that share both. |
| `wikidata_search_metropolis_films.json` | The same search for `Metropolis` — **six** films for one word, with the 1927 one ranked first. The relevance-preservation case; the Sprint 045 unfiltered control put it tenth, behind a record label, a novel and several games. |
| `wikidata_search_el_secreto_de_sus_ojos.json` | The same search for `El secreto de sus ojos` — the Argentine Spanish-language case, one hit. |
| `wikidata_search_la_sustancia.json` | The same search for `La sustancia` — the recent (2024) case, searched in Spanish, one hit. |
| `wikidata_entities_suspiria_pair.json` | `action=wbgetentities&ids=Q546900|Q28123467&props=labels|descriptions|claims` — 200 KiB for **two** films. This is the measurement the batch bound rests on: one entity is ~113 KiB, five reached 1.15 MB and ten reached 1.9 MB against a 2 MiB response limit. |
| `wikidata_entity_Q546900_suspiria_1977.json` | The same request for `Q546900` alone — the fetch-by-id path. Holds the preferred-rank `P364`, the nine mixed-precision `P577` statements, a 17-name cast, `P2047` in minutes, and exact `P345`/`P4947`/`P6127` claims. **No `P18` at all.** |
| `wikidata_entity_Q28123467_suspiria_2018.json` | The same for the 2018 film, whose `P6127` is `suspiria-2018` — the second half of the remake pair. |
| `wikidata_entity_Q748851_secreto.json` | The same for `El secreto de sus ojos`. Its Spanish label differs from its English one (`The Secret in Their Eyes`), which is the localization case, and it credits **thirty-one** cast members, which is the case the cast bound exists for. |
| `wikidata_entity_Q151599_metropolis.json` | The same for `Metropolis`. The deprecated-country and `somevalue`-language case, thirty release dates, and a `P18` that is **`Horst von Harbou - Metropolis set photograph 05.jpg`** — the evidence behind shipping no cover. |
| `wikidata_entity_Q113380226_sustancia.json` | The same for `The Substance` (2024). Its `P18` is a photograph of the cast at a festival: the second measured image, also not poster art. |
| `wikidata_labels_suspiria_pair.json`, `wikidata_labels_Q546900_suspiria_1977.json`, `wikidata_labels_Q748851_secreto.json`, `wikidata_labels_Q151599_metropolis.json`, `wikidata_labels_Q113380226_sustancia.json` | `action=wbgetentities&props=labels` for exactly the linked directors, countries, languages, genres and bounded cast of the entity files above, in the order the adapter asks for them. All under 7 KiB: localizing a whole search costs one small request. |
| `wikidata_search_p6127_suspiria.json` | `srsearch=haswbstatement:P6127=suspiria&srlimit=2` — one hit. Exact Letterboxd-slug resolution through a claim, rather than through a scrape of a site this build has no adapter for. |
| `wikidata_search_p345_tt0076786.json` | The same by IMDb id — one hit, the same film. |
| `wikidata_search_p4947_11906.json` | The same by TMDB movie id — one hit, the same film. Three external identities converging on one entity. |
| `wikidata_search_p6127_no_match.json` | `haswbstatement:P6127=this-film-does-not-exist-xyz` — `totalhits: 0`. A miss is an answer, and is never settled by falling back to a title. |
| `wikidata_search_ambiguous.json` | **Synthetic.** The `P345` response above with its single hit duplicated under a second entity id. No such pair exists on Wikidata today and manufacturing one on a public database is not something to do for a test; the envelope is real so the parser is still exercised against the true shape. |

## Series (Sprint 049, captured 2026-08-31)

Twenty files for the series domain's Wikidata adapter. **Captured without `maxlag`**:
during capture the query-service replicas lagged 40s+ for ~40 minutes, so every
`maxlag=5` request was shed. The replay transport keys on `srsearch`/`ids`/`props`,
not `maxlag`, so the bodies are interchangeable with what the adapter requests.

| File | What it is and why it was chosen |
| --- | --- |
| `wikidata_series_search_bojack.json` | `srsearch=BoJack Horseman haswbstatement:P31=Q5398426\|Q117467246\|Q63952888\|Q1259759\|Q581714&srlimit=6` — the animated-series class (`Q117467246`). The real series `Q17733404` ranks first; the second hit is the fictional show-within-the-show. |
| `wikidata_series_search_chainsaw.json` | The anime-series class (`Q63952888`): `Chainsaw Man` → `Q104211858`, one hit. |
| `wikidata_series_search_chernobyl.json` | The miniseries class (`Q1259759`): `Chernobyl` → `Q48741246` at rank 1, six hits total, so the adapter's two entity batches are both exercised. |
| `wikidata_series_search_breaking_bad.json` | The ordinary class (`Q5398426`): `Breaking Bad` → `Q1079` at rank 1. |
| `wikidata_series_search_bojack_single_class.json` | **Control:** the movie adapter's single-class shape `haswbstatement:P31=Q5398426` for `BoJack Horseman` — `totalhits: 1`, and the one hit is the fictional show-within-the-show `Q87484192`, not the real series. |
| `wikidata_series_search_chainsaw_single_class.json` | **Control:** the same shape for `Chainsaw Man` — `totalhits: 0`. Under the movie shape this title returns *nothing at all*. |
| `wikidata_series_search_chernobyl_single_class.json` | **Control:** the same shape for `Chernobyl` — three hits and the real miniseries is not first. These three recordings are AC3's executable evidence that the five-class filter is load-bearing. |
| `wikidata_series_search_p345_tt0903747.json` | `haswbstatement:P345=tt0903747` — one hit, `Q1079`. Exact IMDb-id resolution, 13/13 in the viability measurement. |
| `wikidata_series_search_p345_no_match.json` | `haswbstatement:P345=tt9999999` — `totalhits: 0`. The id was chosen by querying live: `tt0000001` turned out to be filed on an 1894 film, so a "round number" is not automatically a miss. |
| `wikidata_series_entities_bojack_pair.json` | `action=wbgetentities&ids=Q17733404|Q87484192&props=labels|descriptions|claims` — the real series and the show-within-the-show in one batch. The second entity carries `P31=Q5398426` itself (Wikidata files a fictional series as a series), so it passes the class guard; the search-control recordings are what keep it out of results. |
| `wikidata_series_entity_Q104211858_chainsaw.json` | The anime entity: **no `P170` and no `P161`** — the screenwriter-fallback and absent-cast cases in one. |
| `wikidata_series_entity_Q48741246_chernobyl.json` | The miniseries entity: **no `P2437`** (a miniseries has no seasons claim), `P1113=5`, `P582` present → `Ended`. |
| `wikidata_series_entity_Q1079_breaking_bad.json` | The ordinary long-running entity: 572 KiB alone — the size measurement behind keeping the entity batch at 3. `P1113=62`, `P2437=5`, full cast, `P345=tt0903747`. |
| `wikidata_series_entities_chernobyl_batch2.json` | The second Chernobyl batch (`Q121879824|Q86000614|Q15270776`): what a six-hit search costs in entity reads. |
| `wikidata_series_entity_Q4500_vince_gilligan.json` | `Q4500`, a human (`P31=Q5`). The most legible thing to paste into the add box by mistake; the `_is_series` guard refuses it. |
| `wikidata_series_labels_bojack_pair.json`, `wikidata_series_labels_Q104211858_chainsaw.json`, `wikidata_series_labels_Q48741246_chernobyl.json`, `wikidata_series_labels_Q1079_breaking_bad.json`, `wikidata_series_labels_chernobyl_search.json` | `action=wbgetentities&props=labels` for exactly the linked creators, countries, languages, genres, networks and bounded cast of the entity files above, in the order the adapter asks for them. The `chernobyl_search` one spans both entity batches. |
| `letterboxd_boxd_it_redirect.headers` | `HEAD https://boxd.it/2b0k` — response headers only. Status **302**, `Location: https://letterboxd.com/film/the-dark-knight/`. A public short link, not the owner's export. One hop, HEAD only, and the body is never requested: this is identity resolution, and parsing the destination's HTML would cross the boundary the movie design deliberately avoids. |
