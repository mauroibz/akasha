# Home and recommendations

**Accepted proposal** (DEC-183), written 2026-11-22 at the owner's request and approved the same
day ("Love all of it. Build it all"). The visual mockup is
[`home-and-recommendations-mockup.html`](home-and-recommendations-mockup.html); its covers are
blanked because covers are user data and never committed.

## 1. What the owner asked for

Akasha opens on the library. The owner wants it to open on what they were up to, what they are
doing and what comes next, and also on an overview of the whole library: "a simple way to
interact with what you were likely to be interacting with that day (current and future reads)
but also as an overview of your library. Think bigger, maybe more modular." A first, airy mockup
was rejected for wasted space and for focusing on too few items.

On recommendations: reverse the product-spec non-goal; rank the pile first as a quick win; build
the recommendation code per domain and extensible, prove it with one domain (TMDB), then add a
language model and an embedding model as further sources. Providers must never be crawled to
choose candidates, because that trips their limits. A source selects first; providers enrich only
what was selected. A manual **More like this** on an item.

## 2. Home: a desk you work at

`/` becomes Home. The library moves to `/library`, unchanged.

Home is a 12-column grid of modules with little empty space. Each module reads stored data only
(the invariant: no provider is consulted while rendering a page), and one request,
`GET /api/home`, returns every visible module's payload.

| Module | Reads from | Default size |
|---|---|---|
| Greeting bar | today's date, the active item ("Day 32 of …"), library counts, *Edit home* | full |
| On now | entries in progress across domains (`Library.now()`), with Log, Finished, Set aside | 5 |
| Up next | the pile, five deep, each with *Start*; ranked from Sprint 132 | 7 |
| Year | goals and the Diary: twelve months with covers, slots the goal still needs | 7 |
| Lately | the Diary timeline: finishes, score changes, additions | 5 |
| Library tiles | one per registered domain: count, status bar, score curve, top covers, what is missing; opens `/library?type=…` | full |
| More like this | stored suggestions only, never live calls (from Sprint 134) | 5 |
| Tidy up | duplicate pairs, items without a cover, finished but unscored | 4 |
| One question | Play: a rescore, rank or gap question | 3 |
| Shelves, Lent out | shelves and loans; hidden when empty | 3–4 |

Sizes are column spans: S 3, M 5–6, L 7–8 of 12. On a phone every module is full width in the
same order and its size only changes how much it shows. *Edit home* reorders, resizes and hides
modules; the layout is stored per user on the server. Unknown module keys are ignored on read, so
a layout saved before a module is added or removed still loads.

## 3. Recommendations: select, then enrich

```text
SEED      one item (More like this) or the taste profile
  -> SELECT a source picks a short list in one request, per domain
  -> STORE  suggestions table: title, year, creator, external ids, reason, source, seed
  -> ENRICH the domain's own resolve fills in only the top few, or what the person opens or wants,
            under the existing provider budgets
  -> ANSWER Want (adds to the pile as planned), Not for me, Seen it; stored, shaping the next round
```

A domain declares its sources the way it declares enrichment, so the shared layers never branch on
the item type (technical spec 6.6):

```python
# domains/movie/__init__.py
recommendation = RecommendationSpec(sources=("tmdb",), resolve=resolve_candidate)

# domain/recommendations.py
class RecommendationSource(Protocol):
    name: str
    def select(self, seed: Seed, profile: TasteProfile, limit: int) -> list[Candidate]: ...
```

| Source | Selects from | Domains | Cost | Sprint |
|---|---|---|---|---|
| Rank the pile | the person's planned entries, scored locally | all | none | 132 |
| TMDB | `/movie/{id}/recommendations`, `/tv/{id}/recommendations` | movies, series | one request per seed | 134 |
| Language model | a compact profile in; titles, creators and a reason out | all | one call per round; any OpenAI-compatible endpoint, local or hosted | 135 |
| Embeddings | similarity between stored item text | all | one embedding per item, local or hosted | 136 |

A model can name things that do not exist. Its candidates count only once the domain's resolve
finds them in a provider; anything unresolved is dropped and never shown.

**More like this** is a button on an item's page and on cards in On now and Lately. It queues one
job for that seed; results arrive in a side sheet over the existing event stream. They are stored,
so pressing it again shows the last round with *Refresh*.

## 4. Plan

| Sprint | Delivers |
|---|---|
| 130 | Module grid, `GET /api/home`, On now, Up next, Year, library tiles; the library moves to `/library` |
| 131 | Lately, Tidy up, One question, Shelves, Lent out; Edit home with a stored layout; phone layout |
| 132 | DEC reversing the non-goal; the pile ranked with a reason each, no network |
| 133 | Recommendation infrastructure: per-domain sources, suggestions storage, a `recommend` job with per-source budgets, endpoints, a recorded fake source |
| 134 | TMDB for movies and series, DEC-103 amended for it; More like this button and sheet; the Home module |
| 135 | Model source over an OpenAI-compatible endpoint; off until configured |
| 136 | Embeddings: re-rank the pile and candidates; an offline More like this from the person's own library |
