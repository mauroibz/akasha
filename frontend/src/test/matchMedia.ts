/**
 * jsdom implements no media queries at all, and Motion's reduced-motion support
 * depends on one. `useReducedMotion` reads a module-level global that is seeded
 * once from `window.matchMedia("(prefers-reduced-motion)")` and thereafter kept
 * current only by a `change` listener. When `matchMedia` is missing entirely
 * Motion falls back to "animations allowed", which is the wrong default for a
 * headless suite: a component rendering at `initial={{ opacity: 0 }}` stays at
 * zero opacity until the frameloop advances, and `toBeVisible()` then fails for
 * a reason that has nothing to do with the behavior under test.
 *
 * So the suite installs a real, controllable implementation and defaults to
 * `reduce`. Flipping it must dispatch `change`, or Motion never re-reads it.
 */

type Listener = (event: MediaQueryListEvent) => void;

const REDUCED = "prefers-reduced-motion";

let reduced = true;
const lists = new Set<Stub>();

/**
 * Only the reduced-motion feature is modelled. Every other query reports
 * `false`, which is what a browser reports for a feature it does not support.
 */
class Stub {
  onchange: Listener | null = null;
  private readonly listeners = new Set<Listener>();

  constructor(readonly media: string) {}

  get matches(): boolean {
    if (!this.media.includes(REDUCED)) return false;
    return this.media.includes("no-preference") ? !reduced : reduced;
  }

  addEventListener(type: string, listener: Listener): void {
    if (type === "change") this.listeners.add(listener);
  }

  removeEventListener(type: string, listener: Listener): void {
    if (type === "change") this.listeners.delete(listener);
  }

  /** Motion registers through the legacy pair in some builds. */
  addListener(listener: Listener): void {
    this.listeners.add(listener);
  }

  removeListener(listener: Listener): void {
    this.listeners.delete(listener);
  }

  notify(): void {
    const event = {
      matches: this.matches,
      media: this.media,
      type: "change",
    } as MediaQueryListEvent;
    this.onchange?.(event);
    for (const listener of this.listeners) listener(event);
  }
}

export function installMatchMedia(): void {
  window.matchMedia = ((query: string) => {
    const list = new Stub(query);
    lists.add(list);
    return list as unknown as MediaQueryList;
  }) as typeof window.matchMedia;
}

/**
 * Set the preference and tell every registered listener. Call this *before*
 * `render`: Motion caches the preference at its first hook call, so a component
 * already mounted keeps the value it was born with.
 */
export function setPrefersReducedMotion(value: boolean): void {
  reduced = value;
  for (const list of lists) list.notify();
}
