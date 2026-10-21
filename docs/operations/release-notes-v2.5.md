# Akasha v2.5.0 — release notes

Character: Insights read back as prose, gentle goals on the Diary, and shelves that look like
shelves. Sprints 102–105 (DEC-169).

## What you will notice

- **Insights, read back to you.** The page opens on one sentence ("You keep 142 books and have
  finished 58. You rate generously. You return most to Julio Cortázar."), then numbered sections
  divided by rules instead of boxes:
  - your usual score drawn large beside ten small bars;
  - the library's first leading key as a ranked list with fanned covers;
  - subjects typeset by weight;
  - the decades as short bars;
  - a key with a handful of values (language) as one bar;
  - the rest one line each.

  Every value still opens the library filtered to it. Subjects that differ only by a ", general"
  are counted together, and a broken value such as `{'` is no longer listed.
- **Gentle goals.** On the Diary, *Set a gentle goal*: so many a month or a year, for books,
  films, anime or series. Albums record no finish date, so they have no goal.
  - **What you see.** The goal draws the year as a calendar of lights, after the Everyday
    Calendar: one light for each thing you finished, in its month.
  - **Catching up.** Months count together, so a slow month leaves room and a busy one fills it
    in. There are no streaks, no reminders, and nothing marked missed.
  - **Picks.** If you want them, the Diary offers two picks a month from what is waiting, each
    with its reason ("By Julio Cortázar, whose books you rate 9.0 on average", "Waiting since
    March 2024"). *Start* moves one to Reading or Watching; *Something else* swaps it.
- **Shelves with opinions.** The shelves page is a room of shelves. Each has its name large, a
  line ("11 books · 2 finished · you rate them 7.5"), and its covers standing on a wooden ledge.
  Hover over a cover, or tab to it, and it swings open on its spine to show the title, year and
  score inside; with reduced motion turned on it stays shut. A shelf's own page reads as a
  sentence over larger covers with nothing printed on them; status and score are changed on the
  entry's page.
- **Larger covers on the Diary,** a month's only cover largest.
- **Counts use each library's own plural:** "3 anime", not "3 animes".

## Upgrade

**Tagged `v2.5.0`.** Minor release: one migration (`0026`, goals), no breaking change, no owner
action. Startup takes a pre-migration backup before applying it.

```bash
docker compose pull && docker compose up -d
```

If you pin in `.env`, move the pin to `AKASHA_VERSION=2.5.0` (or track the `2.5` line).

A goal counts finish dates. Entries imported without one do not light the calendar until a
finish date is set on them.
