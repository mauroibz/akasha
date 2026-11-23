# The library is the home again

**Accepted proposal** (DEC-193), written 2026-11-23 at the owner's request after 3.1.0 and
accepted the same day as alternative A, revised over three readings (section 8). Scheduled as
Sprints 139–148. The visual mockup is [`library-first-mockup.html`](library-first-mockup.html); its
covers are invented. If accepted it supersedes part of DEC-183 (Home at `/`, the library at
`/library`); Home's modules and recommendations survive in another form (section 3.3).

## 1. What the owner asked for

The library was meant to be the home screen and its search bar the main way to find and add.
Home took the focus away from it. Adding now lives in three places and *Add*, meant as the last
resort, is the door people try first. Shelves compete with the library, Insights with the Diary,
and the four screens look slightly different. Asked for: one unified experience that still feels
like stepping into your own library; the library ordered as *what you are on now*, *what you did
lately*, *everything else*; a home you can make yours (shelves, metrics); media in your order
("anime first, books second, don't care about music"); a few preset themes.

## 2. What was measured

Run on 3.1.0 against a copy of the local development library (17 entries, books and albums) at
1440 and 390 px. Every main screen was opened and read alongside its code.

### 2.1 Adding has six doors, and the one labelled *Add* is the wrong one

| Door | Where | What it does |
|---|---|---|
| *Search or add* (⌘K) | top bar, every screen | finds in the library, adds from providers, reads links |
| *Add* | navigation | a 20-field manual form and an EPUB drop zone |
| *Import* | navigation | bulk import |
| the search field and *Search* button | Library toolbar | filters the library and shows web results |
| *Add* | Library toolbar, right | the same manual form |
| *Inbox 2* | Library toolbar and the Import badge | what an import left to sort |

The Add page's own first paragraph tells the reader to go elsewhere: "To add from a provider,
press ⌘K or use Search or add". A screen that has to redirect people is in the wrong place. The
good door is styled as a small outlined button on the far right; the last resort has a
navigation slot with a plus sign.

### 2.2 The same content appears under different names

| Content | Places |
|---|---|
| What is under way | Home *On now* (buttons: +chapter, Mark as read, Set aside, More like this) and Library *Now* (+1, Mark as read) |
| What was finished this year | Home *2026*, Home *Your 2026 books*, Home *Lately*, Diary. On the test library the same two books are drawn three times on Home |
| The pile | Home *Up next*, `/pile`, Insights *The pile: still want these?* |
| Small jobs and games | Home *Tidy up* and *One question*, Insights *Play with your library*, `/deck` |
| Shelves | Home *Shelves*, the Shelves screen, the Library's shelf filter, *Pin to library* |
| A subset of the library | a shelf, a saved view, a filter: three mechanisms for one idea |
| Media | Home *Your libraries* tiles and the Library's chooser |

### 2.3 Shelves and the library; Insights and the Diary

A shelf's page is the library filtered to that shelf, drawn with a different card (serif title,
no status or score control), a different width and no filters. The Shelves index is the only
screen with drawn shelf boards. Insights and the Diary both look back: one by field, one by
month. Goals and the year in review hang off the Diary, the year module is on Home, and Insights
opens with four games that are not insights.

### 2.4 The screens do not share a frame

| Element | Variants found |
|---|---|
| Page width | seven: `3xl`, `4xl`, `5xl`, `6xl`, `7xl`, 1280 px, 1600 px |
| Page title | Home: a 30 px sentence. Library: a wordmark and a count, no title. Shelves: 96 px. Insights: 60 px. Diary and others: `PageHeader` at 48 px with a rule |
| Medium chooser | filled pills (Library), underlined tabs (Insights), small chips (command bar), a select (Add) |
| Cover card | five treatments: Library (status and score on the cover), shelf page (serif caption), Diary (truncated caption), Home *Up next* (500 px tall), Shelves (tilted on a board) |
| Sections | bordered cards (Home), flat (Library), numbered and ruled (Insights), boards (Shelves) |

Each screen was designed well by itself, in its own sprint. The disjointed feeling comes from the
sum.

### 2.5 Customising exists and is hard to find

*Edit home* (3.0) reorders, resizes and hides modules, and 3.1 added a module per shelf and a year
per medium. It is a text link at the right of the greeting, opens a modal list of S/M/L rows that
covers the screen it edits, and cannot place a metric. Nothing lets a person order or turn off a
medium: the chooser shows Book, Album, Anime, Movie, Series in that order for everyone, including
the three that are empty in the test library. Themes are two (*Ink*, *Paper*), in Settings.

### 2.6 Navigation

Seven destinations, a search button and Settings on desktop; about thirty routes. The phone bar
holds five (Home, Library, Add, Shelves, Insights) and drops Diary and Import.

## 3. The proposal

Akasha becomes one place, the library, with two rooms off it. Navigation goes from seven items
to two: **Library** and **Journal**. The bar sits between them and the account menu.

