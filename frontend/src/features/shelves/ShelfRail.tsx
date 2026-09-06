/**
 * A shelf's covers, stood up side by side at one height, in their own widths, on a
 * rule (Sprint 074 deliverable 2, proposal §3.3.1) — not three overlapping
 * thumbnails in a corner (`CoverStack`'s own shape), which left the rest of the
 * card's width empty (the owner's note on the proposal's first draft).
 *
 * Deliberately **not** a generalization of `CoverStack` (`InsightsRanking.tsx`):
 * that component is a fixed-size, up-to-three overlapping stack meant to sit
 * beside a ranking row's text. This is an unbounded, naturally-sized, horizontally
 * scrolling rail — a different shape for a different question ("what is on this
 * shelf" rather than "a hint of what's in this group"), so it is its own
 * component rather than a shared one bent to fit both.
 *
 * The rail itself holds no focusable child and is `aria-hidden`: the card around
 * it is the one link naming the shelf and its count (AC2), so a keyboard or
 * screen reader user is never parked inside a horizontally scrolling region.
 * `scroll-snap-type: x proximity` rather than `mandatory`, so a partial scroll
 * does not fight a vertical page swipe on a phone (the sprint's own named risk).
 */
export function ShelfRail({ covers }: { covers: string[] }) {
  if (covers.length === 0) return null;
  return (
    <div className="relative" aria-hidden="true">
      <div
        data-shelf-rail=""
        className="flex items-end gap-1.5 overflow-x-auto px-3 pb-2.5"
        style={{ scrollSnapType: "x proximity", scrollbarWidth: "none" }}
      >
        {covers.map((src, index) => (
          <img
            // `${src}-${index}` rather than a bare `src`: real cover URLs are
            // always unique (an item id and a cover version), but nothing
            // here should assume it -- a rail built from duplicate URLs must
            // not warn React into thinking two children share an identity.
            key={`${src}-${index}`}
            src={src}
            alt=""
            className="h-[74px] w-auto shrink-0 rounded-sm shadow-[0_6px_10px_-6px_rgba(0,0,0,0.9)]"
            style={{ scrollSnapAlign: "start" }}
            // Only the first handful are ever visible before the fade; the rest
            // load as the reader actually scrolls to them.
            loading={index < 6 ? "eager" : "lazy"}
          />
        ))}
      </div>
      {/* The rule the covers stand on, and the fade that says the rail keeps
          going past the card's own edge. */}
      <div className="pointer-events-none absolute inset-x-3 bottom-2 h-px bg-border" />
      <div className="pointer-events-none absolute inset-y-0 right-0 w-8 bg-gradient-to-l from-surface to-transparent" />
    </div>
  );
}
