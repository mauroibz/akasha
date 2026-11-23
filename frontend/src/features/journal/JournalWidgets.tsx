import { useId, useState, type ReactNode } from "react";

import { cn } from "@/lib/utils";

export interface JournalWidget {
  id: string;
  label: string;
  render: () => ReactNode;
}

export const widgetKey = "akasha.journal.widget";

function remembered(widgets: JournalWidget[]): string {
  try {
    const stored = localStorage.getItem(widgetKey);
    if (stored && widgets.some((widget) => widget.id === stored)) return stored;
  } catch {
    // A browser that refuses storage still gets the first widget.
  }
  return widgets[0]?.id ?? "";
}

/**
 * The Journal opens on one thing to do at a time (Sprint 146, DEC-193): a row of
 * tabs and the widget chosen, the last one used remembered in this browser. The
 * owner asked for this in place of a page to write on: "switch between different
 * widgets", with Play as the interactive part.
 *
 * Only the chosen widget is mounted, so one that is not looked at asks for nothing.
 */
export function JournalWidgets({ widgets }: { widgets: JournalWidget[] }) {
  const base = useId();
  const [chosen, setChosen] = useState(() => remembered(widgets));
  const current = widgets.find((widget) => widget.id === chosen) ?? widgets[0];
  if (!current) return null;
  const choose = (id: string) => {
    setChosen(id);
    try {
      localStorage.setItem(widgetKey, id);
    } catch {
      // Not remembered, still chosen.
    }
  };
  return (
    <section
      aria-label="Something to do"
      className="rounded-xl border border-border bg-surface p-4 sm:p-5"
    >
      <div
        role="tablist"
        aria-label="Journal widget"
        className="-mt-1 mb-4 flex gap-6 overflow-x-auto border-b border-border"
        onKeyDown={(event) => {
          const step =
            event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
          if (!step) return;
          event.preventDefault();
          const at = widgets.findIndex((widget) => widget.id === current.id);
          const next = widgets[(at + step + widgets.length) % widgets.length];
          choose(next.id);
          document.getElementById(`${base}-tab-${next.id}`)?.focus();
        }}
      >
        {widgets.map((widget) => (
          <button
            key={widget.id}
            id={`${base}-tab-${widget.id}`}
            type="button"
            role="tab"
            aria-selected={widget.id === current.id}
            aria-controls={`${base}-panel`}
            tabIndex={widget.id === current.id ? 0 : -1}
            onClick={() => choose(widget.id)}
            className={cn(
              "-mb-px min-h-11 shrink-0 border-b-2 px-0.5 text-[15px] font-medium transition-colors focus-ring",
              widget.id === current.id
                ? "border-primary text-foreground"
                : "border-transparent text-muted-foreground hover:text-foreground",
            )}
          >
            {widget.label}
          </button>
        ))}
      </div>
      <div
        id={`${base}-panel`}
        role="tabpanel"
        aria-labelledby={`${base}-tab-${current.id}`}
      >
        {current.render()}
      </div>
    </section>
  );
}
