# Metadata Domains for a “MyAnimeList for Everything” Self-Hosted App

**Status:** historical — a viability survey, not a design. Written before the domain architecture
existed. Its per-provider assessments (catalogue breadth, Spanish coverage, artwork, licensing) are
still the reference for *which* domain to build next and are not superseded by anything.

**Its architecture recommendation is superseded.** "Build the plugin boundary now, keep it internal
and lightweight" was answered by DEC-052 and built by Sprints 025–028: the boundary exists, it is
code rather than a plugin runtime, and how to attach a domain to it is
[`guides/adding-a-domain.md`](guides/adding-a-domain.md). Read the sections below for provider
economics, not for how this codebase is organised.

---

## Executive summary

There are enough viable domains to justify a **generic domain/plugin architecture now** rather than hard-coding books plus one or two additions.

For this project, a domain is worth treating as first-class when a **hosted API can support normal search + item lookup** without requiring a local copy of the provider’s full dataset. Bulk dumps are optional bonuses, not a dependency. The most important product-quality questions are:

1. Can a self-hosted instance search the catalog live?
2. Is the catalog broad enough for real users, including non-US content?
3. Does the provider expose useful artwork/covers/images?
4. For language-sensitive media, can it return **Spanish and English titles/descriptions/editions/localizations** rather than only English metadata?
5. Is there any provider rule that materially blocks a tracker application?

**Best roadmap candidates:** movies/TV, music, video games, academic papers, artworks, books, trading cards, LEGO, packaged products, and (with caveats) wine.

**Domains that look attractive but need care:** anime/manga, board games, podcasts, wine, beer, comics. The issue is usually not technical API quality; it is provider dependency, weak Spanish/localized metadata, catalog gaps, or terms that specifically clash with a tracker.

### Recommended architecture decision

Build the plugin boundary now, but keep it **internal and lightweight** at first. Separate:

- **Domain plugin:** understands the object model and UX (album vs release, game vs platform release, wine vs vintage, series vs episode).
- **Provider adapter:** handles search, lookup, credentials, images, language/localization and provider-specific limitations.

A small shared core is enough: `id`, `title`, `subtitle/creator`, `image`, `status`, `score`, `note`, `dates`, `tags`, plus domain-owned metadata.

---

## The problem

The current app works because books have mature metadata providers: search a title/author/ISBN, retrieve metadata and cover art, then store the user’s own state locally.

The roadmap question is whether this model generalizes. If enough domains have dependable **hosted metadata APIs**, the app can become a framework for personal libraries: games played, albums heard, wines tried, manga read, places visited, papers read, etc. If most domains require maintaining huge local datasets or scraping websites, a generic plugin system would be premature.

The research says the model **does generalize**, but provider capabilities differ enough that domains and providers should not be the same abstraction.

---

## Domain assessment

