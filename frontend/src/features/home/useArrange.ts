import {
  useEffect,
  useRef,
  useState,
  type KeyboardEvent,
  type PointerEvent,
} from "react";

import type { ModuleLayout, ModuleSize } from "@/api/home";

import { labelOf } from "./layout";

/** `module` taken out of `layout` and put back so it is the `to`-th of those shown. */
export function movedAmongShown(
  layout: ModuleLayout[],
  module: string,
  to: number,
): ModuleLayout[] {
  const row = layout.find((item) => item.module === module);
  if (!row) return layout;
  const rest = layout.filter((item) => item.module !== module);
  const shown = rest.filter((item) => !item.hidden);
  const place = Math.max(0, Math.min(shown.length, to));
  // Before the showcase now at that place; after every shown one when it is last.
  const before = shown[place];
  const index = before
    ? rest.indexOf(before)
    : shown.length
      ? rest.indexOf(shown[shown.length - 1]) + 1
      : 0;
  return [...rest.slice(0, index), row, ...rest.slice(index)];
}

/**
 * Arranging the Library where it stands (Sprint 142, DEC-193): the showcases are
 * moved, resized and removed on the screen itself, and added from a tray. Every
 * change is handed to `onChange` at once, so it is stored as it is made. This is
 * the state and the gestures; `ArrangeControls` and `ArrangeTray` draw them.
 *
 * It replaces *Edit home*, a dialog that listed the modules over the screen it was
 * editing. The drag is pointer events on the handle rather than a library, as the
 * tier board moves covers: one gesture for a mouse and a finger.
 */
export function useArrange(
  layout: ModuleLayout[],
  onChange: (next: ModuleLayout[]) => void,
) {
  const boxes = useRef(new Map<string, HTMLElement>());
  const handles = useRef(new Map<string, HTMLButtonElement>());
  const focusAfter = useRef<string | null>(null);
  const [dragging, setDragging] = useState<string | null>(null);
  const [preview, setPreview] = useState<ModuleLayout[] | null>(null);
  const [announcement, setAnnouncement] = useState("");
  // What the last change made, before the parent has rendered it back: two arrow
  // presses in quick succession must move twice, not twice from the same place.
  const latest = useRef(layout);
  const received = useRef(layout);
  if (received.current !== layout) {
    received.current = layout;
    latest.current = layout;
  }
  const nameOf = (module: string) =>
    labelOf(latest.current.find((row) => row.module === module) ?? { module });
  const commit = (next: ModuleLayout[]) => {
    latest.current = next;
    onChange(next);
  };

  useEffect(() => {
    if (!focusAfter.current) return;
    handles.current.get(focusAfter.current)?.focus();
    focusAfter.current = null;
  });

  const patch = (module: string, change: Partial<ModuleLayout>) =>
    commit(
      latest.current.map((row) =>
        row.module === module ? { ...row, ...change } : row,
      ),
    );

  const moveBy = (module: string, step: number) => {
    const shown = latest.current.filter((row) => !row.hidden);
    const from = shown.findIndex((row) => row.module === module);
    const to = from + step;
    if (from < 0 || to < 0 || to >= shown.length) return;
    focusAfter.current = module;
    commit(movedAmongShown(latest.current, module, to));
    setAnnouncement(`${nameOf(module)} moved to ${to + 1} of ${shown.length}`);
  };

  /** Where the pointer is among the other showcases, in reading order. */
  const placeAt = (
    current: ModuleLayout[],
    module: string,
    x: number,
    y: number,
  ) => {
    let place = 0;
    for (const row of current) {
      if (row.hidden || row.module === module) continue;
      const box = boxes.current.get(row.module)?.getBoundingClientRect();
      if (!box) continue;
      const below = y > box.bottom;
      const sameRow = y >= box.top && y <= box.bottom;
      if (below || (sameRow && x > box.left + box.width / 2)) place += 1;
    }
    return place;
  };

  return {
    shown: preview ?? layout,
    dragging,
    announcement,
    box: (module: string) => (node: HTMLElement | null) => {
      if (node) boxes.current.set(module, node);
      else boxes.current.delete(module);
    },
    handle: (module: string) => ({
      ref: (node: HTMLButtonElement | null) => {
        if (node) handles.current.set(module, node);
        else handles.current.delete(module);
      },
      onKeyDown: (event: KeyboardEvent<HTMLButtonElement>) => {
        const step =
          event.key === "ArrowLeft" || event.key === "ArrowUp"
            ? -1
            : event.key === "ArrowRight" || event.key === "ArrowDown"
              ? 1
              : 0;
        if (!step) return;
        event.preventDefault();
        moveBy(module, step);
      },
      onPointerDown: (event: PointerEvent<HTMLButtonElement>) => {
        if (event.button !== 0) return;
        event.currentTarget.setPointerCapture?.(event.pointerId);
        setDragging(module);
        setPreview(latest.current);
      },
      onPointerMove: (event: PointerEvent<HTMLButtonElement>) => {
        if (dragging !== module || !preview) return;
        const next = movedAmongShown(
          preview,
          module,
          placeAt(preview, module, event.clientX, event.clientY),
        );
        if (next.some((row, index) => row.module !== preview[index].module))
          setPreview(next);
      },
      onPointerUp: () => {
        if (dragging !== module) return;
        const next = preview;
        setDragging(null);
        setPreview(null);
        if (
          next &&
          next.some(
            (row, index) => row.module !== latest.current[index]?.module,
          )
        ) {
          commit(next);
          const shown = next.filter((row) => !row.hidden);
          const to = shown.findIndex((row) => row.module === module);
          setAnnouncement(
            `${nameOf(module)} moved to ${to + 1} of ${shown.length}`,
          );
        }
      },
    }),
    resize: (module: string, size: ModuleSize) => patch(module, { size }),
    remove: (module: string) => {
      const name = nameOf(module);
      patch(module, { hidden: true });
      setAnnouncement(`${name} removed`);
    },
    add: (module: string) => {
      const name = nameOf(module);
      // Added at the end of what is shown, where the eye lands after the tray.
      const row = latest.current.find((item) => item.module === module);
      if (!row) return;
      const rest = latest.current.filter((item) => item.module !== module);
      const last = rest.reduce(
        (index, item, at) => (item.hidden ? index : at),
        -1,
      );
      commit([
        ...rest.slice(0, last + 1),
        { ...row, hidden: false },
        ...rest.slice(last + 1),
      ]);
      focusAfter.current = module;
      setAnnouncement(`${name} added`);
    },
  };
}

export type Arrange = ReturnType<typeof useArrange>;
