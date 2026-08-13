# Akasha — brand handoff

> **This is the original brief, kept as written.** The mark was designed against it
> and now ships: see [`BRAND.md`](BRAND.md) for the mark, its construction and its
> usage rules, and `source/` for the files. Two things this brief states are no
> longer true — there *is* a favicon now, and the akashic-records reading of the
> name has since been confirmed by the owner.

A brief for whoever designs the logo. Every colour, radius, weight and size below is
taken from the application's own tokens in `frontend/src/index.css` and
`frontend/tailwind.config.ts`, governed by decision DEC-026. Nothing here was
invented for this document. If a token changes in code, this file is out of date.

---

## What Akasha is

A self-hosted book tracker for one person. It records **what you thought of a book** —
not the file, not the metadata.

It runs on a small server in someone's house. One user, no accounts, no social layer,
no sharing. You add a book, give it a score out of ten, write a note, put it on a
shelf. There is a keyboard-driven triage view for working through a backlog quickly.

The tone is **quiet, dense, and personal** — closer to a card catalogue or a reading
journal than to a social reading app. Nothing in it is playful or exclamatory. The
interface is almost entirely greyscale with a single warm accent, and it earns its
warmth by being sparing.

> **On the name.** "Akasha" is a Sanskrit word for ether or open space, and the root of
> "akashic records" — the idea of a complete compendium of everything that has happened.
> Suggestive for a library of everything one person has read, but **this is not recorded
> anywhere in the project as the intended reference.** Confirm with Mauro before building
> a concept on it.

---

## Environment: dark only

The application declares `color-scheme: dark` and has **no light mode**. There is no
light-background context to design for, now or planned.

| Role | Hex | Tailwind | Used for |
|---|---|---|---|
| Ground | `#09090b` | zinc-950 | page background; what a favicon sits on |
| Surface | `#18181b` | zinc-900 | cards, popovers, the nav bar |
| Raised | `#27272a` | zinc-800 | borders, inputs, hover states |
| Text | `#fafafa` | zinc-50 | primary text |
| Muted | `#a1a1aa` | zinc-400 | secondary text |

The neutral ramp is Tailwind's zinc — very slightly cool, not a pure grey.

---

## Accent: one colour, used sparingly

| Role | Hex | HSL | Tailwind |
|---|---|---|---|
| Accent | `#fbbf24` | `hsl(43 96% 56%)` | amber-400 |

Amber is the only non-neutral in the interface. It marks the active nav item, the
primary button, focus rings, and the eyebrow label above the wordmark. Everything else
is zinc.

Amber on `#09090b` is the brand pairing. When amber is a **fill**, the text on it is
`#09090b` — never white on amber.

**A mark that leans on a second brand colour will not belong here.**

### Not brand colours

Scores 1–10 run along a four-step ramp. This is semantic — it says how much someone
liked a book — and it is the one place other hues appear. Do not draw from it.

| Range | Hex | Tailwind |
|---|---|---|
| 1–3 | `#f87171` | red-400 |
| 4–6 | `#fbbf24` | amber-400 |
| 7–8 | `#a3e635` | lime-400 |
| 9–10 | `#34d399` | emerald-400 |

---

## Typography

**Inter Variable**, self-hosted (`@fontsource-variable/inter`). Not loaded from a CDN.

| Role | Setting |
|---|---|
| Wordmark | 600 weight, `-0.025em` tracking |
| Headings | 600 weight, `-0.02em` tracking |
| Nav items, labels | 500 weight |
| Body | 400 weight, 1.65 line-height |
| Eyebrow | 600, uppercase, `0.3em` tracking, 11px, amber |

### The one distinctive habit

The library page header sets a wide-tracked amber label above a tight-tracked wordmark:

```
PERSONAL LIBRARY        ← 11px, 600, uppercase, 0.3em tracking, #fbbf24
Akasha                  ← 36px, 600, -0.025em tracking, #fafafa
```

This pairing is the closest thing the product already has to an identity. **A logo
lockup should either use it or knowingly replace it.**

If the wordmark is lettered rather than set, it still has to sit next to Inter body
text without arguing with it.

---

## Iconography — the strongest constraint

Navigation uses **Lucide** icons, rendered at **20px**. Lucide's geometry:

- 24 × 24 viewBox
- `stroke-width: 2`
- `stroke-linecap: round`, `stroke-linejoin: round`
- no fill

The nav icons the mark will sit beside: `library-big`, `plus`, `inbox`, `upload`,
`bookmark`.

At small sizes the mark is read as a **sibling of these**, not as a separate object.
This is the single strongest constraint on the design.

### Radii

| Token | Value | Used for |
|---|---|---|
| `--radius` | `10px` | cards, panels, buttons |
| `--radius-control` | `4px` | checkboxes, small controls |

At 10px a 16px checkbox starts reading as a radio button, which is why there are two.
If the mark has a container, those are the two radii to match.

---

## Where the mark appears, and at what size

| Context | Size | Notes |
|---|---|---|
| Browser tab favicon | **16px** | **Nothing exists today.** The most-seen instance by a wide margin. |
| Primary navigation | 20px | Directly beside Lucide icons at the same size |
| Library header lockup | ~48px | Paired with the eyebrow + wordmark |
| Installed app icon | 32 / 48 / 64 / 96px | On the ground colour `#09090b` |

The browser `theme-color` is `#09090b`.

---

## Deliverables

- [ ] **Icon mark, SVG** — square, on a 24px grid so it aligns with Lucide. Must hold at 16px.
- [ ] **Favicon set** — 16, 32, 48px PNG plus source SVG. Nothing exists today, so this is the piece actively missing.
- [ ] **Wordmark** — Inter 600 at `-0.025em`, or a lettered alternative that sits beside Inter body text.
- [ ] **Horizontal lockup** — mark plus wordmark, with the clear-space rule stated.
- [ ] **Single-colour version** — one flat fill, no gradient. For amber-on-dark and for use as a mask.
- [ ] **Source file** — editable vector, outlines not flattened.

---

## What will not work here

- **A mark that needs a light background.** No light theme, none planned. It has to read on `#09090b`.
- **A second brand colour.** Amber is the only accent in the whole interface.
- **Detail that dies at 16px.** The favicon is the most-seen instance of this mark.
- **Gradients and soft shadows.** The interface has neither — flat fills and 1px borders only.
- **An open-book pictogram.** Not forbidden, but it is the obvious answer, and the product is deliberately not about books as objects. It is about one person's opinions of them.
- **Anything playful or exclamatory.** The voice is plain and quiet throughout. No mascots.

---

## Worth knowing

Akasha runs on a home network with no login, so the mark has no marketing job to do.
It is wayfinding: a tab among thirty tabs, an icon on a phone home screen.

**Legibility at small size beats distinctiveness at large size, every time.**

---

## Source of truth

| What | Where |
|---|---|
| Colour, radius, font tokens | `frontend/src/index.css` |
| Token → Tailwind mapping | `frontend/tailwind.config.ts` |
| The design direction decision | `docs/decisions.md`, DEC-026 |
| Header lockup markup | `frontend/src/pages/HomePage.tsx` |
| Nav and icon usage | `frontend/src/components/AppShell.tsx` |
