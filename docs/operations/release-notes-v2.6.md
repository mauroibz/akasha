# Akasha v2.6.0 — release notes

Character: the inbox, one entry at a time. Sprint 106 (DEC-170).

## What you will notice

- **One at a time.** The inbox header has a new primary button, *One at a time*, which opens
  the inbox as a deck of cards over the whole screen, with the inbox's own filter. On a phone
  the list cut every title to a few letters; the deck shows each entry in full.
  - **The card.** A large cover (a typeset one when there is none) and the whole title under
    it. Tap the cover, or press `i`, and the card turns over to its back: subtitle, creator,
    year, formats, date added, the import's suggestion and a link to the full page.
  - **On the same screen.** The status as large buttons, a 1–10 score row (tap again to clear)
    and your shelves as toggles. Nothing scrolls, at phone width or on a desktop.
  - **File or Later.** *File* saves the status, the score if you touched it, and the shelves,
    then moves on. *Later* leaves the entry in the inbox and puts it at the back of the deck.
    Swipe right to file and left to pass; the card leans and is stamped as you drag.
  - **Undo** puts back the last card. A filed card gets its previous status, score and shelves
    back.
  - **Keys.** The status hotkeys, `1`–`9` and `0` for the score, `Enter` or `→` to file,
    `Space` or `←` for later, `Backspace` to undo, `Escape` to leave.
  - **The end of the deck** counts what you filed and passed, fans the filed covers, and offers
    *Go through the N you passed* or *Back to the inbox*.
- *Accept all suggested* is still in the inbox header, now beside *One at a time*.

## Upgrade

**Tagged `v2.6.0`.** Minor release: no migration, no breaking change, no owner action.

```bash
docker compose pull && docker compose up -d
```

If you pin in `.env`, move the pin to `AKASHA_VERSION=2.6.0` (or track the `2.6` line).