### 3.1 Library at `/`: three bands in the order asked for

1. **Now.** Everything under way, across the media marked *Front*, in the owner's media order.
   One card design with the medium's own progress step and *Finish*. The greeting sentence stays
   above it; it is the best-liked line in the application and it belongs to the library.
2. **Lately.** One row of covers: finished (with score) and added, newest first. It replaces
   Home's two year modules and the *Lately* list.
3. **Showcases.** The row or two the person arranged (3.3). Empty by default except *Up next*.
4. **Everything.** The current library grid, unchanged in behaviour: medium tabs in the owner's
   order, filters, and a view switch **Covers · Table · Shelves**.

`/library` redirects to `/`. Home as a separate screen is removed.

### 3.2 One bar

The top bar's field becomes a real input on every screen, centred, labelled "Search your
library, or add something". It is the existing command bar and the Library's search merged:

- results from the library first, then *Add from the web*, with an **Add** button that files
  under the medium's default status and offers the others in place;
- a pasted link or ISBN resolves as it does today; a dropped file is taken anywhere (existing
  `GlobalDrop`);
- on the Library it also filters the grid as you type, so the toolbar's own field goes;
- its footer carries the two last resorts: **Enter it by hand** (today's Add form) and **Bring
  a whole list** (today's Import).

*Add* and *Import* leave the navigation. Import is also reachable from Settings → Your data.
The Inbox count moves to the greeting line ("2 to sort"). On a phone the bar is the centre
button of a three-slot tab bar.

### 3.3 Arrange: showcases, in place

*Arrange* edits the Library where it stands: showcases get a handle, S/M/L and remove; a tray
offers what can be added. This replaces the *Edit home* modal and reuses its stored layout,
packing and the `year:<type>` and `shelf:<id>` families.

| Showcase | From |
|---|---|
| A shelf | Home's shelf module |
| A year or goal, per medium | Home's year modules |
| Up next, More like this, One question | Home's modules, unchanged |
| **A number from Journal** (new) | one insight section at card size: how you rate, top subject, a decade chart |

Dropped as modules because the bands and tabs now say it: *On now*, *Lately*, *Library tiles*,
*Shelves* chips, *Tidy up* (moves to Play), *Lent out* (a built-in shelf).

### 3.4 Your media

A per-person ordered list, each medium **Front**, **Kept** or **Off**:

- order drives the Library's tabs, Now, Lately, the bar's default medium and Journal's tabs;
- *Front* media feed Now, Lately and the greeting; *Kept* media are in Everything and the bar
  only; *Off* media are hidden everywhere and nothing is deleted;
- a medium with no entries that was never chosen is not shown;
- first run asks "What do you keep?" once.

The shared layers take the list as data from the registry and never branch on a medium's name
(technical spec 6.6 holds).

### 3.5 Shelves are a view, and one idea

- The Shelves index becomes the **Shelves** view of Everything, keeping the drawn boards.
- A shelf opens as the library filtered to it: the same card, controls and filters, under the
  shelf's name and sentence. `/shelves/:slug` stays as the address.
- A saved view becomes a shelf with a rule ("anime rated 9 or more") beside hand-picked shelves.
- The pile and *Lent out* become built-in shelves; `/pile` and `/lent` redirect.

### 3.6 Journal

Diary and Insights merge into one screen, and the games join them. Revised twice on the owner's
reading (section 8): it opens on something to do, not on a page of notes or a page of figures.

1. **One widget at a time, switched by tabs.** The last one used is remembered.

   | Widget | What it is | Built from |
   |---|---|---|
   | **Every day** | this week or this month as a grid of days, one light per day, after Simone Giertz's Every Day Calendar; never the whole year. A day lights when progress is logged or something is finished, or when the person lights it. Per person: which media count | new; see below |
   | **Play** | the games and decks as cards: Five minutes, the rank deck, the pile deck, gaps, tidy up, tiers | Insights' *Play with your library*, Home's *Tidy up* and *One question*, `/deck` |
   | **Goal** | a year's slots per medium, and the invitation to set one | the Diary's goal band |

2. **Timeline.** The Diary's months as covers, with the year in review.
3. **Patterns.** The Insights sections, each opening with its sentence.

*Every day* needs data the application does not keep: progress marks say which episode is done,
not on which day. It needs a small dated record (one migration): a row per person and day,
written when progress is logged, when something is finished, or by a tap. Days before the
migration can be lit from stored finish and start dates only. In the lights' existing manner
(DEC-169, DEC-171) an unlit day is plain and nothing counts streaks.

### 3.7 Play

Play has no screen and no navigation slot. It is the Journal's Play widget; each game still opens
full screen at its own address.

### 3.8 One frame for every screen

| Element | Rule |
|---|---|
| Width | two: 1440 px for screens of covers, 960 px for screens of text and forms |
| Header | one `PageHeader`: a serif sentence about your data at 40 px ("Five shelves, 7 things on them"), actions at the right. Shelves and Insights already write this sentence; every screen gets one |
| Medium chooser | one component, underlined tabs, in the owner's order |
| Cover | one component with three sizes and one caption; status and score controls are an option of it, not a second card |
| Section head | serif h2, a quiet count, one link at the right |
| Surfaces | the page is flat; a border and fill mark a showcase or a dialog and nothing else |

### 3.9 Themes

Presets, each a complete token set held to WCAG AA by the existing contrast test: *Paper* and
*Ink* as today, plus four in the mockup (*Moss*, *Claret*, *Dusk*, *Sakura*). The score ramp does
not change with the theme (DEC-026: it means score) and the mark's dot stays amber
(`brand/BRAND.md`). The picker sits in Arrange and in Settings. Free colour pickers are left out:
they cannot be held to contrast.

### 3.10 Style

A first set of stronger positions was drawn at the owner's request and the owner rejected the
Library it produced (section 8): covers on drawn boards in *Now* and *Lately*, a bookplate, a
lamp, *Now* renamed *On the table*, actions as underlined words. Those are withdrawn. The
Library is as first drawn. What stands is section 3.8 and two rules from it: every screen opens
with one serif sentence about the person's own data, and the chrome uses the theme's neutrals
and its one accent so that covers carry the colour.

## 4. Alternatives

| | What changes | Answers | Cost |
|---|---|---|---|
| **A. Library first** (this proposal) | Home merges into Library; one bar; Journal with its widgets; media order; themes | all of section 1 | 10 sprints |
| B. Keep Home, remove the overlaps | Add and Import leave the nav; Now strip leaves the Library; one frame; themes; media order | adding, look, themes, media. Home and Library still compete; Shelves and Diary stay apart | 5 sprints |
| C. One frame only | section 3.8 and themes | the look. No structural change | 2 sprints |
| D. A room per medium | each medium gets its own home, bands and journal, with a lobby above | media that do not mesh. Splits a person who mixes media across rooms, and multiplies screens | 12 or more sprints |

A is recommended. B is the fallback if removing Home a day after shipping it is too much; it
leaves the owner's first complaint standing.

## 5. Cost and order

Each row is one sprint. Order puts what is felt first ahead of what is merged.

| # | Sprint | Delivers |
|---|---|---|
| 1 | One frame | the two widths, `PageHeader`, the cover, the chooser, on every screen. No behaviour change |
| 2 | One bar | the input in the top bar; library results, web add, the two footer doors; Add and Import out of the nav; the Library's own field removed |
| 3 | Library at `/` | Now and Lately bands; `/library` redirects; Home removed; its modules render as showcases |
| 4 | Arrange | in-place editing, the tray, the *number from Journal* showcase |
| 5 | Your media | order and Front/Kept/Off per person, applied everywhere; the first-run question. One migration |
| 6 | Shelves as a view | the Shelves view; a shelf as the filtered library; the pile and Lent out as built-in shelves |
| 7 | Rule shelves | saved views become shelves with a rule. One migration |
| 8 | Journal | the widget switcher with Play and Goal; Timeline; Patterns; old addresses redirect |
| 9 | Every day | the dated record (one migration), the calendar widget, which media count |
| 10 | Themes | four presets and the picker |

Release as 4.0.0: addresses move and Home goes. Every old address redirects.

## 6. Risks

- Home shipped in 3.0 the day before this was written. Its data (`/api/home`, the layout store)
  is reused; its screen is not.
- The Library is the heaviest screen (virtualised grid, DEC-023's DOM budget). The bands above
  it must not break the budget: they are a fixed, small number of cards.
- Sprint 2 changes how every Playwright spec that adds an item gets there.
- *All* as a medium tab mixes 2:3 covers with square ones. It is drawn in the mockup and should
  be decided in sprint 3, by trying it.

## 7. For the owner to decide

1. A or B.
2. Settled: Play lives inside the Journal (section 8).
3. Which presets, and their names.
4. Whether a shelf with a rule is wanted now (sprint 7) or later.

## 8. The owner's reading, 2026-11-23

- **A** is chosen.
- The Journal must invite writing before it shows statistics: section 3.6 is rewritten.
- Theme presets are wanted (3.9 stands).
- Shelves with a rule stay in this line (sprint 7).
- "It can still use some extra style and be more opinionated": section 3.10 is added and the
  mockup redrawn to it.
- Second reading, the same day: no notes page in the Journal, which the owner would rarely use.
  It switches between widgets instead: Play as its interactive part, and a calendar of lit days
  in the style of Simone Giertz's Every Day Calendar (3.6, 3.7; one sprint added).
- The redrawn Library is rejected; the first drawing stands (3.10).
- Third reading: *Every day* shows this week or this month only. "Then great! build it all."
- While the plan was written: lighting a day asks what it was for, drawing from what is under
  way; "this could become a great user flow if expanded, but it must be kept simple and calm".
- Still open: the presets' final list and names.
