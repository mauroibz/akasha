import { useRef, type KeyboardEvent } from "react";

import type { OutlinePart, ProgressMarks } from "@/api/library";
import { capital, isMarked, partState } from "@/features/progress/marks";
import { cn } from "@/lib/utils";

/**
 * The lights: one per episode or chapter, lit when done, in the goal calendar's style
 * (DEC-169, DEC-171). Unlit places are plain, never red, and nothing says behind.
 *
 * Each light is a toggle button named for what it is ("Season 2, episode 5"); its
 * state is `aria-pressed`, so no verb ("watched", "read") has to be chosen for the
 * domain. One light holds the tab stop and the arrow keys move between them: left
 * and right along the outline, up and down to the same place in the part beside.
 */
export function Lights({
  outline,
  marks,
  unit,
  partLabel,
  onLight,
  onPart,
  label,
}: {
  outline: OutlinePart[];
  marks: ProgressMarks;
  /** The singular unit: "episode", "chapter". */
  unit: string;
  /** What one part is called, from the domain's declaration ("Season"); absent for a
   * domain whose outline is one part. */
  partLabel?: string | null;
  onLight: (part: number, number: number) => void;
  /** A tap on a part's label; absent where a part is not a thing to tap. */
  onPart?: (part: OutlinePart) => void;
  label: string;
}) {
  const refs = useRef(new Map<string, HTMLButtonElement>());
  const labelled = outline.length > 1 && Boolean(partLabel);
  const first = outline[0];
  const firstOpen = outline
    .flatMap((part) =>
      Array.from({ length: part.size }, (_, i) => [part.part, i + 1] as const),
    )
    .find(([part, number]) => !isMarked(marks, part, number));
  const [tabPart, tabNumber] = firstOpen ?? [first?.part ?? 1, 1];

  function focus(partIndex: number, number: number) {
    const part = outline[partIndex];
    if (!part) return;
    const clamped = Math.max(1, Math.min(number, part.size));
    refs.current.get(`${part.part}:${clamped}`)?.focus();
  }

  function onKeyDown(
    event: KeyboardEvent<HTMLButtonElement>,
    partIndex: number,
    number: number,
  ) {
    const part = outline[partIndex];
    const moves: Record<string, () => void> = {
      ArrowRight: () =>
        number < part.size
          ? focus(partIndex, number + 1)
          : focus(partIndex + 1, 1),
      ArrowLeft: () =>
        number > 1
          ? focus(partIndex, number - 1)
          : focus(partIndex - 1, outline[partIndex - 1]?.size ?? 1),
      ArrowDown: () => focus(partIndex + 1, number),
      ArrowUp: () => focus(partIndex - 1, number),
      Home: () => focus(partIndex, 1),
      End: () => focus(partIndex, part.size),
    };
    const move = moves[event.key];
    if (!move) return;
    event.preventDefault();
    move();
  }

  return (
    <div role="group" aria-label={label} className="space-y-3">
      {outline.map((part, partIndex) => {
        const state = partState(marks, part);
        const name = labelled ? `${partLabel} ${part.part}` : null;
        return (
          <div
            key={part.part}
            data-part={part.part}
            className={cn(labelled && "grid gap-2 sm:grid-cols-[6.5rem_1fr]")}
          >
            {name &&
              (onPart ? (
                <button
                  type="button"
                  onClick={() => onPart(part)}
                  aria-label={
                    state === "all"
                      ? `Clear ${name.toLowerCase()}`
                      : `Mark all of ${name.toLowerCase()}`
                  }
                  className={cn(
                    "min-h-8 justify-self-start rounded-md text-left text-sm focus-ring",
                    state === "all"
                      ? "font-medium text-primary"
                      : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  {name}
                </button>
              ) : (
                <span className="text-sm text-muted-foreground">{name}</span>
              ))}
            <div className="flex flex-wrap gap-1.5">
              {Array.from({ length: part.size }, (_, index) => {
                const number = index + 1;
                const lit = isMarked(marks, part.part, number);
                const lightName = name
                  ? `${name}, ${unit} ${number}`
                  : `${capital(unit)} ${number}`;
                return (
                  <button
                    key={number}
                    ref={(node) => {
                      const key = `${part.part}:${number}`;
                      if (node) refs.current.set(key, node);
                      else refs.current.delete(key);
                    }}
                    type="button"
                    aria-pressed={lit}
                    aria-label={lightName}
                    title={lightName}
                    data-light={lit ? "lit" : "unlit"}
                    tabIndex={
                      part.part === tabPart && number === tabNumber ? 0 : -1
                    }
                    onClick={() => onLight(part.part, number)}
                    onKeyDown={(event) => onKeyDown(event, partIndex, number)}
                    className={cn(
                      "block h-6 w-5 rounded-[7px] transition-[background-color,box-shadow] duration-150 focus-ring motion-reduce:transition-none",
                      lit
                        ? "bg-primary shadow-[0_0_0_3px_hsl(var(--primary)/0.16),0_0_12px_hsl(var(--primary)/0.5)]"
                        : "bg-muted hover:bg-muted-foreground/25",
                    )}
                  />
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}
