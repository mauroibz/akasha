# Akasha v3.1.0 — release notes

The owner's first review of 3.0. Sprints 137–138 (DEC-192).

## What you will notice

- **Finishing records when.** Setting something to *Read* (or *Watched*, *Completed*) on a
  library card now opens the finish sheet: *Today* is already chosen, so *Finish* is one tap,
  and *Yesterday* or *Another day* are there if it was not today. The same sheet asks for the
  score and, if none is recorded, the format. *Cancel* leaves the card as it was. In *Edit
  opinion*, choosing a finished status with no finished date fills in today; you can change it
  before saving. Bulk changes and the Inbox are unchanged, since they sort imports finished long
  ago.
- **The finish button says what it does.** *Finished* is now *Mark as read* on a book, *Mark as
  watched* on a film, *Mark as completed* on an anime or series: on the library's Now strip,
  Home's *On now* and *Up next*, and an item's page.
- **A varied Up next.** The pile is ordered so that every author's best pick comes before any
  author's second. Several Stephen King books waiting no longer fill *Up next*: one comes first,
  then other authors, then the next King.
- **The pile as a list.** *N on the pile* (in *Up next* and the greeting) opens a new page,
  `/pile`: everything waiting across your libraries, in the order *Up next* offers it, each with
  its reason, *Start*, and a filter by library. *Sort* beside it (and *Sort in cards* on the page)
  is the card deck it used to open.
- **Each library's year on Home.** The Diary goal's grid of what you finished is now a Home
  module for every library that has finished something this year or has a goal: "Your 2026
  books", the covers in the order you finished them, and with a goal of 24 or fewer an empty
  slot for each one still to come. Without a goal it shows the year's covers. They are on by
  default, after *Lately*.
- **Shelves on Home.** Each of your shelves can be placed on Home as its own module: its name,
  how many it holds, and the covers of what changed last. They are off until you turn them on
  in *Edit home*, where each library's year and each shelf can be shown, hidden, resized and
  moved like any other module.

## Upgrade

**Tagged `v3.1.0`.** No migration and no new setting.

```bash
docker compose pull && docker compose up -d
```

If you pin in `.env`, move the pin to `AKASHA_VERSION=3.1.0`. A layout you saved in 3.0 keeps
its order; the libraries' years are added at the end of it and your shelves after them,
hidden. *Reset* in *Edit home* puts the years after *Lately*.

## Still to check live (yours)

Unchanged from 3.0: the *Model* and *From your library* sources have not answered a real
request yet (see the 3.0 notes).
