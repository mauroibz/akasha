# Akasha — mark and lockup

Companion to `brand-handoff.md`. Every colour here comes from the application's own
tokens; nothing new was introduced. If a token in `frontend/src/index.css` changes,
this file is out of date.

---

## The mark

An arch enclosing a single point of light.

The arch is the akashic reading — a space you enter, not an object you hold. The dot
is the only thing inside it: one record, one opinion, held in otherwise empty space.
This is the whole idea, and it is deliberately not a book. A book pictogram would say
*this app holds books*; the product holds what one person thought of them.

The reference is confirmed: "Akasha" is used for the akashic-records sense, per Mauro.
Worth recording in `docs/decisions.md` alongside DEC-026 — the handoff flagged it as
unverified.

### Construction

Drawn on Lucide's grid, because at 20px in the nav the mark is read as a sibling of
`library-big` and `bookmark`, not as a separate object.

| Property | Value |
|---|---|
| viewBox | `0 0 24 24` |
| stroke-width | `2` |
| stroke-linecap | `round` |
| stroke-linejoin | `round` |
| Arch | `M4 21V10a8 8 0 0 1 16 0v11` |
| Dot | `cx 12, cy 11, r 2` |

The arch has open feet. Closing them with a baseline reads more like a container and
less like a tunnel, but costs a stroke that is the first thing to die at 16px. Open
feet was the call; it is reversible.

### The one deviation from Lucide

The dot is **filled**. Lucide is stroke-only throughout. A stroke circle at `r 1` —
what Lucide would draw — turns to mush at 16px, where this mark is seen most. Filled
was the pragmatic choice and it is the single place the mark is not a true sibling of
its neighbours.

---

## Colour

| Element | Hex | Token |
|---|---|---|
| Arch | `#fafafa` | zinc-50 |
| Dot | `#fbbf24` | amber-400 |
| Ground | `#09090b` | zinc-950 |

In code the arch inherits `currentColor`; only the dot is hardcoded. The mark needs no
second brand colour, and must not acquire one.

**Single-colour version** (`mark-mono.svg`, or `<AkashaMark mono />`): both elements
take `currentColor`. Use it as a mask, in amber-on-dark, and anywhere the two-colour
version would be reduced to one channel anyway.

Do not draw the dot from the 1–10 score ramp. That ramp is semantic — it says how much
someone liked a book — and borrowing from it would imply the mark is rating something.

---

## Clear space

**4 units on the 24 grid** — one arch-foot — on all four sides, scaling with the mark.

```
20px mark  →  3.3px   32px mark  →  5.3px   48px mark  →  8px
```

Nothing crosses it: no text, no rule, no adjacent icon. In the nav, this is what keeps
the mark from binding to the wordmark beside it.

---

## Sizes and which file to use

| Context | Size | File |
|---|---|---|
| Browser tab | 16px | `favicon/favicon-16.svg` / `.png` |
| Navigation | 20px | `AkashaMark.tsx` |
| Library header lockup | 48px | `lockup-horizontal.svg` |
| Installed app icon | 32–512px | `favicon/favicon-{32,48,180,192,512}.png` |

**The 16px file is a separate drawing, not a scaled one.** It sits on a 16 grid with
the strokes hinted onto whole pixels and the dot as a crisp 2×2 block; caps are `butt`
and joins `miter` so the feet land on the pixel edge. Letting the browser scale the 24
grid down to 16 produces a soft arch and a smudged dot. Use the 24 grid at 20px and up.

**The favicons carry the ground colour baked in.** Transparent white-on-nothing
disappears against a light browser tab strip, which is most of them. The in-app files
(`mark.svg`, the React component) are transparent, because the app surface is already
`#09090b`.

---

## Lockup

`lockup-horizontal.svg` keeps the existing header pairing rather than replacing it —
the wide-tracked amber eyebrow over the tight-tracked wordmark, with the mark set to
the left at 48px.