| Domain | Recommended provider(s) | Hosted search / lookup | Images | Spanish / multilingual fit | Roadmap viability |
|---|---|---|---|---|---|
| **Books** | Google Books; Open Library | **Yes** | Covers | **Excellent.** Editions carry language; Open Library can prefer/filter editions by language, so Spanish translations can be represented separately. | **Excellent** |
| **Movies** | TMDB | **Yes** | Posters/backdrops | **Excellent.** TMDB supports localized metadata and translated titles/descriptions using language-country codes such as `es-ES` / `es-*`. | **Excellent** |
| **TV series** | TMDB; TVmaze | **Yes** | Posters/episode images | **TMDB: excellent localization. TVmaze: global catalog but localization is much weaker.** Prefer TMDB when Spanish display metadata matters. | **Excellent** |
| **Music albums/releases** | MusicBrainz + Cover Art Archive | **Yes** | Cover art | **Good.** Global catalog; releases store language/script and entities can have locale-specific aliases. Less “translated editorial text” because music metadata is mostly language-neutral. | **Excellent** |
| **Video games** | IGDB | **Yes** | Covers/art/screenshots | **Good global catalog; weaker localized presentation.** Excellent metadata and platform/release structure, but do not assume Spanish titles/descriptions exist for every game. | **Excellent** |
| **Anime / manga** | AniList technically; alternative provider may be needed | **Yes** | Excellent | **Weak for Spanish localization.** AniList exposes romaji, English and native titles, not a general Spanish-title field. More importantly, its terms restrict competing tracker services unless authorized. | **Marginal as a default provider** |
| **Academic papers** | Crossref + OpenAlex | **Yes** | Usually none | **Good/global.** Metadata language follows publications; Spanish-language papers are well represented, though there is no “translated title” expectation like movies/books. | **Excellent** |
| **Artworks / museum objects** | The Met API; Europeana | **Yes** | Often excellent | **Good geographically; variable linguistically.** Europeana is stronger for multilingual European metadata; individual museum records depend on source institution. | **Good–Excellent** |
| **Trading cards** | Scryfall (Magic); Pokémon TCG API | **Yes** | Excellent | **Domain-dependent.** Magic has multilingual printings/card data; Pokémon is franchise-specific. Great plugin model, but not one universal “cards” catalog. | **Excellent per ecosystem** |
| **LEGO sets** | Rebrickable | **Yes** | Set/part images | Mostly language-neutral identifiers/names. Global catalog, not US-only. | **Excellent** |
| **Board games** | BoardGameGeek XML API | **Yes, but throttled/registered** | Yes | **Global catalog, limited localization semantics.** Alternate names help, but Spanish descriptions/localized editions are not the core strength. Registration/approval is now required for most API use. | **Good, provider-dependent** |
| **Wine** | Grapeminds; Open Food Facts as barcode fallback | **Yes** | Variable | **Promising but not yet as clean as books/movies.** Grapeminds is not US-only: it has global regions and explicitly covers Argentina (e.g. Uco Valley/Mendoza). Its API exposes multilingual regional/wine metadata; Spanish appears in endpoint language support, though current top-level docs advertise multilingual support inconsistently. Free access is also very small (~250 requests/month / trial-style entry). | **Good experiment, not core yet** |
| **Beer / breweries** | Open Brewery DB; Open Food Facts for packaged beers | **Yes** | Weak for breweries; product photos via OFF | Global brewery coverage; language mostly names/locations rather than translated content. There is still no equally strong open live catalog for individual beers. | **Good for breweries; weak for beers** |
| **Packaged food/drinks** | Open Food Facts | **Yes** | Excellent product photos | **Excellent multilingual product model.** Language/country can be supplied independently; Spanish and imported products are natural fits. Best UX is barcode-first rather than aggressive search-as-you-type because public search limits are conservative. | **Good–Excellent** |
| **Podcasts** | Podcast Index | **Yes** | Feed artwork | **Good for Spanish discovery** because language and text come from publisher feeds, but metadata quality is publisher-dependent. Provider caching/storage terms make it less natural for a permanently self-contained local catalog. | **Good, with dependency caveat** |

---

## Notes by domain

### Movies and TV — strongest next plugin

**TMDB** is the cleanest example of what the architecture should support. It provides live search/detail APIs, stable IDs, posters/backdrops and first-class localization. Most metadata endpoints support translated data, making it appropriate for an English/Spanish UI without maintaining a local catalog.

Use TMDB for both movies and TV unless TVmaze offers some specific episode/schedule feature you prefer. TVmaze is technically excellent and very easy to consume, but TMDB is clearly stronger when localized display metadata matters.

**Roadmap:** first wave.

### Music — another ideal architecture test

**MusicBrainz** exposes live search and lookup without an API key (with a meaningful User-Agent and ~1 request/sec limit). It models artists, recordings, release groups and individual releases properly, while **Cover Art Archive** supplies artwork.

Its language model is useful rather than cosmetic: releases have language/script and aliases can be locale-specific. It will cover Spanish-language and Latin American music naturally, although “Spanish metadata” is less important here than for movies because album names generally are not translated.

**Roadmap:** first wave.

### Video games — excellent data, moderate localization

**IGDB** has one of the richest live APIs: search, games, platforms, releases, companies, genres, covers, artwork and screenshots. It requires Twitch/OAuth credentials and a backend, with a documented limit around 4 requests/sec.

The catalog is global, but localization should be treated as **optional enrichment**, not guaranteed Spanish display metadata. The plugin should therefore retain original title plus any localized/alternate names the provider exposes instead of assuming a single translated-title field.

**Roadmap:** first wave.

### Anime and manga — good domain, wrong default provider

**AniList** is technically almost perfect for the UX, but two issues matter:

- its title model is primarily `romaji / english / native`, not general localized titles such as Spanish;
- current API terms explicitly prohibit competing anime/manga list/tracker services unless authorized.

So anime/manga remains a **good domain** for the architecture, but AniList should not be the assumed foundation. A future plugin should evaluate another provider or make AniList an optional user-configured integration.

**Roadmap:** domain yes; provider research still needed.

### Wine — viable, but not yet a “free Goodreads for wine”

The earlier assumption that wine metadata might be US-centric is not correct for the strongest current hosted option. **Grapeminds** exposes roughly 292k wines, 79k producers and 2k+ regions and includes Argentine regions such as **Uco Valley, Mendoza**. It provides live full-text search, producer/region/grape structure and multilingual metadata.

