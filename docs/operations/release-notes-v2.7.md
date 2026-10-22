# Akasha v2.7.0 — release notes

Episodes and chapters: how far you got. Sprints 107–108 (DEC-171 to DEC-175).

## What you will notice

- **Episodes watched is a row of lights.** On a series, anime or book's page, the *Episodes
  watched* (or *Chapters read*) row reads "22 / 62 episodes" with *Show episodes*. Opened, it
  shows one light per episode, a row per season, in the goal calendar's style.
  - Tap a light to mark that episode; tap *Season 2* to mark all of it, or clear it when it is
    all marked. The count follows what is lit.
  - A count you already had (from a Trakt or MyAnimeList import, or typed before) is lit from
    the start, and the row says so; change any light to say which ones.
  - Lighting the first one fills an empty *Started* with today; lighting the last fills an
    empty *Finished*. Dates you already have are never changed.
  - No ratings or notes per episode: it is a tracker, nothing more.
- **Series seasons come from TVmaze.** New series bring their season list. One added before
  2.7 offers *Load the episode list* when you open its row.
- **Books count chapters.** A book's row asks *How many chapters?* once; Open Library fills it
  in when its contents number them. The lights are numbered, not named.
- **Dropping asks how far you got.** Set something to *Dropped*, from its page or from a card
  in the library, and *How far did you get?* opens: tap the last episode or chapter you
  finished and everything up to it lights. *Skip* saves nothing more. The inbox, the deck and
  bulk changes do not ask.
- *Edit opinion* no longer has a progress field: the row is the one place the count changes.

## Upgrade

**Tagged `v2.7.0`.** Minor release with one migration, `0027`, which adds a nullable
`entries.progress_marks` column; the application backs the database up before migrating, as
for every migration. No breaking change and no owner action.

```bash
docker compose pull && docker compose up -d
```

If you pin in `.env`, move the pin to `AKASHA_VERSION=2.7.0` (or track the `2.7` line).

The JSON export carries the marks; Started and Finished dates go where they always did.
