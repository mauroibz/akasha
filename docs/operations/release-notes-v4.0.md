# Akasha v4.0.0 — release notes

The library is the home again. Sprints 139–150 (DEC-193, DEC-194, DEC-195).

## What you will notice

- **Akasha opens on your library.** `/` is the Library. Above the grid it shows the greeting,
  what is under way (*On now*), a row of covers for what you finished and added (*Lately*), and
  the things you placed there: *Up next*, a year per library, any shelf, *One question*, *More
  like this*, or a number from the Journal such as how you rate your books. Then *Everything*.
  A search or a filter puts all of that away.
- **Two places.** The navigation is *Library* and *Journal*. Shelves are a view of the Library
  (*Grid · Table · Shelves*); Diary, Insights and the games are the Journal.
- **One bar for finding and adding.** On the Library it is the Library's own search field. On
  every other screen it is the field at the top (⌘K); on a phone, the button in the middle of
  the tab bar. *Add* and *Import* are no longer in the navigation: they are the two links at
  the bottom of the bar, *Enter it by hand* and *Bring a whole list*. What an import left to
  sort shows as "N to sort" at the top of every screen.
- **Personalize.** The link beside the greeting. Drag a handle to move anything, *On now* and
  *Lately* included; set its size; remove it. The dashed square with a plus opens a list of
  what can be added, with a preview drawn from your own library before you add it. *Your
  media* and *Theme* are in the bar at the top while you personalize.
- **Your media.** Order your media and mark each *Front*, *Kept* or *Off*. The order is the
  order of every chooser. Front media fill *On now*, *Lately* and *Up next*; kept media stay in
  the library; off media are hidden and nothing is deleted. Until you choose, the media you
  hold are in front and the ones you never used are off, so their empty tabs are gone. Also in
  Settings.
- **The Journal** opens on one widget at a time:
  - *Every day*: this week or this month as a grid of days, lit on the days you logged
    progress or finished something. Tap a day to light it yourself; it asks what it was for,
    offering what is under way, with *Something else* to search your library or the web. No
    streaks.
  - *Play*: the games that were at the top of Insights, with *Tidy up*, the rank list and
    tiers.
  - *Goal*: this year's goals, or the invitation to set one for a medium you choose.

  Below it, the timeline of what you finished, then the patterns.
- **Shelves.** *The pile* and *Lent out* stand among your shelves. A filtered Library can be
  saved with *Save as a shelf* (it was *Save view*): the shelf follows those filters, and your
  existing saved views appear as such shelves. A shelf's own page still shows covers to look
  at, and links to the same shelf in the Library for sorting and editing.
- **Four more themes.** *Moss*, *Claret*, *Dusk* and *Sakura*, beside *Paper* and *Ink*, in
  Settings and in Personalize. Scores keep their colours in every one.

## Addresses that moved

Old links and bookmarks keep working: each redirects.

| Old | Now |
|---|---|
| `/library` (with any filters) | `/` |
| `/shelves` | `/?view=shelves` |
| `/insights` | `/journal#patterns` |
| `/diary` | `/journal#timeline` |

`/add`, `/import`, `/inbox`, `/pile`, `/lent`, a shelf's page and an item's page are where they
were.

## Upgrading

Set `AKASHA_VERSION=4.0.0` and bring the stack up. Two migrations run on start, after the
usual pre-migration backup:

- **0039** adds `media_preferences` (empty; your media are derived from what you hold until
  you choose).
- **0040** adds `lit_days` and lights past days from the start and finish dates your library
  already holds.

No setting is new or changed. A Home layout saved in 3.0 or 3.1 is kept: what it placed stays
placed, and the modules that no longer exist (the all-libraries year, the library tiles, the
shelves list, *Tidy up*, *Lent out*) drop out of it.

Rolling back to 3.1.0 needs the pre-migration backup: 3.1.0 does not know the two new tables.

## Known limits

- The field at the top opens the search bar; it is not typed into in place.
- A shelf that follows a rule cannot be placed on the Library's front yet.
- *Every day* counts progress on the server's day, not the browser's, when the two differ.
- A year can be placed for a medium you hold nothing of; it stays empty until you do.
