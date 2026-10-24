# Akasha v2.8.0 — release notes

The house and the history. Sprints 109–127 (DEC-176 to DEC-179).

## What you will notice

### Where things are, and who has them

- **Where it is.** Any entry can say where it lives ("Living room, shelf 2"). Search shows
  it, and the library filters by place.
- **Lent out.** Lend something from its page (*Lend…*): who has it and since when. What is
  out stands as the first ledge on **Shelves**, and *It's back* is one tap.

### Finishing, and the reading data

- **Finished.** Anything under way has a *Finished* button on its page and on its card in
  *Now*. One sheet asks when (today is chosen), the score and the format; skip any of them.
  Starting something fills an empty *Started* with today.
- **Only what is there.** The reading panel shows the rows that hold something. Below them,
  one question at a time asks about the most useful gap: when you finished it, how you have
  it, where it is, when you started. *I don't remember* stops that question for that entry.
- **Undo** after changing a status or score from a library card. **Fill from provider**
  under Edition facts fills empty fields only and never overwrites.

### Scores over time

- **Every score change is kept**, with its date and why: a reread, or just time. The page
  shows it under *Over time*.
- **Start again** begins a reread; finishing it asks "Still an 8?".
- **Put your 8s in order:** pick the better of two at a time. Scores never change, and the
  library's score sort follows your order. **Tiers** (`/tiers`): move things between scores
  as a proposal, applied only when you press *Apply*.

### Play, the Diary and the shelves

- **Play with your library**, at the top of Insights: *Which 8 is your best 8?*, *Is Tokio
  blues still a 10?* (a score over a year old), the pile (*Still want these?*), and *Fill in
  the gaps*. *Five minutes* mixes them into one round of five and ends with what changed.
- **Tidy up** (Settings, or the command bar): the inbox, *Find a cover* and *Duplicates*,
  where you pick which copy to keep and nothing the other holds is lost.
- **The Diary leads with your goal.** Without one, it offers three (one every two months,
  one a month, two a month), set in one tap. With one, a slot for each thing you are aiming
  at, filled by the year's covers. *All years* is one timeline with score changes, and
  *Your 2026 in review* reads the year back.
- **Suggested shelves:** the same author three times, a series, or one work across libraries
  (*Dune* the book and the film). Make one in a tap, or dismiss it for good.

## Upgrade

**Tagged `v2.8.0`.** Minor release with six migrations, `0028` to `0033`: entry locations and
loans, duplicate dismissals, the score history (with triggers that record each change; every
existing score gets its first row, dated by its finish date or else when it was added), the
rank inside a score, shelf-suggestion dismissals, and the fields you do not remember. The
application backs the database up before migrating, as for every migration. No breaking
change and no owner action.

```bash
docker compose pull && docker compose up -d
```

If you pin in `.env`, move the pin to `AKASHA_VERSION=2.8.0` (or track the `2.8` line).

The JSON export carries locations, loans, the score history, ranks and the fields you do not
remember.