The weakness is access economics rather than geography: the free allowance is very small, and its language documentation is inconsistent about exactly which fields are available in Spanish. For a personal self-hosted plugin, this is enough to prototype, but not yet strong enough to call the domain solved.

**Open Food Facts** is useful as a barcode/photo fallback for bottles, but it is a packaged-product database, not a specialist wine catalog.

**Roadmap:** experimental plugin after the first media domains.

### Board games — technically viable, newly more annoying

**BoardGameGeek XML API2** remains a strong catalog with search, item lookup and images, but registration/application authorization is now required for nearly all API use and requests are heavily throttled (roughly one every few seconds is the safe pattern). It is still fine for a personal server, but is a strong example of why provider adapters should be replaceable.

**Roadmap:** second wave.

### Academic papers — ideal non-media proof

**Crossref + OpenAlex** show that the architecture is useful beyond entertainment. Both expose hosted APIs and strong canonical identifiers. Spanish-language research is naturally covered because the catalogs are global; the main drawback is visual presentation, since there is no consistent cover-art ecosystem.

**Roadmap:** second wave if this use case is personally useful; technically one of the easiest.

### Packaged products — best “unexpected” domain

**Open Food Facts** gives global, multilingual product metadata plus product photography and barcodes. It explicitly supports language and country independently, so Spanish products, Argentine products and imported products fit naturally.

Its live API is suitable for product lookup and moderate search, but the public search endpoint should not be used as high-frequency typeahead. A barcode scanner would make this plugin particularly strong.

**Roadmap:** second wave / proof that the plugin model extends beyond media.

---

## Suggested roadmap

### Phase 1 — prove the abstraction

1. **Books** (existing)
2. **Movies / TV — TMDB**: localized metadata + rich images
3. **Music — MusicBrainz**: work/release variants + separate image provider
4. **Video games — IGDB**: rich domain schema + authenticated provider

If these four coexist cleanly behind the same app shell, the plugin architecture is justified.

### Phase 2 — prove non-media and provider variation

5. **Academic papers — Crossref/OpenAlex**: no-artwork domain
6. **Packaged products — Open Food Facts**: barcode + multilingual physical products
7. **LEGO or trading cards**: highly structured collectible ecosystem
8. **Board games — BGG**: slower/provider-dependent API

### Phase 3 — exploratory domains

9. **Wine — Grapeminds + optional OFF**
10. **Anime/manga — after selecting a provider compatible with a tracker**
11. **Podcasts**
12. **Beer / breweries**
13. **Comics / other collectibles**

---

## Architecture implication

Do not make the plugin API simply `search(query) -> generic item` and stop there. The minimum useful provider contract should expose capabilities:

```ts
interface MetadataProvider {
  search(query: string, locale?: string): Promise<SearchResult[]>;
  get(id: string, locale?: string): Promise<ProviderItem>;

  capabilities: {
    images: boolean;
    localizedMetadata: boolean;
    variants: boolean;
    barcodeLookup?: boolean;
  };
}
```

And keep **domain identity separate from provider identity**:

```text
MovieDomain -> TMDBProvider
MusicDomain -> MusicBrainzProvider + CoverArtProvider
WineDomain  -> GrapemindsProvider + OpenFoodFactsProvider
```

That is enough abstraction for the roadmap. There is no evidence yet that you need a public third-party plugin SDK or a complex provider-policy engine.

---

## Primary sources checked (Aug 2026)

- TMDB language/localization docs: https://developer.themoviedb.org/docs/languages
- TMDB API basics: https://developer.themoviedb.org/docs/getting-started
- TVmaze API: https://www.tvmaze.com/api
- MusicBrainz API: https://musicbrainz.org/doc/MusicBrainz_API
- MusicBrainz aliases/localization: https://musicbrainz.org/doc/Aliases
- Cover Art Archive API: https://musicbrainz.org/doc/Cover_Art_Archive/API
- IGDB API: https://api-docs.igdb.com/
- AniList API title model: https://docs.anilist.co/reference/object/mediatitle
- AniList API terms: https://docs.anilist.co/guide/terms-of-use
- Open Library Search API: https://openlibrary.org/dev/docs/api/search
- Google Books API: https://developers.google.com/books/docs/v1/using
- BoardGameGeek XML API2: https://boardgamegeek.com/wiki/page/BGG_XML_API2
- BoardGameGeek API registration guide: https://boardgamegeek.com/using_the_xml_api
- Rebrickable API: https://rebrickable.com/api/
- Grapeminds Wine API: https://grapeminds.eu/wine-api
- Grapeminds Uco Valley coverage: https://grapeminds.eu/wine-regions/uco-valley-733
- Open Food Facts API: https://openfoodfacts.github.io/openfoodfacts-server/api/