```
PERSONAL LIBRARY     11px · 600 · uppercase · 0.3em tracking · #fbbf24
Akasha               32px · 600 · -0.025em tracking · #fafafa
```

The wordmark is **set, not lettered** — Inter Variable at the tokens already in the
codebase. There is no custom letterform to license, redraw, or keep in sync, and it
cannot drift from the body text it sits beside. The SVG references
`'Inter Variable', Inter, sans-serif`; it renders correctly wherever the app's
self-hosted Inter is loaded, and falls back gracefully elsewhere. If you need it to
survive outside the app — a README on GitHub, an OG image — convert the two `<text>`
elements to outlines in that copy only, and keep this one editable.

At 32px the wordmark is the header size. Scale the whole lockup as a unit; do not
re-set the type at a different size against a fixed mark.

---

## Files

Where each file actually lives, as wired up:

```
docs/brand/source/mark.svg                    24 grid, currentColor arch, amber dot
docs/brand/source/mark-mono.svg               24 grid, single flat fill
docs/brand/source/lockup-horizontal.svg       mark + eyebrow + wordmark
docs/brand/source/lockup-horizontal-mono.svg  same, single colour
docs/brand/source/mark-on-dark.svg            explicit colours for GitHub dark
docs/brand/source/mark-on-light.svg           explicit colours for GitHub light

frontend/src/components/AkashaMark.tsx        React component, Lucide-compatible props

frontend/public/favicon.svg                   24 grid with ground baked in
frontend/public/favicon-16.svg                hand-hinted 16 grid
frontend/public/favicon-16.png
frontend/public/favicon-32.png
frontend/public/favicon-48.png
frontend/public/favicon-180.png               apple-touch-icon
frontend/public/favicon-192.png               web app manifest
frontend/public/favicon-512.png               web app manifest
frontend/public/manifest.webmanifest
```

The favicons sit flat in `frontend/public/`, not in a `favicon/` subfolder, because
Vite serves that directory at the site root and the `<link href>` values in
`index.html` are therefore `/favicon-32.png` and so on.

**`mark.svg` uses `currentColor` and must not be used in a README.** An `<img>` has no
CSS context, so `currentColor` resolves to black and the mark disappears on a dark
page. `mark-on-dark.svg` and `mark-on-light.svg` exist for that, paired in a
`<picture>` element.

---

## Wiring it up

In `index.html`:

```html
<link rel="icon" href="/favicon-16.png" sizes="16x16" type="image/png" />
<link rel="icon" href="/favicon-32.png" sizes="32x32" type="image/png" />
<link rel="icon" href="/favicon.svg" type="image/svg+xml" />
<link rel="apple-touch-icon" href="/favicon-180.png" />
<meta name="theme-color" content="#09090b" />
```

The PNGs are listed before the SVG deliberately: browsers that support SVG favicons
prefer them regardless of order, and the ones that don't take the first PNG they can
use. This way the hinted 16px raster wins on the browsers that need it.

In `AppShell.tsx`:

```tsx
import { AkashaMark } from "@/components/AkashaMark";

<AkashaMark size={20} className="text-zinc-50" />
```

In `manifest.webmanifest`:

```json
{
  "name": "Akasha",
  "short_name": "Akasha",
  "background_color": "#09090b",
  "theme_color": "#09090b",
  "icons": [
    { "src": "/favicon-192.png", "sizes": "192x192", "type": "image/png" },
    { "src": "/favicon-512.png", "sizes": "512x512", "type": "image/png" }
  ]
}
```

---

## What not to do

- Don't scale the 24 grid down to 16. Use the hinted file.
- Don't add a second colour. Amber is the only non-neutral in the interface.
- Don't fill the arch, add a gradient, or add a shadow. The interface has flat fills
  and 1px borders and nothing else.
- Don't put the mark on a light background. There is no light theme and none planned;
  the mono version exists for the cases where you'd be tempted.
- Don't set the dot from the score ramp.
- Don't re-letter the wordmark. It is Inter by design.
